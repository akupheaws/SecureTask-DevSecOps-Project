"""Fail closed on scanner errors, missing reports, or blocked findings."""

import argparse, datetime, json, pathlib, sys

SOURCE_TOOLS = ["semgrep", "gitleaks", "osv", "checkov", "hadolint"]


def evaluate(directory, tools, policy):
    failures = []
    findings = []
    for tool in tools:
        try:
            status = json.loads((directory / f"{tool}.status.json").read_text())
            if not status.get("completed"):
                raise ValueError("scanner did not complete")
            report = json.loads((directory / f"{tool}.generic.json").read_text())
            if not isinstance(report.get("findings"), list):
                raise ValueError("invalid report")
            for f in report["findings"]:
                findings.append((tool, f))
                exceptions = [
                    e
                    for e in policy.get("exceptions", [])
                    if e.get("finding_id") == f["unique_id_from_tool"]
                    and e.get("tool") == tool
                    and e.get("approver")
                    and e.get("reason")
                    and datetime.date.fromisoformat(e["expires"])
                    >= datetime.date.today()
                ]
                if (
                    tool in policy.get("always_block_tools", [])
                    or f["severity"] == "Critical"
                    or (f["severity"] in policy["block_severities"] and not exceptions)
                ):
                    failures.append(f'{tool}: {f["severity"]} — {f["title"]}')
        except (OSError, ValueError, KeyError, TypeError) as e:
            failures.append(f"{tool}: invalid or missing evidence ({e})")
    return findings, failures


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--reports", default="reports")
    a.add_argument("--tools", nargs="+", default=SOURCE_TOOLS)
    a.add_argument("--policy", default="security/policy.json")
    args = a.parse_args()
    findings, failures = evaluate(
        pathlib.Path(args.reports),
        args.tools,
        json.loads(pathlib.Path(args.policy).read_text()),
    )
    text = (
        f"Security review: {len(findings)} findings; {len(failures)} blocking conditions.\n"
        + "\n".join(failures)
    )
    print(text)
    import os

    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("```text\n" + text.replace("```", "") + "\n```\n")
    sys.exit(bool(failures))
