# GI-Onco Navigator

An open-source, evidence-grounded postoperative navigation platform for people affected by gastrointestinal cancer.

GI-Onco Navigator connects a structured patient profile, a postoperative journey model, governed medical sources, traceable retrieval, and safety controls in one deployable web application. It helps patients understand their current phase, identify missing information, prepare questions for clinical visits, and locate relevant evidence. It does not diagnose, prescribe, rank clinicians, or replace the treating team.

## Capabilities

- Postoperative profiles for colon, rectal, and gastric cancer
- A patient-journey state machine based on surgery date, pathology readiness, and current treatment status
- Emergency-symptom escalation and blocking of patient-specific treatment instructions
- PDF, DOCX, verified subtitle, and restricted public-web ingestion
- Local OCR, corruption detection, page-level extraction audits, and content hashing
- Evidence versioning, copyright state, review state, provenance, and supersession tracking
- SQLite FTS5 lexical retrieval plus local concept-based retrieval and evidence-priority reranking
- Patient answers built only from approved passages with page, timestamp, or section citations
- Explicit consent for stored profiles, short-lived signed access tokens, and self-service export and deletion
- Reminders only for dates already supplied by a clinical team or appointment notice
- A responsive patient web app and a separate evidence-governance workbench
- Four mandatory publication gates: copyright, extraction quality, medical accuracy, and patient readability
- Safe uploads with size, format, archive, and duplicate-source checks; every upload starts in quarantine
- Source withdrawal, quarantine, obsolescence, and version-replacement workflows
- Non-ranking facility filtering based only on verified registration and service attributes
- Privacy-conscious audit events, request tracing, health endpoints, and Prometheus metrics
- Docker deployment, CI, automated tests, and an extensible 50-case benchmark

The default build does not connect to a large language model. It returns retrieved, reviewed evidence directly to reduce unsupported generation. A model can be added as an optional presentation layer, but it must never bypass citation, review, and safety gates.

## Quick start

### Docker

```bash
docker compose up --build
```

- Patient app: <http://localhost:5173>
- Evidence workbench: <http://localhost:5173/admin> (requires `ADMIN_API_KEY`)
- API documentation: <http://localhost:8000/docs>
- Readiness: <http://localhost:8000/health/ready>
- Metrics: <http://localhost:8000/metrics>

### Local development

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/uvicorn backend.app.main:app --reload
```

In another terminal, run `cd frontend`, `pnpm install`, and `pnpm dev`.

## Evidence ingestion

Copyright-restricted guidelines and patient materials are not committed to GitHub. The repository stores source manifests, checksums, processing code, and permitted metadata. Place lawfully obtained files in a local ignored directory and run:

```bash
gi-onco audit-pdf /path/to/source.pdf
gi-onco ingest-pdf data/sources/example.json /path/to/source.pdf
gi-onco ingest-pdf data/sources/example.json /path/to/source.pdf --ocr
gi-onco ingest-docx data/sources/example.json /path/to/source.docx
gi-onco ingest-transcript data/sources/video.json /path/to/verified-subtitles.srt
gi-onco ingest-web data/sources/nci-colon-patient-pdq.json
```

`audit-pdf` reports extraction quality without storing source text. PDF ingestion records all pages that still require OCR. A PDF cannot pass the extraction-quality gate while any page remains unresolved. Re-ingesting a source invalidates its previous chunks and approvals.

Video sources use human-verified UTF-8 SRT or WebVTT subtitles and retain timestamp locators. Public web ingestion accepts only credential-free HTTPS URLs, rejects private and reserved network targets, limits content type and size, and preserves section locators and a content hash. Every newly ingested source remains quarantined.

## Evidence hierarchy

1. Clinical guidelines
2. Peer-reviewed research
3. Patient education material
4. Expert educational video or conference material
5. Community material and other discovery leads

The interface displays evidence type, version, and source locator. Community material, provider lists, and unverified treatment claims cannot support patient-facing answers.

## Tests and benchmark

```bash
pytest -q
ruff check backend
gi-onco-benchmark benchmarks/cases
```

The benchmark contains 50 entirely synthetic cases, including 11 retrieval targets. It evaluates journey classification, safety routing, Recall@K, citation validity, refusal accuracy, and dangerous-advice rate. It is an engineering regression suite, not evidence of clinical effectiveness.

## Repository layout

```text
backend/       FastAPI application, safety layer, ingestion, retrieval, and audit logic
frontend/      React and TypeScript patient app and evidence workbench
data/          Source manifests and ignored local evidence directories
benchmarks/    Synthetic evaluation cases and benchmark runner
docs/          Architecture, governance, deployment, and dataset documentation
.github/       Continuous integration and repository automation
```

See [System design](docs/project_design.md), [Database design](docs/database_design.md), [Evidence governance](docs/evidence_governance.md), [Facility navigation](docs/facility_navigation.md), [Benchmark methodology](docs/benchmark.md), [Material review](docs/material_review.md), [External sources](docs/external_sources.md), and [Deployment boundaries](docs/deployment.md).

## Medical safety and privacy

- The system does not provide patient-specific drugs, regimens, doses, or stop-treatment instructions.
- Potential emergency symptoms stop the ordinary information flow and direct the user to timely medical assessment.
- When no approved evidence is retrieved, the system fails closed instead of filling gaps from model knowledge.
- Never commit identifiable patient information to a public repository.
- A public deployment still requires organizational identity, encryption, access control, backup, security, privacy, clinical, and jurisdiction-specific compliance review.

## Contributing and license

Contributions of code, openly licensed metadata, parsers, and synthetic test cases are welcome. Medical content must include source, version, copyright status, and accountable review; an ordinary code merge cannot publish it to patients.

Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Project code is licensed under Apache-2.0. Third-party medical sources retain their original terms and are not relicensed by this repository.
