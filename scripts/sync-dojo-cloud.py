"""Administrator-only initial report import; release jobs instead use a restricted SSM tunnel."""

import base64, json, pathlib, os, subprocess, argparse, uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--tools", nargs="+", required=True)
    a.add_argument("--scope", default="main")
    a.add_argument("--reports", default="reports")
    args = a.parse_args()
    out = json.loads(
        subprocess.check_output(
            ["terraform", "-chdir=infra/platform", "output", "-json"]
        )
    )
    instance = out["dojo_instance_id"]["value"]
    workspace = "/opt/securetask-reports/" + args.scope + "-" + uuid.uuid4().hex
    commands = ["set -eu", "mkdir -p " + workspace + "/reports", "cd " + workspace]
    for tool in args.tools:
        for suffix in ["status.json", "generic.json"]:
            path = ROOT / args.reports / f"{tool}.{suffix}"
            commands.append(
                "echo "
                + base64.b64encode(path.read_bytes()).decode()
                + " | base64 -d > reports/"
                + path.name
            )
    commands.append(
        "echo "
        + base64.b64encode((ROOT / "scripts/upload_findings.py").read_bytes()).decode()
        + " | base64 -d > upload.py"
    )
    script = f"""import json,os,subprocess
cfg=json.load(open('/opt/securetask-dojo/ci.json'))
env=dict(os.environ,DOJO_URL='http://127.0.0.1:8080',DOJO_ALLOW_LOCAL_HTTP='true',DOJO_TOKEN=cfg['token'],DOJO_TEST_IDS=json.dumps(cfg['tests']))
subprocess.run(['python3','upload.py','--tools',*{args.tools!r},'--scope',{args.scope!r}],env=env,check=True)
"""
    commands.append(
        "echo " + base64.b64encode(script.encode()).decode() + " | base64 -d > run.py"
    )
    commands.append("python3 run.py")
    x = json.loads(
        subprocess.check_output(
            [
                "aws",
                "ssm",
                "send-command",
                "--instance-ids",
                instance,
                "--document-name",
                "AWS-RunShellScript",
                "--parameters",
                json.dumps({"commands": commands}),
                "--output",
                "json",
            ]
        )
    )
    print("Report import dispatched:", x["Command"]["CommandId"])
