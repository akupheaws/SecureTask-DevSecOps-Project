import argparse, json, pathlib, subprocess, sys
from normalize import normalize

ROOT = pathlib.Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("url")
    args = a.parse_args()
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    lock = json.loads((ROOT / "security/tools.lock.json").read_text())["zap"]
    completed = False
    code = -1
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "--user",
                "0",
                "-v",
                str(reports) + ":/zap/wrk:rw",
                lock["image"],
                "zap-baseline.py",
                "-t",
                args.url,
                "-J",
                "zap.json",
                "-r",
                "zap.html",
            ],
            timeout=600,
        )
        code = result.returncode
        if code not in (0, 1, 2):
            raise RuntimeError("ZAP failed to run")
        data = json.loads((reports / "zap.json").read_text())
        (reports / "zap.generic.json").write_text(
            json.dumps(normalize("zap", data), indent=2)
        )
        completed = True
    except Exception as e:
        print(str(e), file=sys.stderr)
    (reports / "zap.status.json").write_text(
        json.dumps(
            {"completed": completed, "exit_code": code, "version": lock["version"]}
        )
    )
    sys.exit(not completed)
