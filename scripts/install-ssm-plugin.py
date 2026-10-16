import pathlib, json, urllib.request, hashlib, subprocess, tempfile

config = json.loads(
    (
        pathlib.Path(__file__).resolve().parents[1] / "security/ssm-plugin.lock.json"
    ).read_text()
)
data = urllib.request.urlopen(config["url"], timeout=60).read()
if hashlib.sha256(data).hexdigest() != config["sha256"]:
    raise SystemExit(
        "SSM plugin checksum changed. Review new official release and update lock; do not bypass verification."
    )
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / "plugin.deb"
    p.write_bytes(data)
    subprocess.run(["sudo", "dpkg", "-i", str(p)], check=True)
