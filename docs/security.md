# Security tooling and findings policy

| Tool | Coverage | Report |
|---|---|---|
| Semgrep 1.180.0 | Project-owned SQL/eval checks and vendored Express rules | JSON |
| Gitleaks 8.30.1 CLI | Committed Git history; secret values redacted | JSON |
| OSV-Scanner 2.6.0 | npm lockfile dependency vulnerabilities | JSON |
| Checkov 3.3.26 | Terraform source and resolved plans | JSON |
| Hadolint 2.15.1 | Dockerfile practices | JSON |
| Trivy 0.75.0 | OS and npm packages in final image | JSON |
| ZAP 2.17.0 | Passive baseline of reachable unauthenticated web pages | JSON + HTML |

`security/tools.lock.json` records exact image digests. `security/actions.lock.json` records the action commits used by workflows. Semgrep rules are vendored with their license, source references, and checksums. Review and update these pins periodically. Vulnerability databases remain live, so findings can change without a code change.

## Normalization

Every scanner report is validated and converted into DefectDojo Generic Findings Import JSON. Stable IDs use scanner, rule/vulnerability ID, file/target, and line. Line moves can create a new identity. Each scanner/scope has its own Dojo Test to prevent one clean report from closing findings from another tool.

Severity mapping is deliberately conservative: Semgrep ERROR is High; Gitleaks findings are High; OSV uses its database severity or defaults to High when absent; Trivy uses vendor severity; ZAP uses riskcode. Hadolint warning is Medium and error is High. Checkov normally provides no severity in its free report: selected public exposure, database encryption, and dangerous access-control checks map to High; other controls map to Medium for human review. This is a project policy, not an assertion that all Checkov controls have equal risk. Extend the explicit mapping for your organization.

Hadolint's two npm warnings correspond to `npm ci` with a committed lockfile and removal of npm from the runtime. They remain visible rather than being broadly suppressed. Alpine package pinning is handled at base-image digest level; the RDS trust bundle is downloaded from the official AWS endpoint at image build time.

## Blocking behavior

Provisioning first scans all real Terraform roots, without AWS credentials. `CKV2_AKUPHE_1` requires all four S3 public-access protections to be enabled; `CKV2_AKUPHE_2` requires RDS storage encryption. Both custom policies are High severity. The tutorial starts with one false setting for each policy in the real configuration. The `infrastructure-security` job blocks the dependent configuration, bootstrap, plan, and apply jobs until those values are corrected. The resolved platform plan also loads these policies before apply. Initial infrastructure failures are retained as Actions artifacts because Dojo has not yet been provisioned.

Missing, malformed, timed-out, or failed scans block. Upload failures block. Secrets and Critical findings always block. High findings block unless a reviewed, unexpired exception permits them. Medium/Low/Info findings remain visible and eligible for manual review.

The report collection stage permits scanner exit codes associated with findings only if a well-formed report exists. Scanner execution errors do not become clean reports. Manually dispatched source-check policy is enforced per scanner. Trusted main releases upload source findings before evaluating aggregate policy.

An exception must contain `tool`, `finding_id`, `reason`, `approver`, and ISO `expires`. DefectDojo accepted-risk labels are not automatically trusted as release waivers. `security/policy.json` is authoritative and should be protected by code review.

The tutorial deliberately reports HTTP and cost/availability tradeoffs. Do not interpret a passing policy as proof that no vulnerabilities exist. ZAP baseline cannot discover all API or authenticated application vulnerabilities. Add authenticated automation and active testing in an isolated environment when extending this project.

## Sources

- https://docs.defectdojo.com/supported_tools/parsers/generic_findings_import/
- https://docs.defectdojo.com/automation/api/api-v2-docs/
- https://github.com/semgrep/semgrep-rules
- https://github.com/gitleaks/gitleaks
- https://google.github.io/osv-scanner/
- https://www.checkov.io/
- https://github.com/hadolint/hadolint
- https://trivy.dev/
- https://www.zaproxy.org/docs/docker/baseline-scan/

The Gitleaks allowlist is restricted to one verified public action commit SHA in `security/actions.lock.json`. Its key contains the word credentials, which otherwise causes a generic-api-key false positive. Real secrets remain blocking; no secret finding is waived through release approval.


## Recorded remediation flow

Secure release has a manually selected `include_remediation_demo` input. It extends Semgrep's normal source targets with two scan-only TypeScript exercises; Checkov continues scanning live Terraform source. Findings are uploaded before policy evaluation, so the first vulnerable run records the issues and stops before Docker build.

Exercise runs use the pre-created `remediation` engagement with separate tests for the five source tools. Normal source runs use `main`, image reports use `image`, and staging reports use `runtime`. Reimports always target the same test within a scope and enable closing old findings, including when a completed report contains an empty findings list. Normal runs cannot close the remediation test by omitting its scan targets.

The book supplies fixes and requires a new run at the corrected commit with the same option enabled. Existing findings become inactive/mitigated rather than being erased. Local pinned Semgrep verification detects exactly two issues before the fixes and zero afterward; this does not assert zero findings across every other scanner.
