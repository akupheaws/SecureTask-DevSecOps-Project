import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import decommission as dc


class DecommissionTests(unittest.TestCase):
    def test_wrong_confirmation_and_bucket_fail_before_aws(self):
        with patch.object(dc, "aws") as aws:
            with self.assertRaises(ValueError):
                dc.guard("123456789012", "securetask-state-123456789012", "destroy")
            with self.assertRaises(ValueError):
                dc.guard("123456789012", "unrelated-bucket", "DESTROY securetask")
            aws.assert_not_called()

    def test_wrong_account_and_branch_are_rejected(self):
        with patch.dict("os.environ", {"GITHUB_REF": "refs/heads/main"}), patch.object(
            dc, "aws", return_value={"Account": "999999999999"}
        ):
            with self.assertRaises(ValueError):
                dc.guard(
                    "123456789012",
                    "securetask-state-123456789012",
                    "DESTROY securetask",
                )
        with patch.dict(
            "os.environ", {"GITHUB_REF": "refs/heads/feature"}
        ), patch.object(dc, "aws") as aws:
            with self.assertRaises(ValueError):
                dc.guard(
                    "123456789012",
                    "securetask-state-123456789012",
                    "DESTROY securetask",
                )
            aws.assert_not_called()

    def test_state_changed_since_approval_aborts(self):
        approved = {
            "account": "123456789012",
            "bucket": "securetask-state-123456789012",
            "repository": "owner/repo",
            "states": {"platform": {"sha256": "old"}},
        }
        with self.assertRaises(ValueError):
            dc.verify_approval(
                approved,
                {"platform": {"sha256": "new"}},
                approved["account"],
                approved["bucket"],
                approved["repository"],
            )
        dc.verify_approval(
            approved,
            approved["states"],
            approved["account"],
            approved["bucket"],
            approved["repository"],
        )

    def test_destroy_inventory_rejects_creation(self):
        plan = {
            "resource_changes": [
                {
                    "mode": "managed",
                    "address": "aws_s3_bucket.state",
                    "type": "aws_s3_bucket",
                    "change": {"actions": ["create"], "before": None},
                }
            ]
        }
        with self.assertRaises(ValueError):
            dc.destroy_inventory(plan)

    def test_prepare_only_changes_deletion_flags(self):
        change = {
            "mode": "managed",
            "type": "aws_db_instance",
            "change": {
                "actions": ["update"],
                "before": {
                    "identifier": "securetask-staging",
                    "deletion_protection": True,
                },
                "after": {
                    "identifier": "securetask-staging",
                    "deletion_protection": False,
                },
            },
        }
        dc.validate_preparation({"resource_changes": [change]})
        change["change"]["after"]["identifier"] = "other-database"
        with self.assertRaises(ValueError):
            dc.validate_preparation({"resource_changes": [change]})
        change["change"]["actions"] = ["create"]
        with self.assertRaises(ValueError):
            dc.validate_preparation({"resource_changes": [change]})

    def test_all_state_versions_and_delete_markers_removed_and_errors_block(self):
        responses = [
            {
                "Versions": [{"Key": "platform/state", "VersionId": "v1"}],
                "DeleteMarkers": [{"Key": "platform/state", "VersionId": "v2"}],
            },
            {},
            {},
        ]
        with patch.object(dc, "aws", side_effect=responses) as aws:
            dc.empty_state_bucket("project-bucket")
            request = json.loads(aws.call_args_list[1].args[-1])
            self.assertEqual(len(request["Objects"]), 2)
        with patch.object(
            dc, "aws", side_effect=[responses[0], {"Errors": ["denied"]}]
        ), self.assertRaises(RuntimeError):
            dc.empty_state_bucket("project-bucket")

    def test_task_definition_cleanup_uses_exact_families(self):
        calls = []

        def aws(*args, **kwargs):
            calls.append(args)
            if args[:2] == ("rds", "describe-db-snapshots"):
                return {
                    "DBSnapshots": [
                        {
                            "DBInstanceIdentifier": "unrelated",
                            "DBSnapshotIdentifier": "keep",
                        }
                    ]
                }
            if args[:2] == ("rds", "describe-db-instance-automated-backups"):
                return {"DBInstanceAutomatedBackups": []}
            if args[:2] == ("ecs", "list-task-definitions"):
                family = args[3]
                return (
                    {
                        "taskDefinitionArns": [
                            f"arn:aws:ecs:us-east-1:123456789012:task-definition/{family}:2"
                        ]
                    }
                    if args[-1] == "ACTIVE"
                    else {"taskDefinitionArns": []}
                )
            return {}

        with patch.object(dc, "aws", side_effect=aws):
            dc.remove_residue(["securetask-production", "securetask-staging"])
        queries = [x[3] for x in calls if x[:2] == ("ecs", "list-task-definitions")]
        self.assertEqual(set(queries), {"securetask-production", "securetask-staging"})
        self.assertFalse(any(x[:2] == ("rds", "delete-db-snapshot") for x in calls))

    def test_verification_does_not_report_success_with_remaining_resources(self):
        with patch.object(
            dc, "remaining_project_resources", return_value={"databases": 1}
        ), patch.object(dc.time, "sleep"):
            with self.assertRaises(RuntimeError):
                dc.verify_removed({}, "project-bucket")
        with patch.object(
            dc,
            "remaining_project_resources",
            side_effect=[{"databases": 1}, {"databases": 0}],
        ), patch.object(dc.time, "sleep"):
            self.assertEqual(dc.verify_removed({}, "project-bucket"), {"databases": 0})

    def test_destroy_order_keeps_bootstrap_until_last(self):
        events = []
        resource = {
            "address": "aws_ecr_repository.app",
            "type": "aws_ecr_repository",
            "id": "securetask",
        }
        states = {s: {"resources": [resource]} for s in dc.SCOPES}
        plan = {
            "resource_changes": [
                {
                    "mode": "managed",
                    "address": resource["address"],
                    "type": resource["type"],
                    "change": {"actions": ["delete"], "before": {"id": "securetask"}},
                }
            ]
        }

        def tf(directory, *args, **kwargs):
            if args[0] == "show":
                return json.dumps(
                    {"resource_changes": []} if args[-1] == "prepare.tfplan" else plan
                )
            if args[0] == "apply":
                events.append((directory.name, args[-1]))

        with tempfile.TemporaryDirectory() as temp:
            work = pathlib.Path(temp)
            for scope in dc.SCOPES:
                (work / scope).mkdir()
            with patch.object(dc, "WORK", work), patch.object(
                dc, "tf", side_effect=tf
            ), patch.object(
                dc,
                "remove_residue",
                side_effect=lambda _: events.append(("residue", "clean")),
            ), patch.object(
                dc,
                "empty_state_bucket",
                side_effect=lambda _: events.append(("bucket", "empty")),
            ):
                dc.destroy(states, "project-bucket")
        self.assertEqual(
            events,
            [
                ("production", "destroy.tfplan"),
                ("staging", "destroy.tfplan"),
                ("platform", "prepare.tfplan"),
                ("platform", "destroy.tfplan"),
                ("residue", "clean"),
                ("bucket", "empty"),
                ("bootstrap", "destroy.tfplan"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
