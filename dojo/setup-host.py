"""Idempotent Dojo setup on the private Ubuntu EC2 host; never print credentials."""

import argparse
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

HOST = pathlib.Path("/opt/securetask-dojo")
UNIT = pathlib.Path("/etc/systemd/system/securetask-dojo.service")


def repair_apt_sources(directory=pathlib.Path("/etc/apt")):
    """Use Ubuntu's HTTPS archives instead of an unreachable EC2 HTTP mirror."""
    sources = [directory / "sources.list"]
    sources += sorted((directory / "sources.list.d").glob("*.list"))
    sources += sorted((directory / "sources.list.d").glob("*.sources"))
    for source in sources:
        if not source.is_file():
            continue
        original = source.read_text()
        updated = re.sub(
            r"https?://(?:[a-z0-9-]+\.)?ec2\.archive\.ubuntu\.com/ubuntu\b",
            "https://archive.ubuntu.com/ubuntu",
            original,
        )
        updated = updated.replace(
            "http://archive.ubuntu.com/ubuntu", "https://archive.ubuntu.com/ubuntu"
        ).replace(
            "http://security.ubuntu.com/ubuntu", "https://security.ubuntu.com/ubuntu"
        )
        if updated != original:
            source.write_text(updated)
    config = directory / "apt.conf.d/99securetask-network"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('Acquire::ForceIPv4 "true";\nAcquire::Retries "3";\n')


def run(*args):
    subprocess.run(args, check=True, cwd=HOST)


def install_runtime():
    print("[Dojo setup] Checking package sources and Docker prerequisites", flush=True)
    repair_apt_sources()
    compose = None
    if shutil.which("docker"):
        compose = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True
        )
    if (
        compose is None
        or compose.returncode
        or not shutil.which("curl")
        or importlib.util.find_spec("boto3") is None
    ):
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"
        run(
            "apt-get",
            "-o", "DPkg::Lock::Timeout=120",
            "-o", "APT::Update::Error-Mode=any",
            "update",
        )
        run(
            "apt-get",
            "-o", "DPkg::Lock::Timeout=120",
            "install", "-y",
            "ca-certificates",
            "curl",
            "docker.io",
            "docker-compose-v2",
            "python3",
            "python3-boto3",
        )
    run("docker", "compose", "version")
    run("systemctl", "enable", "--now", "docker")


def start_stack():
    print("[Dojo setup] Starting the existing Dojo stack; preserving its data", flush=True)
    (HOST / "docker/extra_settings").mkdir(parents=True, exist_ok=True)
    if not (HOST / ".env").exists():
        run("python3", "init-env.py")
    (HOST / ".env").chmod(0o600)
    unit = """[Unit]
Description=Secure Task By Akuphe DefectDojo
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/securetask-dojo
TimeoutStartSec=900
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose stop
[Install]
WantedBy=multi-user.target
"""
    UNIT.write_text(unit)
    # Expanded compose configuration would contain passwords, so keep validation quiet.
    run("docker", "compose", "config", "--quiet")
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "securetask-dojo")
    active = subprocess.run(
        ["systemctl", "is-active", "--quiet", "securetask-dojo"]
    )
    if active.returncode == 0:
        run("docker", "compose", "up", "-d")
    else:
        run("systemctl", "start", "securetask-dojo")


def wait_http(timeout=600):
    print("[Dojo setup] Waiting for the local login page", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8080/login", timeout=10
            ) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(5)
    raise RuntimeError(
        "Dojo login page did not become ready. Inspect Docker service status and "
        "initializer errors on the private host; integration setup was not attempted."
    )


def provision_integration(region, integration_secret, admin_secret):
    print("[Dojo setup] Creating product, scanner tests and integration account", flush=True)
    (HOST / "provision.py").chmod(0o644)
    run("docker", "compose", "cp", "provision.py", "uwsgi:/app/securetask-provision.py")
    run("docker", "compose", "exec", "-T", "uwsgi", "python", "/app/securetask-provision.py")
    run("docker", "compose", "cp", "uwsgi:/app/media/securetask-ci.json", "ci.json")
    (HOST / "ci.json").chmod(0o600)
    print("[Dojo setup] Storing private integration credentials in Secrets Manager", flush=True)
    import boto3

    config = json.loads((HOST / "ci.json").read_text())
    values = dict(
        line.split("=", 1)
        for line in (HOST / ".env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    client = boto3.client("secretsmanager", region_name=region)
    client.put_secret_value(SecretId=integration_secret, SecretString=json.dumps(config))
    client.put_secret_value(
        SecretId=admin_secret,
        SecretString=json.dumps(
            {
                "username": values.get("DD_ADMIN_USER", "admin"),
                "password": values["DD_ADMIN_PASSWORD"],
            }
        ),
    )


def setup(region, integration_secret, admin_secret):
    HOST.mkdir(parents=True, exist_ok=True)
    install_runtime()
    start_stack()
    wait_http()
    provision_integration(region, integration_secret, admin_secret)
    print("[Dojo setup] Private DefectDojo integration is ready", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--integration-secret-arn", required=True)
    parser.add_argument("--admin-secret-arn", required=True)
    args = parser.parse_args()
    setup(args.region, args.integration_secret_arn, args.admin_secret_arn)
