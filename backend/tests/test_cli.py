import json

import pytest
from pydantic import ValidationError

from backend.app.cli import load_manifest


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
