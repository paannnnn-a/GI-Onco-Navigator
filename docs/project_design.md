# GI-Onco Navigator system design

## Product boundary

GI-Onco Navigator is an evidence-grounded information and visit-preparation platform for patients after gastrointestinal cancer surgery. It connects a patient profile and journey phase to governed sources and returns traceable patient education and discussion prompts.

It does not diagnose disease, select a drug, regimen, dose, hospital, or clinician, and does not present community experience as clinical guidance.

## Core flow

```text
Patient profile
  -> field and consistency validation
  -> postoperative journey state machine
  -> emergency and prescriptive-request safety routing
  -> cancer- and phase-aware retrieval scope
  -> approved evidence only
  -> evidence hierarchy and reranking
  -> page, timestamp, or section citation validation
  -> patient-readable evidence and visit questions
  -> privacy-conscious audit event
```

If a patient-facing medical statement cannot be supported by an eligible citation, the application fails closed rather than allowing a model to complete it from general knowledge.

## Components

### Patient application

A responsive React and TypeScript web application provides cancer selection, a structured postoperative profile, journey assessment, safety explanations, evidence provenance, reminders, and navigation topics.

### Application API

FastAPI exposes profile, journey, navigation, evidence, facility, and administrative endpoints. The community build uses SQLite and FTS5. Interfaces are separated so a production operator can migrate storage and retrieval without bypassing review or citation controls.

### Patient journey

States include early recovery, pathology preparation, adjuvant-treatment evaluation, active treatment, surveillance, rehabilitation, and unknown. The state machine organizes information; it is not a clinical diagnosis or treatment decision.

### Knowledge and retrieval

Sources retain version, date, cancer scope, audience, copyright state, review state, supersession, and checksum. Chunks retain a page, timestamp, or section locator, extraction method, and content hash. Retrieval combines SQLite FTS5 keyword recall with local Chinese concept and character features, fuses rankings with reciprocal rank fusion, and applies evidence-type priority. A validated medical embedding service may replace the local similarity layer, but cannot bypass approval and citation gates.

### Safety layer

- Potential emergency symptoms stop ordinary question answering.
- Requests for patient-specific treatment, dosing, or discontinuation do not enter generation.
- Patient endpoints retrieve only `approved` sources and chunks.
- Administrative writes require a separate secret.
- Material actions produce audit events without storing question text.

## Evidence pipeline

```text
Lawfully obtained local or public source
  -> source registration and SHA-256
  -> safe extraction and page-level quality audit
  -> optional local OCR
  -> locatable chunks
  -> quarantine
  -> copyright review
  -> extraction-quality review
  -> medical-accuracy review
  -> patient-readability review
  -> approved index
```

Scanned PDFs require OCR and page-level verification. Re-ingestion invalidates previous chunks and approvals. Restricted or weakly sourced content retains only permitted metadata and discovery leads in the public repository.

## Deployment boundary

Docker Compose starts the API, static web application, and persistent data volume. Nginx handles client routing and `/api` proxying. CI runs linting, backend and frontend tests, the benchmark, production builds, and container builds.

The application emits request IDs, privacy-conscious access logs, liveness, readiness, and Prometheus metrics. A production operator must additionally provide HTTPS, managed secrets, strong organizational identity, least privilege, encrypted backup and restoration, centralized logs, vulnerability management, privacy impact assessment, and applicable medical and data compliance review.

Observability labels use declared route templates rather than raw request paths, so patient IDs and
arbitrary unmatched path content do not enter metrics. Caller-supplied request IDs are accepted
only when they match a short opaque-token format; other values are replaced before logging or
reflection.

## Evaluation

The benchmark uses synthetic patients only. It measures journey-state classification, safety routing, retrieval Recall@K, citation validity, refusal accuracy, and dangerous-advice rate. Clinical validation and public release of a medical evaluation set require independent expert review.
