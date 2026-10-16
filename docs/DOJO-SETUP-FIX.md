# DefectDojo setup recovery — 15 October 2026

The supplied workflow log shows **45 resources added, 0 changed, 0 destroyed**. Terraform completed successfully; the later DefectDojo setup step failed. Keep the existing Terraform state and installation.

## Cause

The EC2 boot log showed that Ubuntu's regional HTTP package mirror timed out. APT continued with incomplete package indexes, then failed with:

```text
E: Package 'docker-compose-v2' has no installation candidate
```

Cloud-init stopped before writing the Dojo setup files. The previous SSM command checked for those files and exited without showing the original package error.

## Install this patch

1. Extract `SecureTask-Dojo-Fix.zip` into a temporary folder. It contains project-relative paths, including the hidden `.github` folder.
2. Copy the extracted files into the matching folders in your existing GitHub project. Replace the listed files and add the new files. Keep the rest of your project. In particular, ensure `dojo/setup-host.py` is present and both workflow files were copied.
3. Commit and push the changes to `main` using your IDE or normal Git workflow. In GitHub, open `dojo/setup-host.py` on `main` to confirm the update reached the repository.
4. Open **Actions > Provision AWS infrastructure > Run workflow**. Select `main` and enter the **same AWS account ID** used for the failed run. Start a new run; **Re-run failed jobs** would still use the previous commit.
5. Approve the `infrastructure` environment for planning. Review the fresh Terraform plan before approving apply. For this repair, the existing Dojo instance should be retained. Unexpected resource replacements need investigation before approval.
6. Approve apply. Let **Wait for DefectDojo and configure its private integration** complete. The workflow repairs the existing host through SSM; no SSH or local Terraform commands are required.

This patch has not been executed against your AWS host by the assistant. Your new workflow run performs the recovery.

Local validation passed: 50 Python tests, GitHub Actions workflow linting, Terraform formatting, and platform configuration validation. These checks cover recovery payloads, state-preserving setup, readiness failures, and SSM error reporting; AWS recovery still needs to complete in your workflow.

## What changed

- A shared `dojo/setup-host.py` handles both first boot and recovery. It changes Ubuntu package sources to canonical HTTPS mirrors, forces IPv4 for APT, retries downloads, and stops immediately if package-index refresh fails.
- The recovery command restores missing project setup files. Existing `.env` credentials, the installed Compose definition, and Docker data volumes are preserved. It does not run `docker compose down` or delete volumes.
- Cold-start timeouts now allow more time for image downloads and database initialization. The login page must respond successfully before integration setup begins.
- Failed SSM setup now reports its command ID, instance ID, response code, and diagnostic output with common credential formats redacted. It no longer hides cloud-init failures.
- User-data assets are compressed to stay within EC2's 16 KiB user-data limit. Existing instances are repaired by the SSM step; changing user data alone would not repair this installation.
- The unsupported `allowed-account-ids` action input was removed. Bootstrap and decommission already check the authenticated account; the apply step now explicitly checks AWS STS identity too.

## Verify the result

The setup log should reach these stages in order:

```text
[Dojo setup] Checking package sources and Docker prerequisites
[Dojo setup] Starting the existing Dojo stack; preserving its data
[Dojo setup] Waiting for the local login page
[Dojo setup] Creating product, scanner tests and integration account
[Dojo setup] Storing private integration credentials in Secrets Manager
[Dojo setup] Private DefectDojo integration is ready
Private DefectDojo and its integration are ready
```

The next workflow step publishes AWS outputs as GitHub variables. Follow Chapter 6 of `docs/PROJECT-BOOK.md` to open the Dojo dashboard through Session Manager, then continue with **Secure release**.

If setup still fails, open the SSM command identified in the new log under **AWS Systems Manager > Run Command**, region **us-east-1**. For first-boot errors, also open **EC2 > Instances > select the Dojo instance > Actions > Monitor and troubleshoot > Get system log**. Check the first failing setup stage. Continued HTTPS or registry timeouts require checking the private subnet's NAT/outbound path. Keep passwords, API tokens, and `.env` contents out of shared logs.

Do not delete Terraform state or run decommission to repair this startup error. Decommission remains a separate, manually triggered workflow for when you intend to remove the project.

## Patch files

```text
.github/workflows/infrastructure.yml
.github/workflows/decommission.yml
dojo/setup-host.py                         NEW
infra/platform/dojo-user-data.sh
infra/platform/dojo.tf
scripts/configure-dojo-host.py
scripts/wait-dojo.py
tests/dojo_setup_test.py                    NEW
docs/PROJECT-BOOK.md
docs/DOJO-SETUP-FIX.md                      NEW
```
