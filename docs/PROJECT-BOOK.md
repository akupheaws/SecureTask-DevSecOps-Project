# Secure Task By Akuphe

## Build, scan, approve, deploy, and decommission through GitHub Actions

A practical AWS DevSecOps project book. Edition 2.4. October 16, 2026.

**Follow the chapters in order.** This edition uses GitHub Actions for the first AWS deployment, infrastructure updates, application releases, and teardown. The region is `us-east-1`. You trigger every workflow manually.

The short route is: create a repository, push this project, add repository secrets, run **Provision AWS infrastructure**, then run **Secure release**. No local Terraform setup is needed.

### What you will build

Secure Task By Akuphe is a React and Express application with PostgreSQL. Terraform creates AWS networking, ECR, an ECS cluster for Fargate services, Application Load Balancers (ALBs), RDS databases, logging, and a private DefectDojo server. Open-source Trivy scans the built Docker image before ECR publishing. Seven scanners feed the security process. Approval gates let you review before a Docker build or production deployment. The video demonstrates four issues across two stages: S3 public-access protection and RDS encryption block infrastructure provisioning, then SQL injection and unsafe eval block the application release. Fix each stage before proceeding.

### Read this before starting

- Use a dedicated AWS sandbox account and a dedicated IAM provisioning user, with access keys that can create and delete the project resources. Keep AWS credentials and GitHub tokens off camera.
- Have a GitHub account and authenticate Git from your terminal or IDE. The repository must be public for the required reviewer gates used by this tutorial on GitHub Free.
- Use test accounts and synthetic data. The application uses an AWS-generated HTTP load balancer URL; a custom domain is not required.
- The checked-in tutorial starts with two marked infrastructure settings that Checkov rejects. Fix them in Chapter 5 before provisioning can proceed.
- Chapter 5 creates chargeable resources. Chapter 10 permanently deletes the project infrastructure and data. Previously incurred charges remain payable.
- When switching from the old laptop-bootstrap Edition 1, finish its teardown before using this pipeline bootstrap. For an existing Edition 2 installation, push the updated source and rerun Provision AWS infrastructure to refresh the Dojo integration and add its remediation tests.

### Contents

1. Prepare your accounts and tools
2. Open the project and optionally run it locally
3. Create your repository and push the code
4. Add the repository secrets
5. Provision AWS through the workflow
6. Open DefectDojo
7. Run the source checks
8. Demonstrate security findings and approval
9. Release and update the application
10. Decommission through the workflow
11. Fix common problems
12. Record your YouTube demonstration

# 1. Prepare your accounts and tools

**Where:** your laptop and the AWS/GitHub websites.

For deployment, you need a GitHub account, an AWS sandbox account, and Git or an IDE that can push your code. Terraform, Python, Node, and the deployment tools run on GitHub-hosted runners.

Docker Desktop is needed only if you want the optional local application preview in Chapter 2. The AWS CLI and Session Manager plugin are needed only for the private DefectDojo browser connection in Chapter 6.

Have your AWS account's 12-digit ID ready. You can see it in the AWS console account menu. The workflow checks it against the credentials you provide before creating resources.

You must be able to administer your GitHub repository. Use your personal account as the repository owner for this walkthrough; the pipeline will configure you as the reviewer.

**Checkpoint:** you have an AWS account ID, GitHub access, and an authenticated way to push code. You do not need to run `terraform init`, `terraform plan`, or `terraform apply` on your laptop.

# 2. Open the project and optionally run it locally

**Where:** Finder or your file manager, then your IDE.

Find **SecureTask-Updated-Project.zip** on your Desktop. Extract it into a fresh folder, such as `securetask-pipeline-lab`. Open its `securetask-devsecops` folder in your IDE.

**Expected result:** you see `frontend`, `backend`, `infra`, `scripts`, `docs`, `Dockerfile`, and the hidden `.github` folder. Push the entire project, including `.github/workflows`.

## 2.1 Optional local preview

Start Docker Desktop. From a terminal in the project folder, run:

```bash
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:3000/health/ready
```

If the readiness command initially fails, wait for the containers to start and retry it.

**Expected result:** the health response is `{"status":"ready"}`. Open `http://127.0.0.1:3000`, register a test account with a password of at least 12 characters, create a project, and add a task.

Local data stays local. It is not copied into AWS. You may skip this preview and go directly to Chapter 3.

# 3. Create your repository and push the code

**Where:** GitHub in your browser, then your terminal or IDE.

**Prerequisite:** you have a GitHub account and Git is authenticated from your terminal or IDE. Complete authentication privately before recording.

## 3.1 Create an empty repository

In GitHub, select **New repository**:

