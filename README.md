# Secure Task By Akuphe

A full-stack AWS DevSecOps project for your YouTube demonstration: React, Express, PostgreSQL, Docker, Terraform, ECR, ECS Fargate, Application Load Balancers, seven security tools, DefectDojo, manual approval gates, and reviewed decommissioning.

## Read the project book

- [Current project book](docs/PROJECT-BOOK.md)
- [Infrastructure failure and fix demonstration](docs/INFRASTRUCTURE-SECURITY-DEMO.md)

Follow its twelve chapters in order. It contains the complete setup, commands, expected results, approval steps, troubleshooting, and teardown. You do not need to assemble instructions from other guides.

The tutorial starts with two marked infrastructure misconfigurations. Checkov blocks **Provision AWS infrastructure** before AWS authentication or state-bucket bootstrap. Fix S3 public-access protection in `infra/bootstrap/main.tf` and RDS storage encryption in `infra/platform/main.tf`, push, and start a new manual run. The resolved platform plan is scanned again before apply. Together with the two source exercises in Chapter 8, this gives you four security issues across the recording. Earlier PDF books describe the preceding edition; use the current project book linked above for this workflow.

You run the deployment yourself. All user-facing workflows are manually dispatched. The target region is `us-east-1`; the application uses an AWS-generated ALB URL with no custom domain. First-time state-bucket bootstrap, all Terraform provisioning, application releases, infrastructure updates, and teardown run through manually triggered GitHub Actions workflows. Add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and REPO_ADMIN_TOKEN repository secrets, then run Provision AWS infrastructure. No local Terraform commands are needed.

The seven tools are Semgrep, Gitleaks, OSV-Scanner, Checkov, Hadolint, Trivy, and ZAP. Open-source Trivy scans the built Docker image for OS and application dependency vulnerabilities before ECR publishing; its findings go to DefectDojo and blocked image findings stop the push. ECS Fargate runs private application tasks behind public Application Load Balancers, with separate staging and production endpoints. The remediation walkthrough uses two scan-only source exercises (SQL injection and unsafe eval). Enable include_remediation_demo on Secure release, show the findings in DefectDojo, fix both files, push, and manually start a fresh release with the same option enabled. Clean reimports resolve the previous findings before approval, image scanning, and deployment. Demonstration fixtures are excluded from the application image and live Terraform. AWS resources incur charges when you create them. The book explains project teardown and removal of the externally managed credentials afterward.


The release deploys staging first, publishes its URL, and runs smoke/ZAP checks. **Staging ready for your review** verifies that production has a required reviewer and shows the inspection checklist. Inspect staging, then use **Review deployments > production > Approve and deploy** to promote the same image digest. Rejecting stops production and leaves staging available.

## Record the tutorial

The October 16 script covers the introduction, architecture rundown, local application, two infrastructure fixes, two source-code fixes, security tools, staging review, production approval, cleanup, and closing statement.

- [Color script PDF](docs/YOUTUBE-SECURITY-SCRIPT.pdf)
- [Editable Word script](docs/YOUTUBE-SECURITY-SCRIPT.docx)
- [Editable Markdown script](docs/YOUTUBE-SECURITY-SCRIPT.md)
- [Spoken teleprompter text](docs/YOUTUBE-TELEPROMPTER.txt)
- [Recording rundown](docs/YOUTUBE-RECORDING-RUNDOWN.md)
