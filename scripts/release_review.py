"""Publish deployment links and verify the GitHub production approval gate."""

import argparse
import json
import os
import re
import subprocess
from urllib.parse import urlparse


def validate_release(url, image):
    parsed = urlparse(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or any(c in url for c in "\r\n()")
    ):
        raise ValueError("A valid application URL is required for staging review")
    if not re.fullmatch(
        r"\d{12}\.dkr\.ecr\.us-east-1\.amazonaws\.com/securetask@sha256:[a-f0-9]{64}",
        image,
    ):
        raise ValueError("Review must identify the immutable ECR image digest")


def required_reviewers(environment):
    reviewers = [
        reviewer
        for rule in environment.get("protection_rules", [])
        if rule.get("type") == "required_reviewers"
        for reviewer in rule.get("reviewers", [])
        if reviewer.get("reviewer", {}).get("id")
    ]
    if not reviewers:
        raise ValueError(
            "Production has no required reviewer. In GitHub Settings > Environments > production, enable Required reviewers and save your reviewer before starting a new release."
        )
    return [
        r["reviewer"].get("login")
        or r["reviewer"].get("name")
        or str(r["reviewer"]["id"])
        for r in reviewers
    ]


def check_production_gate(repository):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Expected GitHub owner/repository")
    result = subprocess.run(
        ["gh", "api", "repos/" + repository + "/environments/production"],
        text=True,
        capture_output=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(
            "Could not verify the production approval environment. Check Actions read permission and the production environment settings. "
            + result.stderr
        )
    return required_reviewers(json.loads(result.stdout))


def staging_summary(url, image, reviewers):
    validate_release(url, image)
    return (
        "## Staging is ready for your review\n\n"
        + "[Open staging application]("
        + url
        + ")\n\n"
        + "Staging deployment, application smoke checks, ZAP reporting, and runtime policy have passed.\n\n"
        + "Inspect the app: sign in or register a test account, create a project and task, change the task status, add a comment, and sign out.\n\n"
        + "Return to this workflow run. Click **Review deployments**, select **production**, and choose **Approve and deploy** only after staging looks correct. Choose **Reject** to stop production.\n\n"
        + "Required reviewer(s): "
        + ", ".join(reviewers)
        + "\n\n"
        + "Production will use this same scanned image: `"
        + image
        + "`\n"
    )


def deployment_summary(environment, url, image):
    validate_release(url, image)
    text = "## " + environment.capitalize() + " deployment passed\n\n"
    text += "[Open " + environment + " application](" + url + ")\n\n"
    text += "Image: `" + image + "`\n\n"
    if environment == "staging":
        text += "You can inspect staging now. After ZAP and runtime policy pass, production waits for your required-reviewer approval.\n"
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["deployed", "staging-ready"])
    parser.add_argument("--environment", choices=["staging", "production"])
    parser.add_argument("--url", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    validate_release(args.url, args.image)
    if args.mode == "staging-ready":
        reviewers = check_production_gate(os.environ["GITHUB_REPOSITORY"])
        text = staging_summary(args.url, args.image, reviewers)
    else:
        if not args.environment:
            parser.error("--environment is required for deployed")
        text = deployment_summary(args.environment, args.url, args.image)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write(text)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write("url=" + args.url + "\n")
    print(text)


if __name__ == "__main__":
    main()