1. Choose your personal account as owner.
2. Enter a repository name of your choice, such as `securetask-devsecops`.
3. Choose **Public**.
4. Leave the README, .gitignore, and license options unselected.
5. Click **Create repository**.

The source already contains its project files. An empty remote avoids conflicting Git histories.

## 3.2 Push the project

Use your IDE's publish/push feature, or run the following from the extracted project folder. Replace `YOUR-USERNAME` and `YOUR-REPOSITORY` with the values you chose:

```bash
git init -b main
git remote add origin \
  https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git add .
git commit -m 'Add Secure Task By Akuphe'
git push -u origin main
```

**Expected result:** your code and `.github/workflows` appear on the repository's `main` branch. The push does not start a workflow.

If Git reports an unknown author identity, configure your Git name and email using your IDE or the commands in Chapter 11, then repeat the commit.

**Checkpoint:** open the repository's **Actions** tab. You should see **Provision AWS infrastructure**, **Manual source checks**, **Record security challenges**, **Secure release**, and **Decommission all project infrastructure**.

# 4. Add the repository secrets

**Where:** GitHub and AWS in your browser. Never record secret values.

## 4.1 Prepare the AWS provisioning credentials

Use a dedicated IAM user in your sandbox account. It needs permissions for S3, IAM runtime roles, networking, ECS, ECR, RDS, load balancing, logs, Secrets Manager, and Systems Manager, including deletion.

For this dedicated sandbox, `AdministratorAccess` is the straightforward setup. It grants broad account access. Keep repository administrators trusted and deactivate the key after teardown. Do not use root-user keys.

In the AWS console, open **IAM > Users > your provisioning user > Security credentials > Create access key**. Follow the displayed options for credentials used outside AWS, and save the key privately. If you already have suitable dedicated keys, use them.

## 4.2 Prepare the GitHub setup token

The workflow configures GitHub approval environments and variables. These API changes require a GitHub token.

In your GitHub account, open **Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token**:

1. Use your personal account as resource owner.
2. Select only the repository created in Chapter 3.
3. Set an expiration that covers your recording and cleanup.
4. Under repository permissions, grant **Administration: Read and write**, **Environments: Read and write**, and **Variables: Read and write**. Metadata read access is included automatically.
5. Generate the token and save it privately.

Provisioning uses this token to configure gates and publish outputs. The usual `GITHUB_TOKEN` cannot administer these repository settings.

## 4.3 Save three repository secrets

Open your repository's **Settings > Secrets and variables > Actions > Secrets > New repository secret**.

| Secret name | Value |
| --- | --- |
| AWS_ACCESS_KEY_ID | Your dedicated AWS access key ID |
| AWS_SECRET_ACCESS_KEY | Its matching secret access key |
| REPO_ADMIN_TOKEN | The repository-scoped GitHub token from Chapter 4.2 |

If using temporary AWS credentials instead, also add `AWS_SESSION_TOKEN` and ensure the credentials remain valid for the entire run. Leave that secret absent when using an IAM user's access key pair.

Do not put these values in repository variables, source files, `.env` files, screenshots, or comments.

**Checkpoint:** GitHub lists the three secret names. You do not need to create the state bucket, IAM workflow roles, repository variables, or approval environments manually.

# 5. Provision AWS through the workflow

**Where:** the GitHub Actions tab. **This chapter starts chargeable AWS resources.**

## 5.1 Start the workflow

Open **Actions > Provision AWS infrastructure > Run workflow**. Select `main`, enter your 12-digit AWS account ID, and click **Run workflow**.

The first job is **Check Terraform before any AWS provisioning**. It scans all real Terraform roots with Checkov and the custom policies in `security/checkov/`. This job has no AWS credentials. It must pass before the workflow checks secrets, creates approval environments, or bootstraps S3.

The tutorial intentionally starts with two incorrect settings marked `VIDEO CHALLENGE`. The initial run should fail this job:

| Policy | Real Terraform configuration to correct |
| --- | --- |
| CKV2_AKUPHE_1 | In `infra/bootstrap/main.tf`, set `block_public_policy = true` for `aws_s3_bucket_public_access_block.state`. Keep all four public-access protections enabled. |
| CKV2_AKUPHE_2 | In `infra/platform/main.tf`, set `storage_encrypted = true` for `aws_db_instance.main`. This covers staging and production RDS databases. |

Show both policy IDs in the failed job and open its **infrastructure-preflight-security** artifact. Built-in Checkov checks may also report the same underlying settings. The later provisioning jobs are skipped; a failed preflight creates no AWS resources. Existing resources from an earlier deployment are not removed.

Fix both settings in your IDE, commit, and push. Start a **new Provision AWS infrastructure** run at the corrected `main` commit with the same account ID. Re-running the old job still checks its original commit. Keep the policies enabled; correct the Terraform values.

