"""Strict report adapters -> DefectDojo Generic Findings Import. No credentials needed."""

import argparse, hashlib, json, pathlib

SEVERITIES = {
    "ERROR": "High",
    "WARNING": "Medium",
    "INFO": "Info",
    "CRITICAL": "Critical",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "MODERATE": "Medium",
    "LOW": "Low",
    "NONE": "Info",
    "UNKNOWN": "Medium",
}


def validate_checkov_policies(data, expected):
    """Require evidence that each mandatory policy examined actual resources."""
    examined = set()
    entries = data if isinstance(data, list) else [data]
    for entry in entries:
        results = entry["results"]
        if any(f["check_id"] in expected for f in results.get("skipped_checks", [])):
            raise ValueError("Required infrastructure policies must not be skipped")
        for key in ["passed_checks", "failed_checks"]:
            examined.update(f["check_id"] for f in results.get(key, []))
    missing = set(expected) - examined
    if missing:
        raise ValueError("Required infrastructure policy coverage missing: " + ", ".join(sorted(missing)))


def normalize(tool, data):
    findings = []

    def add(rule, title, description, path="", line=None, severity="Medium"):
        severity = SEVERITIES.get(str(severity).upper(), severity)
        if severity not in ("Critical", "High", "Medium", "Low", "Info"):
            raise ValueError("Unknown severity " + str(severity))
        identity = f"{tool}|{rule}|{path}|{line or 0}"
        f = {
            "title": f"[{tool}] {title}",
            "description": str(description) or str(title),
            "severity": severity,
            "unique_id_from_tool": hashlib.sha256(identity.encode()).hexdigest(),
            "static_finding": tool != "zap",
            "dynamic_finding": tool == "zap",
            "active": True,
            "verified": False,
        }
        if path:
            f["file_path"] = str(path)
        if line:
            f["line"] = int(line)
        findings.append(f)

    if tool == "semgrep":
        if not isinstance(data, dict) or "results" not in data:
            raise ValueError("Invalid Semgrep report")
        if data.get("errors"):
            raise ValueError("Semgrep reported execution/analysis errors")
        for f in data["results"]:
            add(
                f["check_id"],
                f["extra"]["message"],
                f["extra"]["message"],
                f["path"],
                f["start"]["line"],
                f["extra"]["severity"],
            )
    elif tool == "gitleaks":
        if not isinstance(data, list):
            raise ValueError("Invalid Gitleaks report")
        for f in data:
            add(
                f["RuleID"],
                f["Description"],
                "Potential committed secret. Value redacted; rotate if real.",
                f["File"],
                f["StartLine"],
                "High",
            )
    elif tool == "hadolint":
        if not isinstance(data, list):
            raise ValueError("Invalid Hadolint report")
        for f in data:
            add(
                f["code"],
                f["message"],
                f["message"],
                f["file"],
                f["line"],
                {
                    "error": "High",
                    "warning": "Medium",
                    "info": "Low",
                    "style": "Info",
                }.get(f["level"], "Medium"),
            )
    elif tool == "checkov":
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict) or "results" not in entry:
                raise ValueError("Invalid Checkov report")
            if entry.get("summary", {}).get("parsing_errors", 0):
                raise ValueError("Checkov parsing errors")
            for f in entry["results"].get("failed_checks", []):
                add(
                    f["check_id"],
                    f["check_name"],
                    f["check_name"] + "\nResource: " + f["resource"],
                    f["file_path"],
                    (f.get("file_line_range") or [None])[0],
                    f.get("severity")
                    or (
                        "High"
                        if f["check_id"]
                        in [
                            "CKV_AWS_20",
                            "CKV_AWS_53",
                            "CKV_AWS_54",
                            "CKV_AWS_55",
                            "CKV_AWS_56",
                            "CKV_AWS_17",
                            "CKV_AWS_19",
                            "CKV_AWS_21",
                            "CKV_AWS_24",
                            "CKV_AWS_25",
                            "CKV_AWS_40",
                            "CKV_AWS_41",
                            "CKV2_AKUPHE_1",
                            "CKV2_AKUPHE_2",
                        ]
                        else "Medium"
                    ),
                )
    elif tool == "osv":
        if not isinstance(data, dict) or "results" not in data:
            raise ValueError("Invalid OSV report")
        for result in data["results"]:
            for package in result.get("packages", []):
                for f in package.get("vulnerabilities", []):
                    severity = (f.get("database_specific") or {}).get(
                        "severity"
                    ) or "High"
                    add(
                        f["id"],
                        f["id"] + " in " + package["package"]["name"],
                        f.get("summary") or f.get("details") or f["id"],
                        result["source"]["path"],
                        None,
                        severity,
                    )
    elif tool == "trivy":
        if not isinstance(data, dict) or "SchemaVersion" not in data:
            raise ValueError("Invalid Trivy report")
        for result in data.get("Results", []):
            for f in result.get("Vulnerabilities", []):
                add(
                    f["VulnerabilityID"] + f["PkgName"],
                    f["VulnerabilityID"] + " in " + f["PkgName"],
                    f.get("Description") or f.get("Title") or f["VulnerabilityID"],
                    result["Target"],
                    None,
                    f["Severity"],
                )
    elif tool == "zap":
        if not isinstance(data, dict) or "site" not in data:
            raise ValueError("Invalid ZAP report")
        for site in data["site"]:
            for f in site.get("alerts", []):
                add(
                    f["pluginid"],
                    f["name"],
                    f.get("desc", f["name"]) + "\nSolution: " + f.get("solution", ""),
                    site.get("@name", ""),
                    None,
                    {"0": "Info", "1": "Low", "2": "Medium", "3": "High"}.get(
                        str(f["riskcode"]), "Medium"
                    ),
                )
    else:
        raise ValueError("Unsupported scanner " + tool)
    return {"findings": findings}


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("tool")
    a.add_argument("input")
    a.add_argument("output")
    args = a.parse_args()
    data = json.loads(pathlib.Path(args.input).read_text())
    out = normalize(args.tool, data)
    pathlib.Path(args.output).write_text(json.dumps(out, indent=2))
    print(f'{args.tool}: {len(out["findings"])} findings')
