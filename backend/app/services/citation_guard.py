from __future__ import annotations

from backend.app.schemas import Citation


class CitationValidationError(ValueError):
    pass


def validate_citations(citations: list[Citation], patient_facing: bool = True) -> None:
    if patient_facing and not citations:
        raise CitationValidationError("patient-facing evidence claims require citations")
    for citation in citations:
        if citation.review_status != "approved" and patient_facing:
            raise CitationValidationError(
                f"source {citation.source_id} is not approved for patient-facing use"
            )
        has_web_locator = bool(citation.public_url and citation.section_path)
        if (
            citation.page_start is None
            and citation.timestamp_start_seconds is None
            and not has_web_locator
        ):
            raise CitationValidationError(
                f"source {citation.source_id} has no page, timestamp, or webpage section locator"
            )