After preflight passes, the `configure` job checks the secrets and creates the approval environments, with your personal GitHub account as the required reviewer. It allows deployment only from `main`.

DefectDojo is created later during apply. On the first installation, show these infrastructure findings in GitHub Actions; the two source findings in Chapter 8 will be shown in Dojo. See [Infrastructure security demonstration](INFRASTRUCTURE-SECURITY-DEMO.md) for the short recording checklist.

When the `plan` job waits for approval, click **Review deployments**, select `infrastructure`, and approve. This first approval permits bootstrap and planning. It may create the state bucket, but it does not deploy the application platform yet.

## 5.2 What the workflow does

After the infrastructure preflight policy passes, the runner authenticates to AWS using your repository secrets and confirms the account ID.

It checks for `securetask-state-ACCOUNT_ID` in `us-east-1`. If missing, Terraform creates the bucket with public access blocked, encryption, versioning, and a TLS-only policy. If present, the workflow verifies project ownership, restores the bootstrap snapshot, and reuses it. An unrelated bucket is rejected.

The workflow then initializes the platform's S3 backend with state locking and creates a Terraform plan. Checkov scans the resolved plan with the same custom policies, and the project's security policy must pass before apply becomes available. Approval cannot override a failed dependency.

**Expected result:** the `plan` job succeeds, and the `apply` job waits for approval. Read the plan log and the `infrastructure-security` report artifact before approving.

## 5.3 Approve the platform plan

Click **Review deployments**, select `infrastructure`, and approve the waiting `apply` job.

It applies the saved plan to create the VPC, subnets, NAT gateway, runtime IAM roles, ECR registry, ECS cluster, two ALBs, staging and production RDS databases, CloudWatch logs, Secrets Manager entries, and the private DefectDojo host.

It waits for DefectDojo, provisions its product and integration, confirms the private secrets were stored, and publishes Terraform outputs into GitHub repository/environment variables automatically.

The ECS services are created later by the first release, when a scanned Docker image exists. The application URL can return HTTP 503 until that release finishes.

**Expected result:** the workflow succeeds. Its summary shows the AWS-generated production URL, staging URL, state bucket, Dojo instance ID, and administrator secret ARN. No password or API token appears in the summary.

**Checkpoint:** under **Settings > Environments**, verify reviewers are present for `infrastructure`, `security-review`, `demo-review`, `production`, and `decommission`. Under **Secrets and variables > Actions > Variables**, verify `TF_STATE_BUCKET`, `ECR_REPOSITORY_URL`, and `DOJO_INSTANCE_ID` exist.

## 5.4 Reruns and recovery

For updates, push your changes and run this same workflow. Review and approve the new plan; existing state stays in S3.

If setup fails, keep state intact. Fix the first error and rerun, or decommission using Chapter 10. Teardown derives the bucket from your account ID when variables are missing.

If Terraform reports a successful apply but **Wait for DefectDojo and configure its private integration** fails, the infrastructure already exists. A failed workflow does not roll it back.

For the Ubuntu mirror failure (`docker-compose-v2 has no installation candidate`), use the updated project files, including `dojo/setup-host.py`. Push them to `main`, then start a **new** Provision AWS infrastructure run with the same AWS account ID. Review the plan and approve as usual. The workflow restores missing Dojo setup files and retries setup on the existing host while preserving its `.env` credentials, installed Compose definition, and database volumes. It uses HTTPS Ubuntu mirrors, IPv4, and package-download retries.

Do not use **Re-run failed jobs** on the old run: it checks out the old commit. Do not delete the state bucket or recreate the installation to fix this error. See [Dojo setup recovery](DOJO-SETUP-FIX.md) for the patch installation steps and verification.

# 6. Open DefectDojo

**Where:** AWS console and one local terminal. Infrastructure and Dojo setup are already finished by the workflow.

The provisioning workflow installs self-hosted **DefectDojo Community Edition** on the private EC2 instance using Docker Compose. It creates your product, scanner tests, and CI API account automatically and stores credentials in Secrets Manager. No separate DefectDojo registration is needed. Its open-source software has no subscription charge; AWS hosting resources still incur costs.

DefectDojo stores and tracks scanner findings. The scanners perform the tests; DefectDojo provides the dashboard and remediation history. Viewing the private dashboard uses the encrypted Session Manager tunnel below.

## 6.1 Make the browser connection

Install AWS CLI v2 and the Session Manager plugin if needed. On macOS with Homebrew:

```bash
brew install awscli
brew install --cask session-manager-plugin
```

Authenticate the AWS CLI with an existing AWS profile that can start an SSM session. If none exists, run `aws configure` privately once and choose `us-east-1`. An IAM Identity Center profile can be used instead.

