"""Upload normalized findings to pre-created DefectDojo tests; fail closed."""

import argparse, datetime, json, os, pathlib, secrets, urllib.request, urllib.parse


def upload(tool, path, base, token, test_id, commit, branch, build):
    boundary = "SecureTask" + secrets.token_hex(12)
    chunks = []
    fields = {
        "test": test_id,
        "scan_type": "Generic Findings Import",
        "active": "true",
        "verified": "false",
        "close_old_findings": "true",
        "close_old_findings_product_scope": "false",
        "minimum_severity": "Info",
        "scan_date": datetime.date.today().isoformat(),
        "commit_hash": commit,
        "branch_tag": branch,
        "build_id": build,
    }
    for key, value in fields.items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        )
    chunks.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{tool}.json"\r\nContent-Type: application/json\r\n\r\n'.encode()
        + path.read_bytes()
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        base.rstrip("/") + "/api/v2/reimport-scan/",
        data=b"".join(chunks),
        headers={
            "Authorization": "Token " + token,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        if response.status not in (200, 201):
            raise RuntimeError("Upload failed")
    count = len(json.loads(path.read_text())["findings"])
    print(f"{tool}: reimported {count} findings into existing Test {test_id}")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--reports", default="reports")
    a.add_argument("--tools", nargs="+", required=True)
    a.add_argument("--scope", default="main")
    args = a.parse_args()
    base = os.environ["DOJO_URL"]
    token = os.environ["DOJO_TOKEN"]
    tests = json.loads(os.environ["DOJO_TEST_IDS"])
    scope = tests[args.scope]
    if urllib.parse.urlparse(base).scheme != "https" and not (
        os.environ.get("DOJO_ALLOW_LOCAL_HTTP") == "true"
        and urllib.parse.urlparse(base).hostname in ["localhost", "127.0.0.1"]
    ):
        raise SystemExit(
            "DefectDojo API must use HTTPS; allow local HTTP only on trusted networks"
        )
    for tool in args.tools:
        status = json.loads(
            (pathlib.Path(args.reports) / f"{tool}.status.json").read_text()
        )
        if not status["completed"]:
            raise SystemExit("Incomplete scan: " + tool)
        upload(
            tool,
            pathlib.Path(args.reports) / f"{tool}.generic.json",
            base,
            token,
            scope[tool],
            os.getenv("GITHUB_SHA", "local"),
            os.getenv("GITHUB_REF_NAME", "local"),
            os.getenv("GITHUB_RUN_ID", "local"),
        )
