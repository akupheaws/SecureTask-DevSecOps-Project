import pathlib, secrets, os

path = pathlib.Path(__file__).resolve().parent / ".env"
if path.exists():
    raise SystemExit("Existing .env preserved")
values = {
    "DD_ADMIN_PASSWORD": secrets.token_urlsafe(32),
    "DD_SECRET_KEY": secrets.token_hex(32),
    "DD_CREDENTIAL_AES_256_KEY": secrets.token_hex(16),
    "DD_DATABASE_PASSWORD": secrets.token_urlsafe(32),
    "DD_ADMIN_USER": "admin",
}
path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
os.chmod(path, 0o600)
print("Created private Dojo configuration. Password is in dojo/.env; do not record it.")