Copy the Dojo instance ID from the provisioning workflow summary. Replace `YOUR-DOJO-INSTANCE-ID` below with that exact value:

```bash
aws ssm start-session --region us-east-1 \
  --target YOUR-DOJO-INSTANCE-ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["18080"]}'
```

If your profile is not `default`, add `--profile YOUR-PROFILE` to that command.

Leave the tunnel running. Open `http://127.0.0.1:18080` in your browser.

## 6.2 Sign in

In AWS Secrets Manager in `us-east-1`, open the exact administrator secret ARN shown in the workflow summary. Use **Retrieve secret value** privately. Sign in to Dojo using its stored username and password.

**Expected result:** the product **Secure Task By Akuphe** exists. The workflow has already created the separate CI integration account; you do not copy administrator credentials into GitHub.

**Checkpoint:** you can view Dojo. Keep the tunnel open when reviewing findings. Close it with Ctrl+C when finished.

# 7. Run the source checks

**Where:** GitHub Actions.

Open **Actions > Manual source checks > Run workflow**, select `main`, and start the run.

| Tool | Coverage |
| --- | --- |
| Semgrep | Source code security patterns |
| Gitleaks | Accidental secrets in Git history |
| OSV-Scanner | Dependency vulnerabilities |
| Checkov | Terraform configuration |
| Hadolint | Source checks: Dockerfile practices |
| Trivy | Secure release: vulnerabilities in the built Docker image |
| ZAP | Secure release: running staging application |

**Expected result:** application tests and all five source/configuration scan jobs succeed. Each scan uploads a report artifact. Missing evidence, scanner errors, secrets, Critical findings, and unexcepted High findings block the relevant policy check.

The table shows all seven project scanners. Manual source checks runs the first five. Secure release also runs Trivy after Docker build and ZAP after staging deployment. Source-only scan jobs receive no AWS credentials. Release reports go to Dojo before their policy/approval gates.

The separate **Record security challenges** workflow is an optional isolated approval/rejection exercise. Chapter 8 uses Secure release for the full remediation and deployment recording.

**Checkpoint:** source checks pass. If a job is red, open its report, fix the cause, push the correction, and manually run the checks again.

# 8. Find two issues, fix the code, and rescan

**Where:** GitHub Actions, DefectDojo, and your IDE. Provisioning must have succeeded and your Dojo tunnel must be open.

Use the **Secure release** workflow for this story. Its optional `include_remediation_demo` checkbox adds two controlled source exercises to the Semgrep scan. The exercises are excluded from the Docker image and are never imported by the application. The other four source scanners still scan their normal targets.

## 8.1 Produce the two findings

Your working copy may already contain the fixes from an earlier recording. For another before-fix scene, replace only these two scan-only exercise functions in your IDE with the original examples below. Keep them excluded from the application and image.

Original function in `security/demo/unsafe-search.ts`:

```typescript
export async function unsafeSearch(db: any, search: string) {
  return db.query(`SELECT * FROM tasks WHERE title LIKE '%${search}%'`);
}
```

Original function in `security/demo/unsafe-expression.ts`:

```typescript
export function unsafeNumber(input: string): number {
  return eval(input);
}
```

Commit and push that exercise starting state before starting the first scan. Apply the fixes in Chapter 8.3 before approving a release. The updated source ZIP preserves your working copy's existing fixes; it does not reset them automatically.

Open **Actions > Secure release > Run workflow**, select `main`, enable **include_remediation_demo**, and start the run.

The source scanners run before the Docker build. A scanner can finish successfully while reporting findings. The reporting job uploads those reports to Dojo first, then the source policy blocks the release because of the two High findings.

**Expected result:** the reporting/policy job is red and the Docker build is skipped. That is the intended first recording result; it proves vulnerable source does not reach the build approval gate.

## 8.2 Show the findings in DefectDojo

Open **Secure Task By Akuphe > Secure Task By Akuphe remediation > semgrep**. Show the active findings for these paths:

| Source file | Finding and correction |
| --- | --- |
| security/demo/unsafe-search.ts | SQL injection: interpolated input in a query. Correct it with a parameterized query. |
| security/demo/unsafe-expression.ts | Unsafe eval: input is evaluated as JavaScript. Correct it by parsing and validating a number. |

Explain each finding's severity, affected file, and risk. Show the corresponding commit/build information in Import History. If other source findings appear, review and fix their blocking conditions too.

## 8.3 Fix both files in your IDE

Replace `security/demo/unsafe-search.ts` with:

```typescript
// SCAN-ONLY EXERCISE. Excluded from the application and Docker image.
export async function unsafeSearch(db: any, search: string) {
  return db.query("SELECT * FROM tasks WHERE title LIKE $1", [`%${search}%`]);
}
```

