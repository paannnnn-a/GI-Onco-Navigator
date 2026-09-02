# Security policy

## Reporting a vulnerability

Please do not disclose a suspected vulnerability in a public issue. Use GitHub's private
**Security → Report a vulnerability** workflow for this repository. Include affected versions,
reproduction steps, impact, and any suggested mitigation. Do not include real patient data,
credentials, access tokens, or copyrighted clinical documents.

Until a production security review is completed, this project is a reference implementation for
patient education and visit preparation. It is not authorized to store identifiable health data
in a public deployment. Operators are responsible for applicable privacy, cybersecurity, medical
device, hosting, retention, breach-response, and clinical-governance requirements.

## Supported versions

Security fixes are applied to the current `main` branch. No stable production release is supported
yet.

## Security boundaries

- Never commit secrets or real patient records.
- Change all example secrets before deployment.
- Put the API behind TLS, authenticated access, least-privilege authorization, encrypted storage,
  backups, monitoring, and an incident-response process.
- Treat imported documents and webpages as untrusted input.
- A successful software security review does not constitute medical-content approval.
