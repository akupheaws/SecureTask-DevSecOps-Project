"""Configure repository approval gates and publish Terraform outputs from Actions."""

import argparse
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENVIRONMENTS = [
    "security-review",
    "security-publish",
    "security-reporting",
    "staging",
    "production",
    "demo-review",
    "infrastructure-plan",
    "infrastructure",
    "decommission",
]
REVIEWED = {
    "security-review",
    "production",
    "demo-review",
    "infrastructure",
    "decommission",
}


def gh(*args, data=None):
    result = subprocess.run(
        ["gh", *args],
        input=json.dumps(data) if data is not None else None,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        # GitHub CLI errors contain endpoint details, never print token-bearing environment values.
        raise RuntimeError(result.stderr)
    return result.stdout


def configure_environments(repository, reviewer):
    info = json.loads(gh("api", "repos/" + repository))
    if info["default_branch"] != "main":
        raise ValueError(
            "Set the repository default branch to main before provisioning"
        )
    if info.get("private"):
        raise ValueError(
            "This tutorial expects a public repository for environment approval gates"
        )
    user_id = json.loads(gh("api", "users/" + reviewer))["id"]
    for environment in ENVIRONMENTS:
        data = {
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            }
        }
        if environment in REVIEWED:
            data.update(
                {
                    "reviewers": [{"type": "User", "id": user_id}],
                    "prevent_self_review": False,
                }
            )
        gh(
            "api",
            "--method",
            "PUT",
            f"repos/{repository}/environments/{environment}",
            "--input",
            "-",
            data=data,
        )
        policies = json.loads(
            gh(
                "api",
                f"repos/{repository}/environments/{environment}/deployment-branch-policies",
            )
        )
        for policy in policies["branch_policies"]:
            if policy["name"] != "main" or policy.get("type") != "branch":
                raise ValueError(
                    "Unexpected deployment branch policy; keep only main in "
                    + environment
                )
        if not policies["branch_policies"]:
            gh(
                "api",
                "--method",
                "POST",
                f"repos/{repository}/environments/{environment}/deployment-branch-policies",
                "--input",
                "-",
                data={"name": "main", "type": "branch"},
            )
    print("Repository approval environments configured for main")


def publish_settings(repository, bucket):
    outputs = json.loads(
        subprocess.check_output(
            ["terraform", "-chdir=" + str(ROOT / "infra/platform"), "output", "-json"]
        )
    )

    def val(key):
        return outputs[key]["value"]

    settings = {
        "ECR_REPOSITORY_URL": val("repository_url"),
        "ECS_CLUSTER": val("cluster_name"),
        "DOJO_INSTANCE_ID": val("dojo_instance_id"),
        "DOJO_INTEGRATION_SECRET_ARN": val("dojo_integration_secret_arn"),
        "DOJO_ADMIN_SECRET_ARN": val("dojo_admin_secret_arn"),
        "STAGING_URL": val("staging_url"),
        "PRODUCTION_URL": val("production_url"),
        "TF_STATE_BUCKET": bucket,
    }
    for key, value in settings.items():
        gh("variable", "set", key, "--repo", repository, "--body", value)
    for environment in ["staging", "production"]:
        for key, value in {
            "ECS_SERVICE": "securetask-" + environment,
            "APP_URL": val(environment + "_url"),
        }.items():
            gh(
                "variable",
                "set",
                key,
                "--repo",
                repository,
                "--env",
                environment,
                "--body",
                value,
            )
    summary = "# Infrastructure ready\n\n"
    summary += "- AWS region: us-east-1\n- Terraform bucket: " + bucket + "\n"
    summary += (
        "- Production URL (ready after the first release): "
        + val("production_url")
        + "\n"
    )
    summary += "- Staging URL: " + val("staging_url") + "\n"
    summary += "- DefectDojo instance: " + val("dojo_instance_id") + "\n"
    summary += "- Dojo administrator secret ARN: " + val("dojo_admin_secret_arn") + "\n"
    summary += (
        "\nNext: open DefectDojo through the AWS console, then run Secure release.\n"
    )
    import os

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(summary)
    print("Repository variables updated; read the workflow summary for URLs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository")
    parser.add_argument("--reviewer")
    parser.add_argument("--environments-only", action="store_true")
    parser.add_argument("--bucket")
    args = parser.parse_args()
    if args.environments_only:
        if not args.reviewer:
            parser.error("--reviewer is required with --environments-only")
        configure_environments(args.repository, args.reviewer)
    else:
        if not args.bucket:
            parser.error("--bucket is required when publishing settings")
        publish_settings(args.repository, args.bucket)