The query text remains fixed; the search value is passed separately to PostgreSQL.

Replace `security/demo/unsafe-expression.ts` with:

```typescript
// SCAN-ONLY EXERCISE. Excluded from the application and Docker image.
export function unsafeNumber(input: string): number {
  const value = Number(input);
  if (!Number.isFinite(value)) throw new Error("Enter a finite number");
  return value;
}
```

This converts numeric input without evaluating JavaScript. Keep both files present so the next scan examines the corrected code.

Commit and push the changes using your IDE, or from the project folder:

```bash
git add security/demo/unsafe-search.ts security/demo/unsafe-expression.ts
git commit -m 'Fix SQL injection and unsafe eval exercises'
git push
```

**Checkpoint:** GitHub main contains the fixes. A push does not start the pipeline because all workflows are manually dispatched.

## 8.4 Rerun with the same scan scope

Start a **new Secure release run**, select `main`, and keep **include_remediation_demo enabled**. Do not rerun the old failed job: that old run is tied to its original vulnerable commit. Do not uncheck the option to make the findings disappear.

The new run scans the same corrected files and reimports into the same Dojo Semgrep Test in the remediation engagement. Normal releases use a separate main engagement, so disabling the exercise option does not close remediation findings. The uploader enables Close Old Findings. Issues absent from the new report become inactive/mitigated, while Import History preserves the earlier evidence.

**Expected result:** the Semgrep test has zero active findings from the two exercise files. Show the two old findings as mitigated and the newer import as clean for those issues. Refresh after the import finishes if the dashboard has not updated yet.

Other tools may still report Medium/Low issues or new dependency vulnerabilities. Zero active demonstration issues and a passing blocking policy do not mean the application has no possible vulnerabilities.

## 8.5 Approve and continue the same release

When source policy passes, the workflow waits at `security-review`. Review the clean source results in Dojo and GitHub, then approve. The same run continues to Docker build, Trivy image scan, image policy, ECR publication, staging Fargate deployment, ZAP, production approval, and production deployment as described in Chapter 9.

**Checkpoint:** the clean rescan reaches approval; the original failed run never built or pushed an application image.

# 9. Release and update the application

**Where:** GitHub Actions, Dojo, and your browser.

## 9.1 Start a release

If the corrected Chapter 8 run is waiting for approval, continue that run. For a normal release, open **Actions > Secure release > Run workflow**, select `main`, and start it. Leave the exercise option disabled for normal releases.

The workflow tests the application, runs the five source scanners, uploads their reports to Dojo, and checks the policy. When the `security-review` gate appears, inspect the findings and approve or reject it.

After approval, it builds a Docker image, scans it with Trivy, reports findings, and enforces image policy. It pushes that exact scanned image to ECR with a unique commit/run tag and records its immutable digest.

It deploys the digest to staging, initializes the database if necessary, runs health and application smoke checks, and scans staging with ZAP. Reports go to Dojo and runtime policy must pass.

**Expected result:** the run reaches the `production` approval gate after staging succeeds.

## 9.2 Container scanning before ECR

Trivy is the open-source image scanner, licensed under Apache 2.0. This project uses its standalone CLI in a pinned container; no paid scanner subscription is required. It examines OS packages and application dependencies inside the built image.

In the Actions run, look for **Build Docker image and scan with Trivy**, then **Report container findings and enforce image policy**, then **Push scanned image to Amazon ECR**.

The scanner saves JSON reports as the `image-security` artifact. Reporting uploads findings to DefectDojo, then image policy blocks missing/failed scans, Critical findings, and High findings without a valid exception. ECR publishing depends on successful build, reporting, and policy jobs.

The publisher loads the exported image that was scanned. It does not rebuild the image. Staging and production receive the resulting ECR digest.

**Checkpoint:** a blocking container finding stops the workflow before the ECR push.

## 9.3 ECS Fargate and the load balancer

Both application services use **ECS with Fargate**. Terraform specifies Fargate task compatibility and the Fargate service launch type. Application tasks run in private subnets without public IP addresses.

There are two public **Application Load Balancers**: one for staging and one for production. Each routes traffic to its environment's Fargate service and checks application health. The production ALB's AWS-generated DNS name is your final application endpoint.

```text
Browser -> Public ALB -> Private ECS Fargate tasks -> RDS
```

The private DefectDojo server runs on EC2; the web application runs on Fargate.

## 9.4 Inspect staging, then approve production

The **Deploy staging for inspection** job publishes an **Open staging application** link as soon as its deployment and smoke checks pass. You can inspect the app while ZAP is running.

