# Implementation verification

Target region: **us-east-1**. Deployment is now owned by you; follow [deploy-yourself.md](deploy-yourself.md).

## Completed checks

- TypeScript check and production application build passed.
- Six PostgreSQL-backed application tests passed: authentication, CSRF header, ownership, SQL injection input, comments/activity/admin authorization, and session invalidation.
- Eight report/policy/deployment tests passed, including missing evidence, malformed reports, exceptions, secret blocking, ECS rollback detection, and rollback on smoke failure.
- All three Terraform roots validated and formatted; provider locks include Linux amd64 and macOS arm64.
- GitHub workflow syntax checked with actionlint 1.7.12.
- All seven pinned scanner images executed successfully.
- Clean source/configuration scan: 54 findings eligible for manual review, zero policy blockers. Semgrep/Gitleaks/OSV had zero findings; infrastructure/Dockerfile findings remain visible.
- Final image: one Medium finding, zero High/Critical. Eight High findings in the initial npm tooling were removed by excluding npm from the final runtime.
- ZAP baseline against AWS staging: six findings, zero policy blockers. Passive, unauthenticated coverage only.
- The isolated SQL injection and public-bucket fixtures produced findings and imported successfully into the demo engagement.
- Local and private AWS DefectDojo installations were started; scoped API accounts and separate scanner tests were created. Reports imported/reimported successfully.
- The exact reporting helper used by CI was exercised over an encrypted SSM port-forwarding tunnel, fetching its token from Secrets Manager.
- The image was pushed to ECR by its immutable bootstrap tag. ECS staging and production reached healthy steady state and passed registration/session/project/task/comment/logout smoke tests.
- The deployed application loaded successfully in the browser at the main AWS-generated endpoint.

## Historical AWS validation

An initial validation deployment was performed from the development machine using AWS CLI/Terraform. It was not a hosted GitHub Actions run. The endpoints and registry image from that deployment are no longer intended for use. The GitHub workflows are implemented and syntax-checked; a hosted run requires your own GitHub authentication and repository setup.

The user requested a source-only handoff and removal of that AWS deployment. The final cleanup result is recorded in [cleanup.md](cleanup.md).

## Manual workflow and decommission additions

The user-facing workflows now use workflow_dispatch only. The internal deploy helper is called by the manually started release. Decommission has an account/confirmation guard, a review gate, state-change detection, delete-only plan validation, and cleanup ordering tests. These new tests use mocks and make no AWS changes. The complete hosted destroy workflow has not been executed against a newly provisioned installation.

The source-only changes passed 17 Python tests (including nine decommission safety/order/verification tests), actionlint, validation of all three Terraform roots, and the application build. No AWS provisioning/deletion was performed while implementing these additions.
