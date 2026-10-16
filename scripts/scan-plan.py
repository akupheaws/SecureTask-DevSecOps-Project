import json, pathlib, subprocess, sys
from normalize import normalize, validate_checkov_policies

reports = pathlib.Path("reports")
reports.mkdir(exist_ok=True)
path = pathlib.Path("reports-plan.json").resolve()
lock = json.loads(pathlib.Path("security/tools.lock.json").read_text())["checkov"]
completed = False
code = -1
try:
    with (reports / "checkov.json").open("w") as out:
        code = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                str(path) + ":/plan.json:ro",
                "-v",
                str(pathlib.Path("security/checkov").resolve()) + ":/checks:ro",
                lock["image"],
                "-f",
                "/plan.json",
                "--framework",
                "terraform_plan",
                "--external-checks-dir",
                "/checks",
                "--output",
                "json",
            ],
            stdout=out,
            timeout=600,
        ).returncode
    if code not in [0, 1]:
        raise RuntimeError("Plan scanner failed")
    raw = json.loads((reports / "checkov.json").read_text())
    # S3 bootstrap is checked by the preflight; RDS is in the platform plan.
    validate_checkov_policies(raw, ["CKV2_AKUPHE_2"])
    data = normalize("checkov", raw)
    (reports / "checkov.generic.json").write_text(json.dumps(data))
    completed = True
except Exception as e:
    print(str(e), file=sys.stderr)
(reports / "checkov.status.json").write_text(
    json.dumps({"completed": completed, "exit_code": code, "version": lock["version"]})
)
sys.exit(not completed)
