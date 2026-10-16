# Secure Task By Akuphe Recording Rundown

Updated October 16, 2026. Use the full script for narration and this list to organize your shots. Spoken narration is approximately 14 to 16 minutes; demonstrations, approvals, and workflow waits add time.

| Scene | Show on screen | Key outcome |
| --- | --- | --- |
| 1 Introduction | Application preview, blocked infrastructure run, source findings | Explain why working code needs security evidence before production. |
| 2 Project rundown | Keep the architecture visible and trace each stage | Explain the app, AWS services, GitHub Actions, Terraform, and approval gates. |
| 3 Security tools | Seven logos and four issue labels | Explain each scanner, the four risks, and the concepts behind tool choice. |
| 4 Local application | Root Compose commands, readiness response, browser | Register, create a project/task, update status, refresh, and test sign-in. |
| 5 Infrastructure failure | Provision AWS infrastructure, Checkov job, report artifact | Show S3 public-access protection and RDS encryption blocking before bootstrap. |
| 6 Infrastructure correction | Real Terraform files, pushed fix, fresh run | Set both marked values to true; pass preflight and review the resolved plan. |
| 7 Provision and open Dojo | Plan/apply approvals, workflow outputs, private dashboard | Provision through the workflow and open Dojo over Session Manager. |
| 8 Source failure and fixes | Secure release with remediation enabled, Dojo Semgrep test, IDE | Show SQL injection and unsafe eval, then parameterize the query and validate the number. |
| 9 Rescan and build | Fresh run, same Dojo test, Import History, security-review approval | Show mitigation history before Docker build. |
| 10 Image and registry | Trivy report, image policy, ECR digest | Publish the exact scanned image only after image policy passes. |
| 11 Staging and production | Staging application, ZAP, review summary, production approval | Inspect staging, approve, and verify the same digest in production. |
| 12 Cleanup and closing | Decommission inventory/approval/result, then camera | Confirm verified cleanup and close with the key lesson and invitation to follow along. |

Before recording, prepare the vulnerable starting versions of the two scan-only source exercises using the full script's recording notes. The current source files may already contain their fixes. Keep the infrastructure preflight and every policy gate enabled. Initial infrastructure findings are shown in Actions because Dojo does not exist yet. Keep credentials off camera and announce success only after verification.