After ZAP reporting and runtime policy pass, **Staging ready for your review** verifies that the GitHub production environment has a required reviewer. It publishes the staging link, the exact ECR image digest, and this inspection checklist:

1. Open staging using its full `http://` URL.
2. Register a test account or sign in.
3. Create a project and a task, change the task status, add a comment, and sign out.
4. Review the staging/ZAP results and Dojo findings.

The next job is **Approve production after staging inspection**. Its deployment uses the protected `production` environment and waits for your review. Production deployment starts only when that environment's approval is granted.

Return to the same GitHub Actions run, click **Review deployments**, select **production**, and click **Approve and deploy**. To stop the production release, choose **Reject**. Staging remains available after rejection.

**Expected result:** approving deploys the same scanned image digest you inspected in staging. Production smoke checks pass and the workflow publishes an **Open production application** link.

## 9.4.1 Apply this update to an existing repository

Commit and push the updated `.github/workflows/release.yml`, `.github/workflows/deploy.yml`, and `scripts/release_review.py`. Your existing infrastructure can be reused; these changes do not require a Terraform apply.

In **Settings > Environments > production**, confirm **Required reviewers** includes your GitHub account and save if needed. For this solo recording, leave **Prevent self-review** unchecked so you can approve a run you started. An approval gate is a repository setting; a workflow YAML file alone cannot create its reviewer requirement.

Start a **new Secure release** run after pushing. It uses the updated workflow. A rerun of an older execution uses the older commit.

**Checkpoint:** staging is deployed and checked, its URL is visible, and the production job is waiting for your approval. The review helper fails before production if no required reviewer is configured; it uses the workflow's read-only GitHub token and requires no additional secret.

## 9.5 Release an application update

Change the code, commit, and push using your IDE or Git. Then manually start **Secure release** again. A push itself does not run the pipeline.

If you change Terraform platform files, run **Provision AWS infrastructure** with the same account ID, review its plan, and approve apply. It reuses the state bucket and current infrastructure.

**Checkpoint:** the app works at the ALB URL. Every production update has passed the source, image, staging, runtime, and approval steps.

# 10. Decommission through the workflow

**Where:** GitHub Actions. No local Terraform command is needed.

This permanently removes staging and production application data, Dojo data, ECR images, infrastructure, database backups/snapshots, project logs, and every version in the project state bucket. Export anything you need first.

## 10.1 Start teardown

Finish or cancel other pending infrastructure, release, and demo runs. Open **Actions > Decommission all project infrastructure > Run workflow** and select `main`.

Enter your actual 12-digit AWS account ID and this exact confirmation:

```text
DESTROY securetask
```

The plan job authenticates with the repository AWS secrets and reviews the application, platform, and bootstrap states. Read its inventory before proceeding.

## 10.2 Approve the reviewed deletion

When the run pauses, click **Review deployments**, select `decommission`, and approve.

It rechecks that state has not changed since review, removes application services, disables deletion protection on reviewed resources, destroys the platform, cleans project data, empties the versioned state bucket, and destroys bootstrap last.

AWS credentials are external repository secrets. They remain valid throughout removal of project IAM roles and the backend bucket, so a separate cleanup IAM role is no longer required.

**Expected result:** the workflow succeeds and its `decommission-result` artifact contains `result.json` with `completed: true` and zero remaining-resource counts. The old application URL stops working.

A failed, cancelled, or timed-out run is not proof of complete cleanup. Fix the first error and rerun. Do not delete Terraform state manually.

## 10.3 Finish the tutorial

The GitHub repository, workflow artifacts, provisioning IAM user, and AWS service-linked roles remain outside the project. After successful teardown, deactivate/delete the dedicated AWS access key in IAM and remove the repository AWS secrets. Revoke the GitHub setup token when you no longer need it.

Close the Dojo tunnel with Ctrl+C. If you ran the local preview, stop it with:

```bash
docker compose down
```

This preserves the local database volume. Use `docker compose down --volumes` only when you also want to erase local test data.

**Final checkpoint:** the destroy result confirms zero project resources. For another installation, provide valid secrets and run the provisioning workflow again; you do not need local bootstrap state.

# 11. Fix common problems

