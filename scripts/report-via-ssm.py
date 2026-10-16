"""Tunnel only to the private Dojo host; send token through encrypted SSM transport."""

import argparse, os, subprocess, socket, time, json

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--tools", nargs="+", required=True)
    a.add_argument("--scope", default="main")
    args = a.parse_args()
    config = json.loads(
        subprocess.check_output(
            [
                "aws",
                "secretsmanager",
                "get-secret-value",
                "--secret-id",
                os.environ["DOJO_INTEGRATION_SECRET_ARN"],
                "--query",
                "SecretString",
                "--output",
                "text",
            ],
            text=True,
        )
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        local_port = probe.getsockname()[1]
    params = json.dumps({"portNumber": ["8080"], "localPortNumber": [str(local_port)]})
    with open(os.devnull, "w") as log:
        tunnel = subprocess.Popen(
            [
                "aws",
                "ssm",
                "start-session",
                "--target",
                os.environ["DOJO_INSTANCE_ID"],
                "--document-name",
                "AWS-StartPortForwardingSession",
                "--parameters",
                params,
            ],
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(60):
                if tunnel.poll() is not None:
                    raise RuntimeError("SSM tunnel failed")
                try:
                    with socket.create_connection(("127.0.0.1", local_port), timeout=1):
                        break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError("SSM tunnel timeout")
            env = dict(
                os.environ,
                DOJO_URL=f"http://127.0.0.1:{local_port}",
                DOJO_ALLOW_LOCAL_HTTP="true",
                DOJO_TOKEN=config["token"],
                DOJO_TEST_IDS=json.dumps(config["tests"]),
            )
            subprocess.run(
                [
                    "python3",
                    "scripts/upload_findings.py",
                    "--tools",
                    *args.tools,
                    "--scope",
                    args.scope,
                ],
                env=env,
                check=True,
            )
        finally:
            tunnel.terminate()
            tunnel.wait(timeout=15)
