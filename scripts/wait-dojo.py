"""Wait for private Dojo startup and successful integration setup in the CI runner."""

import json
import pathlib
import re
import subprocess
import time


def aws(*args):
    return json.loads(
        subprocess.check_output(["aws", *args, "--output", "json"], text=True)
    )


def wait_ready(instance, timeout=1800):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = aws(
            "ssm",
            "describe-instance-information",
            "--filters",
            "Key=InstanceIds,Values=" + instance,
        )
        if any(
            item.get("PingStatus") == "Online"
            for item in result["InstanceInformationList"]
        ):
            return
        time.sleep(15)
    raise RuntimeError("Dojo instance did not become Online within 30 minutes")


def safe_output(value, limit=6000):
    """Remove common credential representations before exposing a diagnostic tail."""
    value = str(value or "")
    value = re.sub(r"(://[^:/\s]+:)[^@/\s]+@", r"\1[REDACTED]@", value)
    value = re.sub(
        r"(?im)^.*(?:password|secretstring|(?:api|access|secret)[_-]?key|token)"
        r"[\"']?\s*[:=].*$",
        "[REDACTED credential assignment]",
        value,
    )
    value = re.sub(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b", "[REDACTED AWS key]", value)
    value = re.sub(r"\b[a-fA-F0-9]{40}\b", "[REDACTED token or hash]", value)
    return value[-limit:]


def setup_error(instance, command, data):
    details = [
        "Dojo setup failed: " + str(data.get("Status", "unknown")),
        "Instance: " + instance + "; SSM command: " + command,
        "Response code: " + str(data.get("ResponseCode", "unknown")),
    ]
    for key in ["StandardOutputContent", "StandardErrorContent"]:
        if data.get(key):
            details.append(key + ":\n" + safe_output(data[key]))
    details.append(
        "Open AWS Systems Manager > Run Command in us-east-1 and select this command. "
        "If output stops before a setup stage, inspect EC2 > Instance > Actions > "
        "Monitor and troubleshoot > Get system log for cloud-init errors."
    )
    return "\n".join(details)


def wait_setup(instance, command, timeout=2700):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "aws",
                "ssm",
                "get-command-invocation",
                "--instance-id",
                instance,
                "--command-id",
                command,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            if "InvocationDoesNotExist" not in result.stderr:
                raise RuntimeError(safe_output(result.stderr))
        else:
            data = json.loads(result.stdout)
            status = data["Status"]
            if status == "Success" and data.get("ResponseCode") == 0:
                return
            if status not in ("Pending", "InProgress", "Delayed"):
                raise RuntimeError(setup_error(instance, command, data))
        time.sleep(10)
    raise RuntimeError(
        "Dojo setup exceeded the runner deadline; instance " + instance
        + "; SSM command " + command
        + ". Inspect or cancel that command before starting another provisioning run."
    )


if __name__ == "__main__":
    outputs = json.loads(
        subprocess.check_output(
            ["terraform", "-chdir=infra/platform", "output", "-json"]
        )
    )
    instance = outputs["dojo_instance_id"]["value"]
    wait_ready(instance)
    subprocess.run(["python3", "scripts/configure-dojo-host.py"], check=True)
    setup = json.loads(pathlib.Path("activation/dojo-setup-command.json").read_text())
    wait_setup(instance, setup["id"])
    for key in ["dojo_integration_secret_arn", "dojo_admin_secret_arn"]:
        secret = aws(
            "secretsmanager", "describe-secret", "--secret-id", outputs[key]["value"]
        )
        if not any(
            "AWSCURRENT" in stages
            for stages in secret.get("VersionIdsToStages", {}).values()
        ):
            raise RuntimeError("Dojo secret has no current version: " + key)
    print("Private DefectDojo and its integration are ready")
