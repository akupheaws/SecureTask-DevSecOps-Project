"""Review and destroy only this project's Terraform roots; never called automatically."""

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import time

from bootstrap_ci import validate_state

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = ROOT / "activation" / "decommission"
ZERO_DIGEST = "sha256:" + "0" * 64
SCOPES = ("production", "staging", "platform", "bootstrap")
PREPARE_FIELDS = {
    "aws_db_instance": {"deletion_protection", "skip_final_snapshot"},
    "aws_lb": {"enable_deletion_protection"},
    "aws_ecr_repository": {"force_delete"},
}


def aws(*args, missing_ok=False, timeout=120):
    result = subprocess.run(
        ["aws", *args, "--output", "json"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        if missing_ok and any(
            code in result.stderr
            for code in (
                "NoSuchKey",
                "ResourceNotFoundException",
                "DBSnapshotNotFound",
                "DBInstanceNotFound",
                "NoSuchBucket",
            )
        ):
            return None
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def guard(account, bucket, confirmation=None):
    if not re.fullmatch(r"\d{12}", account) or bucket != "securetask-state-" + account:
        raise ValueError(
            "Expected a 12-digit account and its dedicated securetask-state bucket"
        )
    if os.environ.get("GITHUB_REF", "refs/heads/main") != "refs/heads/main":
        raise ValueError("Decommissioning is restricted to main")
    if confirmation is not None and confirmation != "DESTROY securetask":
        raise ValueError(
            "Type exactly DESTROY securetask to acknowledge permanent data deletion"
        )
    identity = aws("sts", "get-caller-identity")
    if identity["Account"] != account:
        raise ValueError(
            "Authenticated AWS account does not match the explicitly selected account"
        )
    return identity


def tf(directory, *args, capture=False):
    command = ["terraform", "-chdir=" + str(directory), *args]
    if capture:
        return subprocess.check_output(command, text=True)
    subprocess.run(command, check=True)


def destroy_inventory(plan):
    inventory = []
    for change in plan.get("resource_changes", []):
        if change["mode"] != "managed":
            continue
        actions = change["change"]["actions"]
        if actions == ["no-op"]:
            continue
        if actions != ["delete"]:
            raise ValueError(
                "Destroy plan contains a non-delete action: " + change["address"]
            )
        before = change["change"]["before"] or {}
        inventory.append(
            {
                "address": change["address"],
                "type": change["type"],
                "id": before.get("id"),
            }
        )
    return sorted(inventory, key=lambda x: x["address"])


def validate_preparation(plan):
    for change in plan.get("resource_changes", []):
        if change["mode"] != "managed" or change["change"]["actions"] == ["no-op"]:
            continue
        if change["type"] not in PREPARE_FIELDS or change["change"]["actions"] != [
            "update"
        ]:
            raise ValueError(
                "Cleanup preparation would create/delete or modify an unexpected resource"
            )
        before, after = change["change"]["before"], change["change"]["after"]
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        if not changed <= PREPARE_FIELDS[change["type"]]:
            raise ValueError(
                "Cleanup preparation changes more than deletion settings: "
                + ", ".join(sorted(changed))
            )


def fetch_state(bucket, key, path, required=False):
    result = aws(
        "s3api",
        "get-object",
        "--bucket",
        bucket,
        "--key",
        key,
        str(path),
        missing_ok=True,
    )
    if result is None:
        if required:
            raise ValueError(
                "Missing bootstrap state snapshot. Check the Provision AWS infrastructure workflow and its bootstrap step."
            )
        return None
    return json.loads(path.read_text())


def prepare_roots(bucket, repository):
    WORK.mkdir(parents=True, exist_ok=True)
    states = {}
    for scope in SCOPES:
        source = (
            ROOT
            / "infra"
            / ("application" if scope in ("production", "staging") else scope)
        )
        directory = WORK / scope
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir()
        for file in source.iterdir():
            if file.suffix == ".tf" or file.name == ".terraform.lock.hcl":
                shutil.copy2(file, directory / file.name)
        if scope == "platform":
            shutil.copy2(source / "dojo-user-data.sh", directory / "dojo-user-data.sh")
            # templatefile references ../../dojo from the temporary module directory.
            shutil.copytree(ROOT / "dojo", WORK.parent / "dojo", dirs_exist_ok=True)
        key = (
            "application/" + scope if scope in ("production", "staging") else scope
        ) + "/terraform.tfstate"
        state_path = directory / "downloaded-state.json"
        state = fetch_state(bucket, key, state_path, required=scope == "bootstrap")
        states[scope] = {
            "key": key,
            "sha256": (
                hashlib.sha256(state_path.read_bytes()).hexdigest()
                if state is not None
                else None
            ),
        }
        if scope == "bootstrap":
            if state is None:
                raise ValueError("Missing bootstrap state")
            validate_state(state, bucket, repository)
            shutil.copy2(state_path, directory / "terraform.tfstate")
            config = {
                "state_bucket": bucket,
                "github_repository": repository,
            }
            tf(directory, "init", "-input=false")
        else:
            if state is None:
                continue  # A service need not have been deployed yet.
            config = (
                {
                    "state_bucket": bucket,
                    "environment": scope,
                    "image_digest": ZERO_DIGEST,
                    "allow_http_demo": True,
                }
                if scope in ("production", "staging")
                else {
                    "github_repository": repository,
                    "allow_http_demo": True,
                }
            )
            tf(
                directory,
                "init",
                "-input=false",
                "-reconfigure",
                "-backend-config=bucket=" + bucket,
                "-backend-config=key=" + key,
                "-backend-config=region=us-east-1",
                "-backend-config=encrypt=true",
                "-backend-config=use_lockfile=true",
            )
        config["region"] = "us-east-1"
        (directory / "terraform.auto.tfvars.json").write_text(json.dumps(config))
        tf(directory, "plan", "-destroy", "-input=false", "-out=destroy.tfplan")
        plan = json.loads(
            tf(directory, "show", "-json", "destroy.tfplan", capture=True)
        )
        states[scope]["resources"] = destroy_inventory(plan)
        if scope == "platform":
            states[scope]["databases"] = [
                c["change"]["before"]["identifier"]
                for c in plan.get("resource_changes", [])
                if c["type"] == "aws_db_instance" and c["mode"] == "managed"
            ]
        if scope == "bootstrap":
            states[scope]["role_names"] = [
                i["attributes"]["name"]
                for r in state.get("resources", [])
                if r["type"] == "aws_iam_role"
                for i in r.get("instances", [])
            ]
    return states


def verify_approval(approved, current, account, bucket, repository):
    if any(
        approved.get(k) != v
        for k, v in {
            "account": account,
            "bucket": bucket,
            "repository": repository,
        }.items()
    ):
        raise ValueError("Approval manifest does not match this deployment")
    if approved["states"] != current:
        raise ValueError(
            "Terraform state or destroy inventory changed after review. Start a new workflow run."
        )


def empty_state_bucket(bucket):
    listing = aws("s3api", "list-object-versions", "--bucket", bucket)
    objects = [
        {"Key": x["Key"], "VersionId": x["VersionId"]}
        for kind in ("Versions", "DeleteMarkers")
        for x in listing.get(kind, [])
    ]
    for start in range(0, len(objects), 1000):
        result = aws(
            "s3api",
            "delete-objects",
            "--bucket",
            bucket,
            "--delete",
            json.dumps({"Objects": objects[start : start + 1000], "Quiet": True}),
        )
        if result.get("Errors"):
            raise RuntimeError("Failed to remove some state object versions")
    if aws("s3api", "list-multipart-uploads", "--bucket", bucket).get("Uploads"):
        raise RuntimeError(
            "State bucket has unfinished uploads; resolve them before deleting bootstrap"
        )


def remove_residue(databases):
    for database in databases:
        if database not in ("securetask-staging", "securetask-production"):
            raise ValueError("Refusing to clean an unexpected database name")
        for suffix in ("postgresql", "upgrade"):
            aws(
                "logs",
                "delete-log-group",
                "--log-group-name",
                "/aws/rds/instance/" + database + "/" + suffix,
                missing_ok=True,
            )
    for snapshot in aws("rds", "describe-db-snapshots", "--snapshot-type", "manual")[
        "DBSnapshots"
    ]:
        if snapshot["DBInstanceIdentifier"] in databases:
            aws(
                "rds",
                "delete-db-snapshot",
                "--db-snapshot-identifier",
                snapshot["DBSnapshotIdentifier"],
            )
            aws(
                "rds",
                "wait",
                "db-snapshot-deleted",
                "--db-snapshot-identifier",
                snapshot["DBSnapshotIdentifier"],
                timeout=1800,
            )
    for backup in aws("rds", "describe-db-instance-automated-backups")[
        "DBInstanceAutomatedBackups"
    ]:
        if (
            backup["DBInstanceIdentifier"] in databases
            and backup["Status"] == "retained"
        ):
            aws(
                "rds",
                "delete-db-instance-automated-backup",
                "--dbi-resource-id",
                backup["DbiResourceId"],
            )
    for secret in ("securetask-dojo-admin", "securetask-dojo-integration"):
        aws(
            "secretsmanager",
            "delete-secret",
            "--secret-id",
            secret,
            "--force-delete-without-recovery",
            missing_ok=True,
        )
    for family in ("securetask-staging", "securetask-production"):
        for status in ("ACTIVE", "INACTIVE"):
            for arn in aws(
                "ecs",
                "list-task-definitions",
                "--family-prefix",
                family,
                "--status",
                status,
            )["taskDefinitionArns"]:
                if arn.split("/")[-1].rsplit(":", 1)[0] != family:
                    raise ValueError("Unexpected task definition family")
                if status == "ACTIVE":
                    aws("ecs", "deregister-task-definition", "--task-definition", arn)
                result = aws(
                    "ecs", "delete-task-definitions", "--task-definitions", arn
                )
                if result.get("failures"):
                    raise RuntimeError("Task-definition deletion failed")


def destroy(states, bucket):
    for scope in ("production", "staging"):
        if states[scope].get("resources"):
            tf(WORK / scope, "apply", "-input=false", "destroy.tfplan")
    platform = WORK / "platform"
    if states["platform"].get("resources"):
        (platform / "cleanup_override.tf").write_text(
            'resource "aws_db_instance" "main" {\n deletion_protection = false\n skip_final_snapshot = true\n}\nresource "aws_lb" "main" {\n enable_deletion_protection = false\n}\nresource "aws_lb" "staging" {\n enable_deletion_protection = false\n}\nresource "aws_ecr_repository" "app" {\n force_delete = true\n}\n'
        )
        # Target only resources already reviewed; never recreate a deleted resource on a retry.
        targets = [
            r["address"]
            for r in states["platform"]["resources"]
            if r["type"] in PREPARE_FIELDS
        ]
        if targets:
            tf(
                platform,
                "plan",
                "-input=false",
                "-out=prepare.tfplan",
                *["-target=" + address for address in targets],
            )
            validate_preparation(
                json.loads(
                    tf(platform, "show", "-json", "prepare.tfplan", capture=True)
                )
            )
            tf(platform, "apply", "-input=false", "prepare.tfplan")
        tf(platform, "plan", "-destroy", "-input=false", "-out=destroy.tfplan")
        if (
            destroy_inventory(
                json.loads(
                    tf(platform, "show", "-json", "destroy.tfplan", capture=True)
                )
            )
            != states["platform"]["resources"]
        ):
            raise ValueError(
                "Platform destroy inventory changed during deletion preparation"
            )
        tf(platform, "apply", "-input=false", "destroy.tfplan")
    remove_residue(["securetask-production", "securetask-staging"])
    # Bootstrap uses a local state copy: deleting its S3 bucket cannot break the final state write.
    # Repository-secret AWS credentials remain valid when project roles and the bucket are deleted.
    empty_state_bucket(bucket)
    if states["bootstrap"].get("resources"):
        tf(WORK / "bootstrap", "apply", "-input=false", "destroy.tfplan")


def remaining_project_resources(states, bucket):
    databases = {"securetask-production", "securetask-staging"}
    managed = [r for scope in SCOPES for r in states[scope].get("resources", [])]
    ids = lambda kind: {r["id"] for r in managed if r["type"] == kind}
    checks = {
        "databases": sum(
            x["DBInstanceIdentifier"] in databases
            for x in aws("rds", "describe-db-instances")["DBInstances"]
        ),
        "snapshots": sum(
            x["DBInstanceIdentifier"] in databases
            for x in aws("rds", "describe-db-snapshots")["DBSnapshots"]
        ),
        "retained_backups": sum(
            x["DBInstanceIdentifier"] in databases
            for x in aws("rds", "describe-db-instance-automated-backups")[
                "DBInstanceAutomatedBackups"
            ]
        ),
        "registry": sum(
            x["repositoryName"] == "securetask"
            for x in aws("ecr", "describe-repositories")["repositories"]
        ),
        "state_bucket": sum(
            x["Name"] == bucket for x in aws("s3api", "list-buckets")["Buckets"]
        ),
        "load_balancers": sum(
            x["LoadBalancerArn"] in ids("aws_lb")
            for x in aws("elbv2", "describe-load-balancers")["LoadBalancers"]
        ),
        "iam_roles": sum(
            x["RoleName"] in ids("aws_iam_role")
            for x in aws("iam", "list-roles")["Roles"]
        ),
        "boundary": sum(
            x["PolicyName"] == "securetask-runtime-boundary"
            for x in aws("iam", "list-policies", "--scope", "Local")["Policies"]
        ),
        "dojo_secrets": sum(
            x["Name"] in {"securetask-dojo-admin", "securetask-dojo-integration"}
            for x in aws("secretsmanager", "list-secrets")["SecretList"]
        ),
        "ecs_cluster": sum(
            x["status"] == "ACTIVE"
            for x in aws("ecs", "describe-clusters", "--clusters", "securetask")[
                "clusters"
            ]
        ),
        "task_definitions": sum(
            len(
                aws(
                    "ecs",
                    "list-task-definitions",
                    "--family-prefix",
                    family,
                    "--status",
                    "ACTIVE",
                )["taskDefinitionArns"]
            )
            for family in databases
        ),
        "logs": sum(
            len(
                aws("logs", "describe-log-groups", "--log-group-name-prefix", prefix)[
                    "logGroups"
                ]
            )
            for prefix in ("/ecs/securetask", "/aws/rds/instance/securetask-")
        ),
        "vpcs": sum(
            x["VpcId"] in ids("aws_vpc") for x in aws("ec2", "describe-vpcs")["Vpcs"]
        ),
        "elastic_ips": sum(
            x.get("AllocationId") in ids("aws_eip")
            for x in aws("ec2", "describe-addresses")["Addresses"]
        ),
        "nat_gateways": sum(
            x["NatGatewayId"] in ids("aws_nat_gateway") and x["State"] != "deleted"
            for x in aws("ec2", "describe-nat-gateways")["NatGateways"]
        ),
    }
    for instance in ids("aws_instance"):
        reservations = aws("ec2", "describe-instances", "--instance-ids", instance)[
            "Reservations"
        ]
        checks["instance:" + instance] = sum(
            i["State"]["Name"] != "terminated"
            for r in reservations
            for i in r["Instances"]
        )
    return checks


def verify_removed(states, bucket):
    for attempt in range(7):
        checks = remaining_project_resources(states, bucket)
        if not any(checks.values()):
            return checks
        if attempt < 6:
            time.sleep(10)
    raise RuntimeError(
        "AWS verification found remaining project resources: " + json.dumps(checks)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "destroy"])
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--confirmation", required=True)
    parser.add_argument("--manifest", default="reports/decommission/manifest.json")
    args = parser.parse_args()
    os.umask(0o077)
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"
    identity = guard(args.account, args.bucket, args.confirmation)
    states = prepare_roots(args.bucket, args.repository)
    path = pathlib.Path(args.manifest)
    if args.mode == "plan":
        manifest = {
            "account": args.account,
            "bucket": args.bucket,
            "repository": args.repository,
            "states": states,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, indent=2))
        lines = [
            "# Decommission plan",
            "",
            "Account: " + args.account,
            "Region: us-east-1",
            "",
            "Permanent deletion includes database data, images, Dojo data, retained snapshots/backups, logs, and ALL state versions.",
            "Provisioning IAM user, external credentials, AWS service-linked roles, and GitHub repository remain.",
            "",
        ]
        for scope in SCOPES:
            resources = states[scope].get("resources", [])
            lines.append(f"## {scope}: {len(resources)} resources")
            lines.extend(
                "- `" + r["address"] + "` — `" + str(r["id"]) + "`" for r in resources
            )
            lines.append("")
        summary = "\n".join(lines)
        (path.parent / "review.md").write_text(summary)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
                output.write(summary)
    else:
        verify_approval(
            json.loads(path.read_text()),
            states,
            args.account,
            args.bucket,
            args.repository,
        )
        caller_role = identity["Arn"].split(":assumed-role/")[-1].split("/")[0]
        if caller_role in states["bootstrap"].get("role_names", []):
            raise ValueError(
                "Cleanup role must be managed outside the project bootstrap"
            )
        destroy(states, args.bucket)
        checks = verify_removed(states, args.bucket)
        path.with_name("result.json").write_text(
            json.dumps(
                {
                    "completed": True,
                    "account": args.account,
                    "region": "us-east-1",
                    "destroyed_roots": list(SCOPES),
                    "remaining_resources": checks,
                },
                indent=2,
            )
        )
        print(
            "All project Terraform roots destroyed; residual project data cleanup completed."
        )


if __name__ == "__main__":
    main()
