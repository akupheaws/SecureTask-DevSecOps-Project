"""Refresh Dojo integration on its private host without sending credentials in commands."""

import argparse
import base64
import gzip
import json
import os
import pathlib
import shlex
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"]))


def build_commands(outputs, root=ROOT):
    """Recover a failed bootstrap as well as refresh an already-running host."""
    assets = {}
    for name in ["docker-compose.yml", "init-env.py", "provision.py", "setup-host.py"]:
        assets[name] = base64.b64encode(
            gzip.compress((root / "dojo" / name).read_bytes(), mtime=0)
        ).decode()
    unpack = """import base64,gzip,json,pathlib
root=pathlib.Path('/opt/securetask-dojo')
root.mkdir(parents=True,exist_ok=True)
assets=json.loads(PAYLOAD)
for name,content in assets.items():
    path=root/name
    # Preserve the installed image versions on existing hosts.
    if name == 'docker-compose.yml' and path.exists():
        continue
    path.write_bytes(gzip.decompress(base64.b64decode(content)))
    path.chmod(0o644)
""".replace("PAYLOAD", repr(json.dumps(assets)))
    setup = [
        "python3", "/opt/securetask-dojo/setup-host.py", "--region", "us-east-1",
        "--integration-secret-arn", outputs["dojo_integration_secret_arn"]["value"],
        "--admin-secret-arn", outputs["dojo_admin_secret_arn"]["value"],
    ]
    return [
        "set -eu",
        "echo '[Dojo setup] Waiting for initial cloud-init to finish'",
        "cloud-init status --wait || echo '[Dojo setup] cloud-init reported an error; recovering the project bootstrap'",
        "python3 - <<'SECURETASK_ASSETS'\n" + unpack + "SECURETASK_ASSETS",
        shlex.join(setup),
    ]


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--instance")
    args = a.parse_args()
    outputs = json.loads(
        subprocess.check_output(
            ["terraform", "-chdir=infra/platform", "output", "-json"]
        )
    )
    instance = args.instance or outputs["dojo_instance_id"]["value"]
    commands = build_commands(outputs)
    x = aws(
        "ssm",
        "send-command",
        "--instance-ids",
        instance,
        "--document-name",
        "AWS-RunShellScript",
        "--parameters",
        json.dumps({"commands": commands, "executionTimeout": ["2400"]}),
    )
    command = x["Command"]["CommandId"]
    (ROOT / "activation").mkdir(exist_ok=True)
    (ROOT / "activation/dojo-setup-command.json").write_text(
        json.dumps({"id": command, "instance": instance})
    )
    print("Setup dispatched: " + command)
