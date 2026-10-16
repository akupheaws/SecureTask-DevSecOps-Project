import unittest, sys, pathlib, tempfile, json

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from normalize import normalize
from policy import evaluate


class SecurityTests(unittest.TestCase):
    def test_missing_evidence_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(
                evaluate(pathlib.Path(d), ["semgrep"], {"block_severities": ["High"]})[
                    1
                ]
            )

    def test_clean_evidence_passes(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "semgrep.status.json").write_text('{"completed":true}')
            (p / "semgrep.generic.json").write_text('{"findings":[]}')
            self.assertFalse(
                evaluate(p, ["semgrep"], {"block_severities": ["High"]})[1]
            )

    def test_high_finding_blocks_and_valid_exception_allows(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "semgrep.status.json").write_text('{"completed":true}')
            (p / "semgrep.generic.json").write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "title": "Injection",
                                "severity": "High",
                                "unique_id_from_tool": "abc",
                            }
                        ]
                    }
                )
            )
            policy = {"block_severities": ["High"], "exceptions": []}
            self.assertTrue(evaluate(p, ["semgrep"], policy)[1])
            policy["exceptions"] = [
                {
                    "tool": "semgrep",
                    "finding_id": "abc",
                    "approver": "reviewer",
                    "reason": "Isolated fixture",
                    "expires": "2099-01-01",
                }
            ]
            self.assertFalse(evaluate(p, ["semgrep"], policy)[1])
            policy["exceptions"][0]["expires"] = "2000-01-01"
            self.assertTrue(evaluate(p, ["semgrep"], policy)[1])

    def test_secrets_cannot_be_excepted(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "gitleaks.status.json").write_text('{"completed":true}')
            (p / "gitleaks.generic.json").write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "title": "Secret",
                                "severity": "High",
                                "unique_id_from_tool": "abc",
                            }
                        ]
                    }
                )
            )
            policy = {
                "block_severities": ["High"],
                "always_block_tools": ["gitleaks"],
                "exceptions": [
                    {
                        "tool": "gitleaks",
                        "finding_id": "abc",
                        "approver": "reviewer",
                        "reason": "test",
                        "expires": "2099-01-01",
                    }
                ],
            }
            self.assertTrue(evaluate(p, ["gitleaks"], policy)[1])

    def test_report_adapters(self):
        cases = {
            "semgrep": {
                "results": [
                    {
                        "check_id": "x",
                        "path": "a.ts",
                        "start": {"line": 1},
                        "extra": {"message": "SQL", "severity": "ERROR"},
                    }
                ]
            },
            "gitleaks": [
                {"RuleID": "x", "Description": "secret", "File": "a", "StartLine": 1}
            ],
            "hadolint": [
                {
                    "code": "DL3000",
                    "message": "path",
                    "file": "Dockerfile",
                    "line": 1,
                    "level": "warning",
                }
            ],
            "checkov": {
                "results": {
                    "failed_checks": [
                        {
                            "check_id": "CKV_AWS_20",
                            "check_name": "bucket",
                            "resource": "s3",
                            "file_path": "x.tf",
                            "file_line_range": [1],
                        }
                    ]
                }
            },
            "osv": {
                "results": [
                    {
                        "source": {"path": "package-lock.json"},
                        "packages": [
                            {
                                "package": {"name": "foo"},
                                "vulnerabilities": [
                                    {
                                        "id": "CVE-TEST",
                                        "summary": "bad",
                                        "database_specific": {"severity": "HIGH"},
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            "trivy": {
                "SchemaVersion": 2,
                "Results": [
                    {
                        "Target": "alpine",
                        "Vulnerabilities": [
                            {
                                "VulnerabilityID": "CVE-TEST",
                                "PkgName": "foo",
                                "Severity": "HIGH",
                            }
                        ],
                    }
                ],
            },
            "zap": {
                "site": [
                    {
                        "@name": "http://test",
                        "alerts": [
                            {
                                "pluginid": "1",
                                "name": "x",
                                "riskcode": "2",
                                "desc": "bad",
                            }
                        ],
                    }
                ]
            },
        }
        for tool, data in cases.items():
            with self.subTest(tool=tool):
                self.assertEqual(len(normalize(tool, data)["findings"]), 1)

    def test_malformed_reports_raise(self):
        for tool in [
            "semgrep",
            "gitleaks",
            "osv",
            "checkov",
            "hadolint",
            "trivy",
            "zap",
        ]:
            with self.subTest(tool=tool):
                with self.assertRaises((ValueError, TypeError, KeyError)):
                    normalize(tool, {"unexpected": "format"})


class DeploymentTests(unittest.TestCase):
    def test_ecs_rollback_is_not_reported_as_success(self):
        from unittest.mock import patch
        from deploy import deploy

        initial = {"services": [{"taskDefinition": "old"}]}
        definition = {
            "taskDefinition": {
                "family": "securetask-staging",
                "containerDefinitions": [{"name": "app", "image": "old-image"}],
            }
        }
        responses = [
            initial,
            definition,
            {"taskDefinition": {"taskDefinitionArn": "new"}},
            {},
            {"services": [{"taskDefinition": "old", "deployments": []}]},
            {},
        ]
        with patch("deploy.aws", side_effect=responses) as call, patch(
            "deploy.subprocess.run"
        ):
            with self.assertRaises(RuntimeError):
                deploy("securetask", "securetask-staging", "new-image")
            self.assertEqual(call.call_args.args[-1], "old")

    def test_smoke_failure_restores_previous_definition(self):
        from unittest.mock import patch
        from deploy import deploy

        responses = [
            {"services": [{"taskDefinition": "old"}]},
            {
                "taskDefinition": {
                    "family": "securetask-staging",
                    "containerDefinitions": [{"name": "app", "image": "old-image"}],
                }
            },
            {"taskDefinition": {"taskDefinitionArn": "new"}},
            {},
            {"services": [{"taskDefinition": "new", "deployments": []}]},
            {},
        ]
        with patch("deploy.aws", side_effect=responses) as call, patch(
            "deploy.subprocess.run"
        ), patch("smoke.smoke", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                deploy("securetask", "securetask-staging", "new-image", "http://test")
            self.assertEqual(call.call_args.args[-1], "old")


if __name__ == "__main__":
    unittest.main()
