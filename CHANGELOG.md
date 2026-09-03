# Changelog

All notable changes to GI-Onco Navigator are documented in this file. The project follows semantic versioning for its software interfaces. Release numbers do not imply clinical validation or regulatory authorization.

## 1.0.0 — 2026-09-03

First stable community engineering release.

### Patient navigation

- Added structured postoperative profiles for colon, rectal, gastric, and other gastrointestinal cancers.
- Added a deterministic postoperative journey model with missing-information detection and phase-specific visit-preparation topics.
- Added consent-gated profile storage, signed patient access, reminders based only on clinician-supplied dates, and self-service export and deletion.
- Added non-ranking facility filtering using verified public attributes.

### Evidence and safety

- Added quarantined PDF, DOCX, verified-subtitle, and restricted public-web ingestion with provenance, hashes, locators, and extraction audits.
- Added four independent publication gates, source lifecycle controls, supersession tracking, and an evidence review workbench.
- Added cancer-filtered hybrid retrieval, evidence-class priority, bounded journey-phase reranking, and citation validation.
- Added bilingual emergency escalation and refusal of individualized drug, regimen, dose, switching, and discontinuation instructions.
- Kept the default answer path extractive and fail-closed when reviewed evidence is unavailable.

### Engineering

- Added an English React patient application and administration workbench, a FastAPI service, SQLite/FTS5 storage, observability, hardened web proxy settings, and production configuration validation.
- Added Docker development and production-like deployment definitions and GitHub Actions checks for backend, frontend, benchmark, and container builds.
- Added comprehensive backend and frontend tests plus a 60-case synthetic bilingual benchmark.
- Added architecture, evidence governance, data, deployment, safety, contribution, and security documentation.

### Deployment boundary

The community release is a complete runnable reference implementation, not a clinically validated medical device. A real-patient deployment still requires accountable clinical, legal, privacy, security, accessibility, human-factors, and jurisdiction-specific review, plus organization-grade identity and infrastructure controls described in `docs/deployment.md`.
