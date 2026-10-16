#!/bin/bash
set -euo pipefail
mkdir -p /opt/securetask-dojo
cd /opt/securetask-dojo
# Compressed project-owned assets keep EC2 user data below its 16 KiB limit.
python3 - <<'ASSETS'
import base64,gzip,pathlib
assets = {
    'docker-compose.yml': '${compose}',
    'init-env.py': '${init_env}',
    'provision.py': '${provision}',
    'setup-host.py': '${setup_host}',
}
for name, data in assets.items():
    target=pathlib.Path(name)
    target.write_bytes(gzip.decompress(base64.b64decode(data)))
    target.chmod(0o644)
ASSETS
python3 setup-host.py --region '${region}' --integration-secret-arn '${integration_secret_arn}' --admin-secret-arn '${admin_secret_arn}'
