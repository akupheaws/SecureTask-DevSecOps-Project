# Infrastructure security checks before provisioning

The **Provision AWS infrastructure** workflow now checks the real Terraform configuration before it authenticates to AWS or creates the state bucket. A failed Checkov policy prevents bootstrap, planning, and apply. The resolved platform plan is checked again before apply becomes available.

## The two infrastructure challenges

The tutorial starts with two deliberately incorrect settings in the real Terraform files. They are marked `VIDEO CHALLENGE`.

| Checkov policy | Setting to fix |
| --- | --- |
| CKV2_AKUPHE_1 | In `infra/bootstrap/main.tf`, change `block_public_policy = false` to `true` in `aws_s3_bucket_public_access_block.state`. The other three public-access protections must also stay `true`. |
| CKV2_AKUPHE_2 | In `infra/platform/main.tf`, change `storage_encrypted = false` to `true` in `aws_db_instance.main`. This setting covers both staging and production databases. |

The custom policies are in `security/checkov/` and have High severity. They run alongside Checkov's built-in checks. A built-in check may report the same underlying misconfiguration too; this is two infrastructure issues, rather than a promise of exactly two report rows.

## Record the failure and correction

1. Push the complete updated project to `main`, including `.github/workflows/infrastructure.yml`, `scripts/`, and `security/checkov/`.
2. Open **Actions > Provision AWS infrastructure > Run workflow**, select `main`, and enter the AWS account ID.
3. Open **Check Terraform before any AWS provisioning**. Show the failed policy step and both custom policy IDs. The **infrastructure-preflight-security** artifact contains raw findings, normalized findings, and scanner status. Later provisioning jobs are skipped.
4. In your IDE, fix the two settings listed above. Keep both policies enabled; do not remove resources or suppress checks to pass the demonstration.
5. Commit and push the corrections. Start a **new** Provision AWS infrastructure run. Re-running the old job uses its original vulnerable commit.
6. The preflight policy should pass. Review and approve planning/bootstrap, then review the resolved plan's Checkov evidence and approve apply as described in Chapter 5 of the Project Book.

Fixing only one issue leaves the other blocking. Human approval does not override a failed job dependency. Existing AWS resources are not deleted by a failed preflight; the workflow simply does not proceed with that provisioning run.

## Four issues across the video

| Stage | Issue | Where to show it |
| --- | --- | --- |
| Before infrastructure provisioning | S3 public-access protection disabled | GitHub Actions Checkov reports |
| Before infrastructure provisioning | RDS storage encryption disabled | GitHub Actions Checkov reports |
| Before the application image build | SQL injection exercise | DefectDojo Semgrep test |
| Before the application image build | Unsafe eval exercise | DefectDojo Semgrep test |

On the first installation, DefectDojo does not exist while infrastructure provisioning is blocked. Use the Actions reports for the first two issues. After fixing them and provisioning Dojo, follow Chapter 8 for the two source-code exercises and their mitigation history. Existing corrected source exercises are preserved; Chapter 8 shows how to prepare their vulnerable starting versions for recording.

## Verified behavior

Checkov 3.3.26 was run locally against the actual Terraform source and a corrected temporary copy. Both custom checks failed in the starting configuration; fixing only S3 still blocked; fixing S3 and RDS removed the blocking infrastructure findings under the project policy. Passing and failing Terraform-plan examples were checked too. No Terraform apply or AWS deployment was run for this change.

The policy mechanism follows [Checkov custom YAML policies](https://www.checkov.io/3.Custom%20Policies/YAML%20Custom%20Policies.html). The project collects findings first, then fails its policy gate; execution errors and missing policy files also block.
