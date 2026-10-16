import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from normalize import normalize
from policy import evaluate
from upload_findings import upload
import scan


class RemediationTests(unittest.TestCase):
    def test_two_source_findings_block_and_clean_scan_passes(self):
        raw = {
            "results": [
                {
                    "check_id": rule,
                    "path": path,
                    "start": {"line": 3},
                    "extra": {"message": title, "severity": "ERROR"},
                }
                for rule, path, title in [
                    (
                        "securetask.sql-concatenation",
                        "security/demo/unsafe-search.ts",
                        "SQL injection",
                    ),
                    (
                        "securetask.no-eval",
                        "security/demo/unsafe-expression.ts",
                        "Unsafe eval",
                    ),
                ]
            ]
        }
        policy = {"block_severities": ["Critical", "High"], "exceptions": []}
        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            (directory / "semgrep.status.json").write_text('{"completed":true}')
            (directory / "semgrep.generic.json").write_text(
                json.dumps(normalize("semgrep", raw))
            )
            findings, failures = evaluate(directory, ["semgrep"], policy)
            self.assertEqual(len(findings), 2)
            self.assertEqual(len(failures), 2)
            (directory / "semgrep.generic.json").write_text(
                json.dumps(normalize("semgrep", {"results": []}))
            )
            self.assertEqual(evaluate(directory, ["semgrep"], policy), ([], []))

    def test_empty_scan_is_reimported_into_same_test_and_closes_old_findings(self):
        requests = []

        class Response:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def send(request, **kwargs):
            requests.append(request)
            return Response()

        with tempfile.TemporaryDirectory() as temp, patch(
            "urllib.request.urlopen", side_effect=send
        ):
            path = pathlib.Path(temp) / "semgrep.generic.json"
            for findings in [
                [{"title": "SQL injection"}, {"title": "Unsafe eval"}],
                [],
            ]:
                path.write_text(json.dumps({"findings": findings}))
                upload(
                    "semgrep",
                    path,
                    "http://127.0.0.1:18080",
                    "test-token",
                    42,
                    "commit",
                    "main",
                    "run",
                )
        self.assertEqual(len(requests), 2)
        for request in requests:
            self.assertTrue(request.full_url.endswith("/api/v2/reimport-scan/"))
            body = request.data.decode()
            self.assertIn('name="test"\r\n\r\n42', body)
            self.assertIn('name="close_old_findings"\r\n\r\ntrue', body)
            self.assertIn('name="close_old_findings_product_scope"\r\n\r\nfalse', body)
        self.assertIn('"findings": []', requests[1].data.decode())

    def test_cli_report_scopes_cannot_target_each_others_tests(self):
        import os
        import runpy

        requests = []

        class Response:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def send(request, **kwargs):
            requests.append(request.data.decode())
            return Response()

        with tempfile.TemporaryDirectory() as temp:
            directory = pathlib.Path(temp)
            (directory / "semgrep.status.json").write_text('{"completed":true}')
            (directory / "semgrep.generic.json").write_text('{"findings":[]}')
            env = {
                "DOJO_URL": "http://127.0.0.1:18080",
                "DOJO_ALLOW_LOCAL_HTTP": "true",
                "DOJO_TOKEN": "test-token",
                "DOJO_TEST_IDS": json.dumps(
                    {"main": {"semgrep": 1}, "remediation": {"semgrep": 42}}
                ),
            }
            with patch.dict(os.environ, env), patch(
                "urllib.request.urlopen", side_effect=send
            ):
                for scope in ["remediation", "main"]:
                    with patch.object(
                        sys,
                        "argv",
                        [
                            "upload_findings.py",
                            "--reports",
                            temp,
                            "--tools",
                            "semgrep",
                            "--scope",
                            scope,
                        ],
                    ):
                        runpy.run_path(
                            str(ROOT / "scripts/upload_findings.py"),
                            run_name="__main__",
                        )
        self.assertIn('name="test"\r\n\r\n42', requests[0])
        self.assertIn('name="test"\r\n\r\n1', requests[1])
        self.assertNotIn('name="test"\r\n\r\n42', requests[1])

    def test_release_demo_extends_semgrep_without_changing_infrastructure_scan_scope(
        self,
    ):
        calls = []
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "security").mkdir()
            (root / "security/tools.lock.json").write_text(
                json.dumps(
                    {
                        "semgrep": {"image": "scanner:semgrep", "version": "test"},
                        "checkov": {"image": "scanner:checkov", "version": "test"},
                    }
                )
            )
            for name in scan.CHECKOV_POLICIES:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())

            class Result:
                returncode = 0

            def run(command, **kwargs):
                calls.append(command)
                report = (
                    {"results": []}
                    if "scanner:semgrep" in command
                    else {"results": {"failed_checks": [], "passed_checks": [
                        {"check_id": "CKV2_AKUPHE_1"}, {"check_id": "CKV2_AKUPHE_2"},
                    ]}}
                )
                kwargs["stdout"].write(json.dumps(report))
                return Result()

            with patch.object(scan, "ROOT", root), patch.object(
                scan.subprocess, "check_output",
                return_value="\0".join(scan.CHECKOV_POLICIES).encode()
            ), patch.object(scan.subprocess, "run", side_effect=run):
                self.assertTrue(scan.run("semgrep", include_remediation_demo=True))
                self.assertTrue(scan.run("checkov", include_remediation_demo=True))
        self.assertIn("security/demo/unsafe-search.ts", calls[0])
        self.assertIn("security/demo/unsafe-expression.ts", calls[0])
        self.assertIn("infra", calls[1])
        self.assertNotIn("security/demo", calls[1])


if __name__ == "__main__":
    unittest.main()
