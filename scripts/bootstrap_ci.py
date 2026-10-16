"""Create/reuse the dedicated state bucket and persist bootstrap state across CI runs."""

import argparse
import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOOT = ROOT / "infra/bootstrap"


def aws(*args, missing_ok=False):
    result = subprocess.run(
        ["aws", *args, "--output", "json"], text=True, capture_output=True, timeout=120
    )
    if result.returncode:
        if missing_ok and any(
            code in result.stderr
            for code in ("NoSuchBucket", "NoSuchKey", "(404)", "Not Found")
        ):
            return None
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def validate_state(state, bucket, repository):
    resources = [
        i["attributes"]
        for resource in state.get("resources", [])
        if resource["type"] == "aws_s3_bucket"
        for i in resource.get("instances", [])
    ]
    if len(resources) != 1 or resources[0].get("id") != bucket:
        raise ValueError("Bootstrap snapshot does not own the expected state bucket")
    if resources[0].get("tags", {}).get("Repository") != repository:
        raise ValueError("Bootstrap snapshot belongs to a different repository")


def tf(*args):
    subprocess.run(["terraform", "-chdir=" + str(BOOT), *args], check=True)


def bootstrap(account, repository):
    if not re.fullmatch(r"\d{12}", account) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise ValueError("Expected AWS account ID and GitHub owner/repository")
    if os.environ.get("GITHUB_REF", "refs/heads/main") != "refs/heads/main":
        raise ValueError("Infrastructure setup is restricted to main")
    if aws("sts", "get-caller-identity")["Account"] != account:
        raise ValueError("AWS identity does not match the selected account")
    bucket = "securetask-state-" + account
    exists = (
        aws(
            "s3api",
            "head-bucket",
            "--bucket",
            bucket,
            "--expected-bucket-owner",
            account,
            missing_ok=True,
        )
        is not None
    )
    state_path = BOOT / "terraform.tfstate"
    if exists:
        location = aws("s3api", "get-bucket-location", "--bucket", bucket)[
            "LocationConstraint"
        ]
        if location not in (None, "us-east-1"):
            raise ValueError("The dedicated state bucket must be in us-east-1")
        tags = {
            x["Key"]: x["Value"]
            for x in aws("s3api", "get-bucket-tagging", "--bucket", bucket)["TagSet"]
        }
        if tags.get("Project") != "securetask" or tags.get("Repository") != repository:
            raise ValueError(
                "Existing bucket is not owned by this project and repository; refusing to adopt it"
            )
        snapshot = aws(
            "s3api",
            "get-object",
            "--bucket",
            bucket,
            "--key",
            "bootstrap/terraform.tfstate",
            str(state_path),
            missing_ok=True,
        )
        if snapshot is None:
            # Recover the known, tagged bucket if a previous runner stopped before its first snapshot.
            state_path.unlink(missing_ok=True)
    else:
        state_path.unlink(missing_ok=True)
    if state_path.exists():
        validate_state(json.loads(state_path.read_text()), bucket, repository)
    (BOOT / "terraform.auto.tfvars.json").write_text(
        json.dumps({"state_bucket": bucket, "github_repository": repository})
    )
    tf("init", "-input=false")
    if exists and not state_path.exists():
        # Only the bucket is imported. The configuration recreates the project's protections.
        tf("import", "-input=false", "aws_s3_bucket.state", bucket)
    try:
        tf("apply", "-input=false", "-auto-approve")
    finally:
        # Save even after a partial apply: an ephemeral runner is not a durable state store.
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if any(
                res["type"] == "aws_s3_bucket" and res.get("instances")
                for res in state.get("resources", [])
            ):
                validate_state(state, bucket, repository)
                aws(
                    "s3api",
                    "put-object",
                    "--bucket",
                    bucket,
                    "--key",
                    "bootstrap/terraform.tfstate",
                    "--body",
                    str(state_path),
                    "--server-side-encryption",
                    "AES256",
                )
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as f:
            f.write("bucket=" + bucket + "\n")
    print("State bucket ready: " + bucket)
    return bucket


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"
    bootstrap(args.account, args.repository)
