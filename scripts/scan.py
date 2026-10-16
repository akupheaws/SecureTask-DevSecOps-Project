"""Run pinned scanner containers with no cloud credentials or Docker socket."""

import argparse, json, pathlib, subprocess, sys, os, tempfile, shutil
from normalize import normalize, validate_checkov_policies

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKOV_POLICIES = [
    "security/checkov/s3_public_access.yml",
    "security/checkov/rds_encryption.yml",
]


def run(tool, demo=False, image=None, include_remediation_demo=False):
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    out = reports / f"{tool}.json"
    status = reports / f"{tool}.status.json"
    generic = reports / f"{tool}.generic.json"
    lock = json.loads((ROOT / "security/tools.lock.json").read_text())
    ref = lock[tool]["image"]
    platform = os.getenv("SCANNER_PLATFORM", lock[tool].get("platform", "linux/amd64"))
    sandbox = tempfile.TemporaryDirectory(prefix="securetask-scan-")
    source = pathlib.Path(sandbox.name)
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    for name in files:
        if not name:
            continue
        original = ROOT / name
        if original.is_symlink():
            raise ValueError("Symlinks are not accepted in scanner inputs")
        if original.is_file():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
    if tool == "gitleaks":
        shutil.copytree(
            ROOT / ".git", source / ".git", ignore=shutil.ignore_patterns("hooks")
        )
    common = [
        "docker",
        "run",
        "--rm",
        "--platform",
        platform,
        "-v",
        f"{source}:/src:ro",
        "-w",
        "/src",
    ]
    args = {
        "semgrep": [
            "semgrep",
            "scan",
            "--config",
            "security/semgrep",
            "--json",
            "--error",
            "backend",
            "frontend",
        ]
        + (["security/demo/unsafe-search.ts"] if demo else [])
        + (
            ["security/demo/unsafe-search.ts", "security/demo/unsafe-expression.ts"]
            if include_remediation_demo
            else []
        ),
        "gitleaks": [
            "git",
            "--redact",
            "--config",
            "/src/.gitleaks.toml",
            "--report-format",
            "json",
            "--report-path",
            "/out/report.json",
            "/src",
        ],
        "osv": [
            "scan",
            "source",
            "--lockfile",
            "package-lock.json",
            "--format",
            "json",
        ],
        "checkov": [
            "-d",
            "infra",
            "--framework",
            "terraform",
            "--output",
            "json",
        ]
        + (
            ["--external-checks-dir", "security/checkov"]
            if (ROOT / "security/checkov").exists()
            else []
        ),
        "hadolint": [
            "hadolint",
            "--config",
            "security/.hadolint.yaml",
            "--format",
            "json",
            "Dockerfile",
        ],
        "trivy": [
            "image",
            "--input",
            "/image/image.tar",
            "--format",
            "json",
            "--exit-code",
            "1",
            "--scanners",
            "vuln",
        ],
    }
    if tool == "checkov" and demo:
        args[tool] = [
            "-d",
            "security/demo",
            "--framework",
            "terraform",
            "--output",
            "json",
            "--quiet",
        ]
    if tool == "gitleaks":
        scratch = reports / "gitleaks-work"
        scratch.mkdir(exist_ok=True)
        common += ["-v", f"{scratch}:/out"]
    if tool == "trivy":
        if not image:
            raise ValueError("--image required")
        subprocess.run(
            ["docker", "save", "-o", str(reports / "image.tar"), image], check=True
        )
        common += ["-v", f"{reports}:/image:ro"]
    completed = False
    code = -1
    try:
        if tool == "checkov" and not demo:
            for name in CHECKOV_POLICIES:
                if not (source / name).is_file():
                    raise ValueError("Missing required infrastructure policy: " + name)
        with out.open("w") as handle:
            result = subprocess.run(
                common + [ref] + args[tool], stdout=handle, timeout=900
            )
            code = result.returncode
        if tool == "gitleaks":
            source = reports / "gitleaks-work/report.json"
            if source.exists():
                out.write_text(source.read_text())
        # Both 0 (clean) and 1 (findings) are valid only with a well-formed report.
        if code not in [0, 1]:
            raise RuntimeError(f"scanner exited {code}")
        raw = json.loads(out.read_text())
        if tool == "checkov" and not demo:
            validate_checkov_policies(raw, ["CKV2_AKUPHE_1", "CKV2_AKUPHE_2"])
        result = normalize(tool, raw)
        generic.write_text(json.dumps(result, indent=2))
        completed = True
    except Exception as e:
        print(f"{tool}: {type(e).__name__}: {e}", file=sys.stderr)
    status.write_text(
        json.dumps(
            {
                "tool": tool,
                "completed": completed,
                "exit_code": code,
                "version": lock[tool]["version"],
            }
        )
    )
    if tool == "trivy":
        (reports / "image.tar").unlink(missing_ok=True)
    sandbox.cleanup()
    return completed


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument(
        "--tools",
        nargs="+",
        default=["semgrep", "gitleaks", "osv", "checkov", "hadolint"],
    )
    a.add_argument("--demo", action="store_true")
    a.add_argument("--image")
    a.add_argument("--include-remediation-demo", action="store_true")
    args = a.parse_args()
    if args.demo and args.include_remediation_demo:
        a.error("Use either the legacy demo or the release remediation exercises")
    success = True
    for tool in args.tools:
        success = (
            run(tool, args.demo, args.image, args.include_remediation_demo) and success
        )
    sys.exit(not success)