| Problem | Fix |
| --- | --- |
| No workflows in Actions | Push the entire project, including the hidden .github folder, to main. Check that main is the default branch. |
| Git reports an unknown author | Set your name with `git config user.name "Your Name"` and email with `git config user.email "YOUR-EMAIL"`, then repeat the commit. |
| Git cannot push | Authenticate Git through your IDE or GitHub CLI. For CLI authentication, run `gh auth login` then `gh auth setup-git`. Use an empty remote for this walkthrough. |
| Missing repository secret | Add the exact secret name from Chapter 4 under Actions repository Secrets, then start a new run. |
| GitHub setup returns 403 | Check token expiry, selected repository, and Administration, Environments, and Variables write permissions. Replace REPO_ADMIN_TOKEN with a valid token. |
| GitHub setup returns 422 | Confirm the repository is public, main is the default branch, and the reviewer is a user with repository access. |
| AWS account mismatch | Check your entered account ID and the account that owns the repository AWS keys. No provisioning should continue with a mismatch. |
| AWS AccessDenied | Check the dedicated IAM user's permissions, permission boundaries, and organizational restrictions. Secrets do not grant permissions by themselves. |
| AWS credentials expired | Replace the repository secrets, including AWS_SESSION_TOKEN for temporary credentials, and start a new run. |
| State bucket ownership check fails | Confirm this repository owns that installation. Do not adopt another project's bucket or delete its contents. This edition expects a fresh installation. |
| Bootstrap snapshot is missing | Rerun provisioning. It can recover its correctly tagged bucket; it refuses unowned buckets. If state objects were manually deleted, restore a known-good private S3 version before making further changes. |
| Infrastructure preflight fails | Open infrastructure-preflight-security. Correct the marked S3 and RDS settings in Chapter 5.1, push, and start a new manual run. No bootstrap or AWS provisioning starts while this job is blocked. |
| The plan scanner or policy fails | Open infrastructure-security, fix the finding or scanner failure, commit/push, and rerun provisioning. The state bucket may already exist. |
| Terraform state is locked | Finish or cancel the other workflow using the state. Investigate a stale lock before releasing it; do not remove locks while a run is active. |
| Dojo startup fails | The updated workflow prints setup stages and the failing command's diagnostic output. For the Ubuntu mirror/package-index failure, follow Chapter 5.4 and [Dojo setup recovery](DOJO-SETUP-FIX.md). Otherwise inspect the identified command under Systems Manager > Run Command in us-east-1 and the EC2 system log. |
| Dojo tunnel cannot open | Check AWS CLI authentication, Session Manager plugin, SSM Online status, and whether local port 18080 is already used. |
| A workflow is queued | Finish or cancel the other AWS workflow. Infrastructure, release, demo, and decommission share a concurrency group. |
| Fixed findings stay active in Dojo | Start a new release at the corrected main commit, keep the exercise option enabled, confirm reporting succeeded, and refresh after reimport completes. Use the same remediation engagement and Semgrep Test. |
| Staging review says no required reviewer | In Settings > Environments > production, enable Required reviewers, select your account, save, and start a new release. For a solo recording, allow self-review. |
| Approval is unavailable | Inspect the earlier failed job or policy. A blocked policy prevents later approval. Verify required reviewers in Settings > Environments. |
| ALB returns HTTP 503 | Before the first release, this is expected. After a release, inspect ECS events, target health, and CloudWatch logs. |
| Decommission detects changed state | Start a new destroy run and review its fresh inventory. |
| Decommission partly fails | Read the first AWS error, correct permissions or the resource issue, and rerun while state still exists. Do not report successful cleanup without its verification result. |

A documented, reviewed exception in `security/policy.json` needs a tool, stable finding ID, approver, reason, and expiry date. Dojo accepted-risk notes do not override pipeline policy. Secrets and Critical findings always block. Fix real tutorial findings rather than weakening policy to get a green run.

# 12. Record your YouTube demonstration

## 12.1 Introduce the AWS services

Show the architecture before running workflows. Use this table to explain the services you can show in your AWS console:

| AWS service | Role in this project |
| --- | --- |
| Amazon S3 | Encrypted, versioned Terraform state, state locking, and the bootstrap snapshot. |
| Amazon VPC | Public/private subnets, routes, security groups, internet gateway, NAT gateway, and its Elastic IP. |
| Amazon ECR | Stores the scanned Docker image and its immutable digest. Basic scan-on-push is also enabled as an additional AWS check. |
| Amazon ECS and AWS Fargate | ECS manages the application services; Fargate runs their containers in private subnets. |
| Elastic Load Balancing: ALB | Separate public staging and production entry points, routing, and health checks. The production ALB supplies the final URL. |
| Amazon RDS for PostgreSQL | Separate private, encrypted staging and production application databases. |
| Amazon EC2 | Runs the private self-hosted DefectDojo Community Edition stack. |
| AWS Systems Manager | Private Dojo setup commands and encrypted Session Manager dashboard/reporting tunnels. |
| AWS Secrets Manager | RDS-managed database credentials and the Dojo administrator/API integration secrets. |
| AWS IAM | Runtime service roles and permissions. The provisioning user's keys are entered as GitHub secrets. |
| AWS STS | Confirms the AWS identity/account before provisioning or teardown. |
| Amazon CloudWatch | Application/database logs, ECS monitoring, and the ALB error alarm. |

