import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


bc = module("bootstrap_ci", "bootstrap_ci.py")
gc = module("configure_github", "configure-github.py")
wd = module("wait_dojo", "wait-dojo.py")
ACCOUNT = "123456789012"
BUCKET = "securetask-state-" + ACCOUNT
REPOSITORY = "owner/repo"


def state():
    return {
        "resources": [
            {
                "type": "aws_s3_bucket",
                "instances": [
                    {"attributes": {"id": BUCKET, "tags": {"Repository": REPOSITORY}}}
                ],
            }
        ]
    }


class BootstrapTests(unittest.TestCase):
    def test_account_or_branch_mismatch_prevents_mutations(self):
        with patch.object(bc, "aws", return_value={"Account": "999999999999"}) as aws:
            with self.assertRaises(ValueError):
                bc.bootstrap(ACCOUNT, REPOSITORY)
            self.assertEqual(aws.call_count, 1)
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/feature"}), patch.object(
            bc, "aws"
        ) as aws:
            with self.assertRaises(ValueError):
                bc.bootstrap(ACCOUNT, REPOSITORY)
            aws.assert_not_called()

    def test_snapshot_must_own_bucket_and_repository(self):
        bc.validate_state(state(), BUCKET, REPOSITORY)
        with self.assertRaises(ValueError):
            bc.validate_state(state(), "another-bucket", REPOSITORY)
        with self.assertRaises(ValueError):
            bc.validate_state(state(), BUCKET, "another/repo")

    def run_bootstrap(self, existing=False, snapshot=True, fail_apply=False):
        events = []
        with tempfile.TemporaryDirectory() as temp:
            boot = Path(temp)

            def aws(*args, **kwargs):
                events.append(("aws", args[:2]))
                if args[:2] == ("sts", "get-caller-identity"):
                    return {"Account": ACCOUNT}
                if args[:2] == ("s3api", "head-bucket"):
                    return {} if existing else None
                if args[:2] == ("s3api", "get-bucket-location"):
                    return {"LocationConstraint": None}
                if args[:2] == ("s3api", "get-bucket-tagging"):
                    return {
                        "TagSet": [
                            {"Key": "Project", "Value": "securetask"},
                            {"Key": "Repository", "Value": REPOSITORY},
                        ]
                    }
                if args[:2] == ("s3api", "get-object"):
                    if snapshot:
                        Path(args[-1]).write_text(json.dumps(state()))
                        return {}
                    return None
                return {}

            def tf(*args):
                events.append(("tf", args[0]))
                if args[0] in ("apply", "import"):
                    (boot / "terraform.tfstate").write_text(json.dumps(state()))
                if fail_apply and args[0] == "apply":
                    raise RuntimeError("partial apply")

            with patch.object(bc, "BOOT", boot), patch.object(
                bc, "aws", side_effect=aws
            ), patch.object(bc, "tf", side_effect=tf), patch.dict(
                os.environ, {"GITHUB_REF": "refs/heads/main"}
            ):
                if fail_apply:
                    with self.assertRaises(RuntimeError):
                        bc.bootstrap(ACCOUNT, REPOSITORY)
                else:
                    self.assertEqual(bc.bootstrap(ACCOUNT, REPOSITORY), BUCKET)
        return events

    def test_missing_bucket_is_created_and_snapshot_saved(self):
        events = self.run_bootstrap()
        self.assertNotIn(("tf", "import"), events)
        self.assertEqual(events[-1], ("aws", ("s3api", "put-object")))

    def test_existing_bucket_restores_snapshot_without_import(self):
        events = self.run_bootstrap(existing=True)
        self.assertIn(("aws", ("s3api", "get-object")), events)
        self.assertNotIn(("tf", "import"), events)

    def test_tagged_bucket_with_missing_snapshot_is_recovered(self):
        self.assertIn(
            ("tf", "import"), self.run_bootstrap(existing=True, snapshot=False)
        )

    def test_partial_apply_persists_recovery_state(self):
        self.assertEqual(
            self.run_bootstrap(fail_apply=True)[-1], ("aws", ("s3api", "put-object"))
        )

    def test_unrelated_existing_bucket_is_not_adopted(self):
        def aws(*args, **kwargs):
            if args[:2] == ("sts", "get-caller-identity"):
                return {"Account": ACCOUNT}
            if args[:2] == ("s3api", "get-bucket-location"):
                return {"LocationConstraint": None}
            if args[:2] == ("s3api", "get-bucket-tagging"):
                return {"TagSet": [{"Key": "Repository", "Value": "someone/else"}]}
            return {}

        with patch.object(bc, "aws", side_effect=aws), patch.object(bc, "tf") as tf:
            with self.assertRaises(ValueError):
                bc.bootstrap(ACCOUNT, REPOSITORY)
            tf.assert_not_called()

    def test_github_api_failure_does_not_silently_skip_gate_configuration(self):
        with patch.object(gc, "gh", side_effect=RuntimeError("403 Forbidden")):
            with self.assertRaises(RuntimeError):
                gc.configure_environments(REPOSITORY, "owner")

    def test_all_review_gates_are_created(self):
        calls = []

        def gh(*args, **kwargs):
            calls.append((args, kwargs))
            if args == ("api", "repos/" + REPOSITORY):
                return '{"default_branch":"main","private":false}'
            if args == ("api", "users/owner"):
                return '{"id":1}'
            if args[-1].endswith("/deployment-branch-policies"):
                return '{"branch_policies":[]}'
            return "{}"

        with patch.object(gc, "gh", side_effect=gh):
            gc.configure_environments(REPOSITORY, "owner")
        reviewed = [
            a[-3].split("/")[-1] for a, kw in calls if "reviewers" in kw.get("data", {})
        ]
        self.assertEqual(set(reviewed), gc.REVIEWED)

    def test_failed_dojo_setup_cannot_be_reported_ready(self):
        class Result:
            returncode = 0
            stdout = '{"Status":"Failed"}'

        with patch.object(wd.subprocess, "run", return_value=Result()):
            with self.assertRaises(RuntimeError):
                wd.wait_setup("i-123", "command")


if __name__ == "__main__":
    unittest.main()
