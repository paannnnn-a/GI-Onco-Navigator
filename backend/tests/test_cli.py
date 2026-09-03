import json

import pytest
from pydantic import ValidationError

from backend.app.cli import load_manifest, verify_content_free_pages
from backend.app.knowledge import ExtractedPage


def test_cli_manifest_uses_admin_metadata_contract(tmp_path) -> None:
    path = tmp_path / "source.json"
    path.write_text(
        json.dumps(
            {
                "source_id": "nci-colon.patient-2026",
                "title": "Synthetic source",
                "evidence_type": "patient_education",
                "cancer_types": ["colon"],
                "copyright_status": "synthetic_test_permission",
                "tags": ["follow-up", "records"],
                "review_status": "approved",
            }
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(path)

    assert manifest["tags"] == ["follow-up", "records"]
    assert manifest["review_status"] == "quarantined"


@pytest.mark.parametrize("source_id", ["../outside", "spaces are unsafe", "中文标识", "-leading"])
def test_cli_manifest_rejects_unsafe_source_identifier(tmp_path, source_id: str) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "title": "Synthetic source",
                "evidence_type": "patient_education",
                "copyright_status": "synthetic_test_permission",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_manifest(path)


def test_content_free_page_review_is_accountable_and_narrow() -> None:
    pages = [
        ExtractedPage(1, "", "ocr", True),
        ExtractedPage(2, "42", "ocr", True),
        ExtractedPage(3, "Real section content", "ocr", False),
    ]

    review = verify_content_free_pages(
        pages,
        {1, 2},
        "Reviewer A",
        "Rendered pages contain only blank space and page furniture.",
    )

    assert review == {
        "page_numbers": [1, 2],
        "reviewer": "Reviewer A",
        "reason": "Rendered pages contain only blank space and page furniture.",
    }
    with pytest.raises(ValueError, match="at most three"):
        verify_content_free_pages(pages, {3}, "Reviewer A", "Visually reviewed page.")
    with pytest.raises(ValueError, match="require"):
        verify_content_free_pages(pages, {1}, None, None)