Say: "Terraform provisions the cloud resources through GitHub Actions. Our app runs on ECS Fargate behind an ALB; DefectDojo runs privately on EC2."

## 12.2 Introduce the security tools and DefectDojo

The workflow uses community command-line scanners. Trivy image scanning does not require a paid subscription. Describe what each tool contributes:

| Tool or platform | Explain during the video |
| --- | --- |
| Semgrep | Source patterns such as SQL injection and unsafe eval. It detects our two remediation exercises. |
| Gitleaks | Secrets accidentally committed to Git history. |
| OSV-Scanner | Known vulnerabilities in application dependencies. |
| Checkov | Terraform configuration and resolved infrastructure plans. |
| Hadolint | Dockerfile practices, distinct from scanning the built image. |
| Trivy | OS and application dependency vulnerabilities inside the Docker image. |
| ZAP | Passive security checks against the running staging application. |
| DefectDojo Community Edition | Consolidates reports, tracks active and mitigated findings, and retains scan/import history. |

Say: "The scanners find issues. DefectDojo collects their reports. Pipeline policy blocks unacceptable findings, and GitHub approval gates control the build and production deployment."

## 12.3 Record the full remediation story

1. Introduce the application and explain the AWS services and security tools above.
2. Show the GitHub repository and secret names, keeping values private.
3. Run Provision AWS infrastructure with the two marked misconfigurations. Show Checkov blocking before AWS bootstrap, fix S3 public-access protection and RDS encryption, push, and start a fresh run. Review the bootstrap/plan approvals and the resolved plan scan before apply.
4. Show the resulting AWS resources, workflow summary, and automatically configured Dojo product.
5. Start Secure release with include_remediation_demo enabled.
6. Show source reports reaching Dojo, the two High findings, and policy stopping Docker build.
7. Open both exercise files in your IDE, explain the fixes, commit, and push.
8. Start a new Secure release at the corrected commit, keeping the same option enabled.
9. Show a clean Semgrep rescan, two mitigated findings, and Import History in the same Dojo test.
10. Approve security-review and show the Docker build, Trivy report, policy, ECR tag, and digest.
11. Explain that Fargate pulls the approved digest from ECR; show staging, ZAP, and health checks.
12. Open the staging link, inspect its project/task flow, show the waiting production job, approve production, then open its ALB URL.
13. Run decommission, review its inventory, approve, and show the zero-resource result.

Keep push and manual dispatch distinct on camera: the push saves the fix; Run workflow starts the new scan/build run. Use a fresh vulnerable source extraction for another recording. Do not revert the exercises while a corrected release is still running.

### Workflow reference

| Workflow name | Purpose |
| --- | --- |
| Provision AWS infrastructure | First-time bootstrap, infrastructure provisioning, and later updates |
| Manual source checks | Application tests and five source/configuration scanners |
| Record security challenges | Optional isolated approval/rejection exercise |
| Secure release | Scan, build, publish, stage, review, and deploy |
| Decommission all project infrastructure | Review and permanently remove the project |

### Validation status

Edition 2.4 adds Checkov policies to the real infrastructure provisioning path. Local Checkov 3.3.26 scans of the actual starting Terraform configuration fail both custom controls. Fixing only S3 still blocks; correcting S3 and RDS in a temporary copy removes the blocking infrastructure findings under the project policy. Passing and failing Terraform-plan examples were verified. Python policy/helper tests and workflow linting pass. These changes have not been run in GitHub Actions or applied to AWS by the assistant. You trigger deployment. Earlier application and scanner validation belongs to the preceding editions; a passing policy does not assert the absence of all possible vulnerabilities.

### Official references

- [Checkov custom YAML policies](https://www.checkov.io/3.Custom%20Policies/YAML%20Custom%20Policies.html)

- [DefectDojo Community Edition](https://docs.defectdojo.com/get_started/open_source/)
- [DefectDojo reimport and resolved-finding history](https://docs.defectdojo.com/import_data/import_intro/reimport/)

- [Trivy image scanning](https://trivy.dev/docs/latest/guide/target/container_image/)
- [Trivy Apache 2.0 license](https://github.com/aquasecurity/trivy/blob/main/LICENSE)

- [AWS credential action and repository-secret authentication](https://github.com/aws-actions/configure-aws-credentials)
- [Terraform S3 backend, encryption, and locking](https://developer.hashicorp.com/terraform/language/backend/s3)
- [GitHub environment permissions](https://docs.github.com/en/rest/deployments/environments)
- [GitHub repository/environment variable permissions](https://docs.github.com/en/rest/actions/variables)
- [GitHub manual dispatch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
- [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)
