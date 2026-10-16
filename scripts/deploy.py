"""Deploy a specific approved digest; confirm rollback did not replace the release."""

import argparse, json, subprocess, time, os

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def aws(*args):
    return json.loads(subprocess.check_output(["aws", *args, "--output", "json"]))


def deploy(cluster, service, image, url=None):
    old = aws("ecs", "describe-services", "--cluster", cluster, "--services", service)
    if old.get("failures") or len(old.get("services", [])) != 1:
        raise RuntimeError("Service not found; run initial application Terraform apply")
    previous = old["services"][0]["taskDefinition"]
    definition = aws("ecs", "describe-task-definition", "--task-definition", previous)[
        "taskDefinition"
    ]
    allowed = [
        "family",
        "taskRoleArn",
        "executionRoleArn",
        "networkMode",
        "containerDefinitions",
        "volumes",
        "placementConstraints",
        "requiresCompatibilities",
        "cpu",
        "memory",
        "pidMode",
        "ipcMode",
        "proxyConfiguration",
        "inferenceAccelerators",
        "ephemeralStorage",
        "runtimePlatform",
    ]
    definition = {k: v for k, v in definition.items() if k in allowed}
    for c in definition["containerDefinitions"]:
        if c["name"] == "app":
            c["image"] = image
    # Use a local temporary file; CLI input contains no secret values, only secret ARNs.
    import tempfile, os

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(definition, f)
        name = f.name
    try:
        new = aws(
            "ecs", "register-task-definition", "--cli-input-json", "file://" + name
        )["taskDefinition"]["taskDefinitionArn"]
        aws(
            "ecs",
            "update-service",
            "--cluster",
            cluster,
            "--service",
            service,
            "--task-definition",
            new,
        )
        subprocess.run(
            [
                "aws",
                "ecs",
                "wait",
                "services-stable",
                "--cluster",
                cluster,
                "--services",
                service,
            ],
            check=True,
        )
        current = aws(
            "ecs", "describe-services", "--cluster", cluster, "--services", service
        )["services"][0]
        if current["taskDefinition"] != new or any(
            d.get("rolloutState") == "FAILED" for d in current["deployments"]
        ):
            raise RuntimeError("Release failed or ECS rolled back")
        if url:
            from smoke import smoke

            smoke(url)
        print("Deployed " + new)
    except Exception:
        aws(
            "ecs",
            "update-service",
            "--cluster",
            cluster,
            "--service",
            service,
            "--task-definition",
            previous,
        )
        raise
    finally:
        os.unlink(name)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--cluster", required=True)
    a.add_argument("--service", required=True)
    a.add_argument("--image", required=True)
    a.add_argument("--url")
    args = a.parse_args()
    import re

    if not re.fullmatch(
        r"\d{12}\.dkr\.ecr\.us-east-1\.amazonaws\.com/[a-z0-9._/-]+@sha256:[a-f0-9]{64}",
        args.image,
    ):
        raise SystemExit("Expected us-east-1 ECR image pinned by digest")
    deploy(args.cluster, args.service, args.image, args.url)
