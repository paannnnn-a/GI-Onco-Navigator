import pytest

from backend.app.schemas import Citation, EvidenceType
from backend.app.services.citation_guard import CitationValidationError, validate_citations


def test_patient_claim_requires_approved_located_citation() -> None:
    citation = Citation(
        source_id="x",
        title="fixture",
        evidence_type=EvidenceType.GUIDELINE,
        review_status="unreviewed",
        page_start=1,
    )
    with pytest.raises(CitationValidationError):
        validate_citations([citation])


def test_approved_citation_with_page_is_valid() -> None:
    citation = Citation(
        source_id="x",
        title="fixture",
        evidence_type=EvidenceType.GUIDELINE,
        review_status="approved",
        page_start=1,
    )
    validate_citations([citation])
