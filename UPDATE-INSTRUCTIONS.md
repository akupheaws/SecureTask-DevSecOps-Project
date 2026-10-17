# Apply this README update to your existing project

This package contains documentation and architecture images. Use the repository you already have on your computer.

## 1. Copy the files

Open your existing project root—the folder that already contains `.git`, `docker-compose.yml`, and `Dockerfile`.

Copy these files into it, preserving their paths:

```text
README.md
docs/assets/architecture/SecureTask-AWS-Architecture.png
docs/assets/architecture/SecureTask-AWS-Architecture.svg
docs/assets/architecture/CREDITS.md
```

Replace the existing `README.md`. If `docs/assets/architecture/` is missing, create those directories. If the directories already exist, merge the new files into them and keep their other contents.

Keep the README and diagram files together so the embedded architecture image renders on GitHub. The README's links to `docs/PROJECT-BOOK.md`, `docs/INFRASTRUCTURE-SECURITY-DEMO.md`, and `docs/architecture.md` refer to guides already in your project.

## 2. Preview the result

Open `README.md` in your editor's Markdown preview. Confirm that the architecture diagram displays and that the existing project-guide links work.

## 3. Commit and push

Run these commands from your existing project root:

```bash
git diff -- README.md
git add README.md docs/assets/architecture/SecureTask-AWS-Architecture.png docs/assets/architecture/SecureTask-AWS-Architecture.svg docs/assets/architecture/CREDITS.md
git commit -m "docs: refresh README with architecture and local setup"
git push
```

Use your already authenticated terminal or IDE. `git push` publishes to your current branch's configured upstream. No repository creation or additional GitHub CLI setup is needed for this update.

`UPDATE-INSTRUCTIONS.md` is a handoff guide; it does not need to be copied into the project or committed.

## 4. Run the application locally

Start Docker Desktop, open your existing project root in a terminal, and run:

```bash
docker compose up --build -d
```

Open **http://127.0.0.1:3000**. The replacement README contains the readiness check, log commands, and local troubleshooting.
