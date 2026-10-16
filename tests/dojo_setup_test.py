import base64
import gzip
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


host = module("dojo_host_setup", "dojo/setup-host.py")
config = module("dojo_host_config", "scripts/configure-dojo-host.py")
wait = module("dojo_wait_test", "scripts/wait-dojo.py")
OUTPUTS = {
    "dojo_integration_secret_arn": {"value": "arn:aws:secretsmanager:us-east-1:123456789012:secret:dojo-ci"},
    "dojo_admin_secret_arn": {"value": "arn:aws:secretsmanager:us-east-1:123456789012:secret:dojo-admin"},
}


class DojoSetupTests(unittest.TestCase):
    def test_deb822_and_legacy_mirrors_are_repaired_idempotently(self):
        with tempfile.TemporaryDirectory() as temp:
            apt = Path(temp)
            (apt / "sources.list.d").mkdir()
            deb822 = apt / "sources.list.d/ubuntu.sources"
            legacy = apt / "sources.list"
            third_party = apt / "sources.list.d/vendor.list"
            deb822.write_text(
                "URIs: http://us-east-1.ec2.archive.ubuntu.com/ubuntu/\n"
                "Suites: noble noble-updates\nComponents: main universe\n"
                "URIs: http://security.ubuntu.com/ubuntu\n"
            )
            legacy.write_text("deb http://ec2.archive.ubuntu.com/ubuntu noble universe\n")
            third_party.write_text("deb https://vendor.example/packages stable main\n")
            host.repair_apt_sources(apt)
            expected = deb822.read_text()
            self.assertIn("https://archive.ubuntu.com/ubuntu/", expected)
            self.assertIn("https://security.ubuntu.com/ubuntu", expected)
            self.assertIn("Components: main universe", expected)
            self.assertIn("https://archive.ubuntu.com/ubuntu", legacy.read_text())
            self.assertEqual(third_party.read_text(), "deb https://vendor.example/packages stable main\n")
            self.assertIn('Acquire::ForceIPv4 "true"', (apt / "apt.conf.d/99securetask-network").read_text())
            host.repair_apt_sources(apt)
            self.assertEqual(deb822.read_text(), expected)

    def test_existing_runtime_does_not_reinstall_packages(self):
        with patch.object(host, "repair_apt_sources"), patch.object(
            host.shutil, "which", return_value="/usr/bin/existing"
        ), patch.object(host.importlib.util, "find_spec", return_value=object()), patch.object(
            host.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ), patch.object(host, "run") as run:
            host.install_runtime()
        self.assertFalse(any(call.args[0] == "apt-get" for call in run.call_args_list))
        run.assert_any_call("docker", "compose", "version")

    def test_failed_package_update_stops_before_install_or_start(self):
        with patch.object(host, "repair_apt_sources"), patch.object(
            host.shutil, "which", return_value=None
        ), patch.object(host, "run", side_effect=subprocess.CalledProcessError(100, "apt-get")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                host.install_runtime()
        self.assertEqual(run.call_count, 1)
        self.assertIn("APT::Update::Error-Mode=any", run.call_args.args)

    def test_existing_environment_credentials_and_volumes_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = root / ".env"
            env.write_text("DD_ADMIN_PASSWORD=keep-existing-password\n")
            with patch.object(host, "HOST", root), patch.object(host, "UNIT", root / "service"), patch.object(
                host, "run"
            ) as run, patch.object(host.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
                host.start_stack()
            self.assertEqual(env.read_text(), "DD_ADMIN_PASSWORD=keep-existing-password\n")
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)
            commands = [call.args for call in run.call_args_list]
            self.assertNotIn(("python3", "init-env.py"), commands)
            self.assertIn(("docker", "compose", "up", "-d"), commands)
            self.assertFalse(any("down" in command or "--volumes" in command for command in commands))
            self.assertIn("TimeoutStartSec=900", (root / "service").read_text())

    def test_readiness_timeout_prevents_integration_setup(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(host, "HOST", Path(temp)), patch.object(
            host, "install_runtime"
        ), patch.object(host, "start_stack"), patch.object(
            host, "wait_http", side_effect=RuntimeError("not ready")
        ), patch.object(host, "provision_integration") as provision:
            with self.assertRaisesRegex(RuntimeError, "not ready"):
                host.setup("us-east-1", "ci", "admin")
            provision.assert_not_called()

    def test_http_wait_requires_success_and_stops_on_deadline(self):
        with patch.object(host.time, "monotonic", side_effect=[0, 0, 2]), patch.object(
            host.time, "sleep"
        ), patch.object(host.urllib.request, "urlopen", side_effect=OSError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "integration setup was not attempted"):
                host.wait_http(timeout=1)

    def unpack_recovery(self, root):
        commands = config.build_commands(OUTPUTS)
        script = commands[3].split("\n", 1)[1].rsplit("\nSECURETASK_ASSETS", 1)[0]
        script = script.replace("'/opt/securetask-dojo'", repr(str(root)))
        exec(compile(script, "recovery-assets", "exec"), {})
        return commands

    def test_recovery_restores_missing_bootstrap_files_and_valid_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            commands = self.unpack_recovery(root)
            for name in ["docker-compose.yml", "init-env.py", "provision.py", "setup-host.py"]:
                self.assertEqual((root / name).read_bytes(), (ROOT / "dojo" / name).read_bytes())
            self.assertEqual(subprocess.run(["sh", "-n"], input="\n".join(commands), text=True).returncode, 0)
            self.assertIn("recovering the project bootstrap", commands[2])
            self.assertLess(len(json.dumps(commands)), 24000)

    def test_recovery_does_not_overwrite_installed_compose_or_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docker-compose.yml").write_text("keep installed image versions\n")
            (root / ".env").write_text("private existing credentials\n")
            self.unpack_recovery(root)
            self.assertEqual((root / "docker-compose.yml").read_text(), "keep installed image versions\n")
            self.assertEqual((root / ".env").read_text(), "private existing credentials\n")

    def test_cloud_init_payload_is_valid_shell_and_below_ec2_limit(self):
        template = (ROOT / "infra/platform/dojo-user-data.sh").read_text()
        values = {
            key: base64.b64encode(gzip.compress((ROOT / "dojo" / name).read_bytes(), mtime=0)).decode()
            for key, name in {"compose": "docker-compose.yml", "init_env": "init-env.py", "provision": "provision.py", "setup_host": "setup-host.py"}.items()
        }
        values.update(region="us-east-1", integration_secret_arn=OUTPUTS["dojo_integration_secret_arn"]["value"], admin_secret_arn=OUTPUTS["dojo_admin_secret_arn"]["value"])
        rendered = re.sub(r"\$\{([a-z_]+)\}", lambda m: values[m.group(1)], template)
        self.assertNotIn("${", rendered)
        self.assertLessEqual(len(rendered.encode()), 16384)
        self.assertEqual(subprocess.run(["bash", "-n"], input=rendered, text=True).returncode, 0)

    def test_failed_ssm_output_identifies_stage_and_hides_credentials(self):
        payload = {
            "Status": "Failed", "ResponseCode": 100,
            "StandardOutputContent": "[Dojo setup] Checking package sources\nDD_ADMIN_PASSWORD=private-value",
            "StandardErrorContent": "E: Package docker-compose-v2 has no installation candidate\npostgres://user:private-db-password@host/db",
        }
        result = SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        with patch.object(wait.subprocess, "run", return_value=result):
            with self.assertRaises(RuntimeError) as error:
                wait.wait_setup("i-123", "command-123")
        message = str(error.exception)
        self.assertIn("Checking package sources", message)
        self.assertIn("no installation candidate", message)
        self.assertIn("i-123", message)
        self.assertIn("command-123", message)
        self.assertNotIn("private-value", message)
        self.assertNotIn("private-db-password", message)

    def test_eventual_consistency_and_running_status_are_retried(self):
        results = [
            SimpleNamespace(returncode=1, stderr="InvocationDoesNotExist"),
            SimpleNamespace(returncode=0, stdout='{"Status":"InProgress"}'),
            SimpleNamespace(returncode=0, stdout='{"Status":"Success","ResponseCode":0}'),
        ]
        with patch.object(wait.subprocess, "run", side_effect=results) as run, patch.object(wait.time, "sleep"):
            wait.wait_setup("i-123", "command")
        self.assertEqual(run.call_count, 3)

    def test_success_status_requires_zero_response_code(self):
        for code in [1, None]:
            with self.subTest(code=code), patch.object(wait.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps({"Status": "Success", "ResponseCode": code})
            )):
                with self.assertRaises(RuntimeError):
                    wait.wait_setup("i-123", "command")


if __name__ == "__main__":
    unittest.main()
