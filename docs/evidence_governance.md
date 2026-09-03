# Evidence governance

GI-Onco Navigator separates application code from restricted source material.

## Evidence classes

1. Clinical guidelines and consensus statements
2. Peer-reviewed literature
3. Patient education material
4. Expert conference or educational video
5. Local operational data such as hospitals and services

Every indexed passage must preserve source identity, edition, publication date, cancer type,
intended audience, page or timestamp, copyright status, supersession status, and review status.

## Public repository policy

- Do not commit copyrighted PDFs, videos, patient records, access tokens, or generated embeddings
  that reproduce restricted material.
- Commit ingestion code, schemas, metadata examples, checksums, evaluation fixtures, and instructions.
- Users place restricted files under `data/private/`, which is ignored by Git.
- Generated responses must distinguish guideline content, patient education, expert experience, and
  model-generated explanation.

## Version policy

Newer guidance does not silently overwrite earlier editions. Both remain traceable. Retrieval
prefers the latest in-scope, reviewed edition and surfaces conflicts or superseded content.

## Review gates

Every source starts in quarantine. Publication requires four independent active approvals:
copyright, extraction quality, medical accuracy, and patient readability. A rejection blocks the
source; quarantine, withdrawal, supersession, or content re-ingestion invalidates earlier active
approvals. Only approved passages may support patient-facing clinical navigation in production.

PDF ingestion records a page-level extraction audit. The extraction-quality gate cannot be
approved while any page still requires OCR, and a PDF without a recorded audit cannot pass that
gate. OCR output must still be checked against the rendered page because successful character
recognition does not establish table order or medical accuracy.

Web sources must use a public HTTPS URL, retain a content hash and section locator, and remain
quarantined after ingestion. A trusted publisher does not remove the need for copyright,
extraction-quality, medical-accuracy, and patient-readability review.
