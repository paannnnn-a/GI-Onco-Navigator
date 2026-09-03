# User-provided material review

This record describes ingestion and governance decisions without reproducing copyright-restricted source text.

| Source | Technical findings | Processing decision | Patient state |
|---|---|---|---|
| 2025 CSCO Guidelines for Colorectal Cancer | 160-page scan; visually clear samples; no usable text layer | Full local OCR, page sampling, and version tracking | Quarantined |
| 2026 CSCO Guidelines for Colorectal Cancer | 174-page scan; visually clear samples; no usable text layer | Full local OCR; registered as successor to the 2025 edition | Quarantined |
| Gastric Cancer 101 Patient Handbook, 2026 v1 | 54 pages; broken Chinese font mapping on 47 body pages; seven reference pages extract as text | OCR body; verify authorship, permission, citations, and claims; patient-explanation candidate only | Quarantined |
| Introduction to Colorectal Cancer Treatment | 132 pages; visually readable but every text-layer page fails quality checks; visible 2016 print date | Full OCR; historical patient-education candidate only, not current treatment authority | Quarantined |
| Knowledge Graph of Colorectal Liver Metastasis: Panda and Friends | 88 paragraphs, 84 non-empty; directly extractable | Four local discovery chunks; source and video-lead discovery only | Quarantined |

## High-risk claim handling

The community DOCX contains treatment regimens, indications, costs, outcomes, and provider names without consistent claim-level primary citations. It cannot be treated as guidance or drive individual recommendations. Each claim must be separated, checked against current guidance, regulator material, trial registration, or primary research, assigned scope and date, and reviewed by a qualified medical reviewer. Provider information may be matched only through maintainable official directories and is never ranked.

Original files remain in ignored local storage and are not committed. The public repository contains only checksums, source metadata, processing code, and governance decisions.

Run `gi-onco audit-pdf <file>` before ingestion to generate a non-content quality report with checksum, file size, page count, character statistics, and unresolved page numbers. Corrupt pages are excluded from chunks. Successful OCR does not establish medical accuracy: complex tables can still contain reading-order, Roman-numeral, and terminology errors.

On 2026-09-03, representative pages from all four PDFs produced readable Chinese with local OCR. Full OCR of the 2026 CSCO guideline produced 106 quarantined chunks. Six initially unresolved pages (4, 17, 20, 56, 122, and 157) were visually confirmed to be legitimate cover or section-title pages, which prompted a safer sparse-page detection rule. No extracted medical content has been approved for patient use.
