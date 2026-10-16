import contextlib
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from normalize import normalize, validate_checkov_policies
from policy import evaluate
import scan


class InfrastructurePolicyTests(unittest.TestCase):
    def test_missing_or_skipped_policies_cannot_be_reported_as_clean(self):
        expected = ["CKV2_AKUPHE_1", "CKV2_AKUPHE_2"]
        for report in [
            {"results": {"passed_checks": [], "failed_checks": []}},
            {"results": {"skipped_checks": [{"check_id": expected[0]}]}},
            {"results": {"passed_checks": [{"check_id": expected[0]}]}},
        ]:
            with self.subTest(report=report), self.assertRaises(ValueError):
                validate_checkov_policies(report, expected)
        validate_checkov_policies({"results": {"passed_checks": [
            {"check_id": rule} for rule in expected
        ]}}, expected)

    def test_either_infrastructure_violation_blocks_until_both_are_corrected(self):
        checks = [
            {"check_id": "CKV2_AKUPHE_1", "check_name": "Protect S3 access",
             "resource": "aws_s3_bucket_public_access_block.state",
             "file_path": "/bootstrap/main.tf", "file_line_range": [40, 50]},
            {"check_id": "CKV2_AKUPHE_2", "check_name": "Encrypt RDS storage",
             "resource": "aws_db_instance.main",
             "file_path": "/platform/main.tf", "file_line_range": [135, 160]},
        ]
        policy = {"block_severities": ["Critical", "High"], "exceptions": []}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "checkov.status.json").write_text('{"completed":true}')
            for remaining in [checks, checks[1:], []]:
                raw = {"results": {"failed_checks": remaining}}
                (directory / "checkov.generic.json").write_text(
                    json.dumps(normalize("checkov", raw))
                )
                findings, failures = evaluate(directory, ["checkov"], policy)
                self.assertEqual(len(findings), len(remaining))
                self.assertEqual(len(failures), len(remaining))
                self.assertTrue(all(f["severity"] == "High" for _, f in findings))

    def test_missing_custom_policy_blocks_instead_of_silently_skipping(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "security").mkdir()
            (root / "security/tools.lock.json").write_text(json.dumps({
                "checkov": {"image": "scanner:test", "version": "test"},
            }))
            with patch.object(scan, "ROOT", root), patch.object(
                scan.subprocess, "check_output", return_value=b""
            ), patch.object(scan.subprocess, "run") as run:
                self.assertFalse(scan.run("checkov"))
                run.assert_not_called()
            status = json.loads((root / "reports/checkov.status.json").read_text())
            self.assertFalse(status["completed"])

    def test_plan_scanner_error_cannot_produce_successful_policy_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "security/checkov").mkdir(parents=True)
            (root / "security/tools.lock.json").write_text(json.dumps({
                "checkov": {"image": "scanner:test", "version": "test"},
            }))
            (root / "reports-plan.json").write_text('{}')
            with contextlib.chdir(root), patch(
                "subprocess.run", return_value=SimpleNamespace(returncode=2)
            ) as run:
                with self.assertRaises(SystemExit) as error:
                    runpy.run_path(str(ROOT / "scripts/scan-plan.py"), run_name="__main__")
            self.assertNotEqual(error.exception.code, 0)
            status = json.loads((root / "reports/checkov.status.json").read_text())
            self.assertFalse(status["completed"])
            self.assertIn("--external-checks-dir", run.call_args.args[0])
            self.assertIn(str((root / "security/checkov").resolve()) + ":/checks:ro", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
