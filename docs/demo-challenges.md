# Security remediation walkthrough

Follow Chapter 8 of the [Project Book](PROJECT-BOOK.md). The main video uses **Secure release** with `include_remediation_demo` enabled: report two source findings, fix both scan-only files, push, and manually start a new release with the same option enabled. Reimport into the same DefectDojo remediation engagement and Semgrep test resolves the previous findings; policy must pass before build approval.

The separate **Record security challenges** workflow is an optional approval/rejection exercise. It scans SQL and public-bucket fixtures and never builds or deploys an application image.

The complete book is also available as [a PDF](../output/pdf/Secure-Task-By-Akuphe-Project-Book.pdf).
