# User-provided material review

This record describes ingestion and governance decisions without reproducing copyright-restricted source text.

| Source | Technical findings | Processing decision | Patient state |
|---|---|---|---|
| 2025 CSCO Guidelines for Colorectal Cancer | 160-page scan with no usable text layer; full local OCR produced 94 chunks and no unresolved content pages; rendered pages 12 and 160 contain only blank space or page furniture | Retain reviewer-attributed blank-page record, perform table/order QA, and track as predecessor to the 2026 edition | Quarantined |
| 2026 CSCO Guidelines for Colorectal Cancer | 174-page scan; full local OCR produced 106 chunks; six sparse chapter-title pages were visually checked and motivated the sparse-page rule | Re-run with the corrected sparse-page rule; registered as successor to the 2025 edition | Quarantined |
| Gastric Cancer 101 Patient Handbook, 2026 v1 | 54 pages; broken Chinese font mapping on 47 body pages; full local OCR produced 54 chunks with no unresolved pages | Verify authorship, permission, citations, layout order, and claims; patient-explanation candidate only | Quarantined |
| Introduction to Colorectal Cancer Treatment | 132 pages; every original text-layer page fails quality checks; full local OCR produced 66 chunks with no unresolved pages; visible 2016 print date | Historical patient-education candidate only; check every retained claim against current evidence | Quarantined |
| Knowledge Graph of Colorectal Liver Metastasis: Panda and Friends | 88 paragraphs, 84 non-empty, one inline image, no tables; directly extractable into four chunks | Source and video-lead discovery only; do not expose its treatment, cost, outcome, or provider claims | Quarantined |

## High-risk claim handling

The community DOCX contains treatment regimens, indications, costs, outcomes, and provider names without consistent claim-level primary citations. It cannot be treated as guidance or drive individual recommendations. Each claim must be separated, checked against current guidance, regulator material, trial registration, or primary research, assigned scope and date, and reviewed by a qualified medical reviewer. Provider information may be matched only through maintainable official directories and is never ranked.

Original files remain in ignored local storage and are not committed. The public repository contains only checksums, source metadata, processing code, and governance decisions.

Run `gi-onco audit-pdf <file>` before ingestion to generate a non-content quality report with checksum, file size, page count, character statistics, and unresolved page numbers. Corrupt pages are excluded from chunks. Successful OCR does not establish medical accuracy: complex tables can still contain reading-order, Roman-numeral, and terminology errors.

On 2026-09-03, representative pages from all four PDFs produced readable Chinese with local OCR.
Full OCR completed for the 2025 CSCO guideline, Gastric Cancer 101 handbook, and colorectal
treatment primer. The 2025 run retained an accountable visual record for two content-free pages.
Full OCR of the 2026 CSCO guideline initially produced 106 quarantined chunks; six sparse pages (4,
17, 20, 56, 122, and 157) were visually confirmed to be legitimate cover or section-title pages,
which prompted a safer sparse-page detection rule and a clean re-run. The DOCX passed structural
extraction, but visual DOCX rendering could not be completed in this environment because
LibreOffice is unavailable. No extracted medical content has been approved for patient use.
