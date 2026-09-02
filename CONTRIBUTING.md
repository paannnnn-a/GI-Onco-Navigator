# Contributing

GI-Onco Navigator welcomes code, tests, documentation, public-source metadata, ingestion adapters,
and synthetic benchmark cases. Never submit identifiable patient information or redistribute
clinical material without permission.

## Development checks

Before opening a pull request, run:

```bash
ruff check backend
pytest -q
gi-onco-benchmark benchmarks/cases
cd frontend && pnpm install --frozen-lockfile && pnpm build
```

Describe the problem, the safety impact, tests performed, and any migration or deployment changes.
Keep changes scoped and include regression tests for altered behavior.

## Medical evidence contributions

Medical content is data, not executable instruction. A contribution must identify the publisher,
title, edition or version, publication date, stable URL or lawful local-file workflow, evidence
type, intended audience, copyright status, and content hash. It enters quarantine by default.

No pull request, maintainer role, automated check, or successful ingestion can mark medical content
patient-ready. Publication requires separate review of copyright, extraction quality, medical
accuracy, and patient readability by accountable reviewers. Conflicts, retractions, and superseded
versions must remain traceable. Expert videos and community material cannot be represented as
clinical guidelines.

## Synthetic evaluation data

Benchmark cases must be invented and contain no details copied from a real individual. Document the
expected journey stage, safety outcome, retrieval target, and citation expectation when applicable.
