"""First release creates its ECS service through Terraform; subsequent releases update it."""

import argparse, json, subprocess, os, pathlib, re

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
a = argparse.ArgumentParser()
a.add_argument("--environment", choices=["staging", "production"], required=True)
a.add_argument("--image", required=True)
a.add_argument("--bucket", required=True)
args = a.parse_args()
if not re.fullmatch(
    r"\d{12}\.dkr\.ecr\.us-east-1\.amazonaws\.com/securetask@sha256:[a-f0-9]{64}",
    args.image,
):
    raise SystemExit("Invalid immutable release image")
x = json.loads(
    subprocess.check_output(
        [
            "aws",
            "ecs",
            "describe-services",
            "--cluster",
            "securetask",
            "--services",
            "securetask-" + args.environment,
            "--output",
            "json",
        ]
    )
)
if x.get("services") and x["services"][0]["status"] == "ACTIVE":
    print("Service exists; continuing to digest deployment")
else:
    base = ["terraform", "-chdir=infra/application"]
    subprocess.run(
        base
        + [
            "init",
            "-input=false",
            "-reconfigure",
            "-backend-config=bucket=" + args.bucket,
            "-backend-config=key=application/"
            + args.environment
            + "/terraform.tfstate",
            "-backend-config=region=us-east-1",
            "-backend-config=encrypt=true",
            "-backend-config=use_lockfile=true",
        ],
        check=True,
    )
    subprocess.run(
        base
        + [
            "apply",
            "-input=false",
            "-auto-approve",
            "-var=state_bucket=" + args.bucket,
            "-var=environment=" + args.environment,
            "-var=image_digest=" + args.image.split("@")[1],
            "-var=allow_http_demo=true",
        ],
        check=True,
    )
