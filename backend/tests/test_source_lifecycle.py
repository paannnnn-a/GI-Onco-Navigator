from backend.app.storage import REQUIRED_REVIEW_DIMENSIONS, Database


def _source(identifier: str, supersedes: str | None = None) -> dict[str, object]:
    return {
        "source_id": identifier, "title": identifier, "evidence_type": "guideline", "version": identifier,
        "publication_date": None, "cancer_types": ["colon"], "intended_audience": "patient",
        "copyright_status": "test", "license_name": None, "public_url": None,
        "local_filename": None, "sha256": None, "supersedes_source_id": supersedes,
        "review_status": "quarantined", "metadata": {},
    }


def _approve(database: Database, source_id: str) -> None:
    for dimension in REQUIRED_REVIEW_DIMENSIONS:
        database.review_source(source_id, dimension, "approved", "Reviewer", "完成合成资料审核。")


def _add_located_chunk(database: Database, source_id: str) -> None:
    database.add_chunk(
        {
            "chunk_id": f"{source_id}:0", "source_id": source_id, "ordinal": 0,
            "text": "用于版本生命周期测试的合成证据内容。", "page_start": 1, "page_end": 1,
            "timestamp_start_seconds": None, "timestamp_end_seconds": None, "section_path": [],
            "cancer_types": ["colon"], "tags": [], "extraction_method": "synthetic_test",
            "review_status": "quarantined", "content_hash": f"hash-{source_id}",
        }
    )


def test_approved_new_version_marks_declared_predecessor_outdated(tmp_path) -> None:
    database = Database(tmp_path / "versions.db")
    database.add_source(_source("v1"))
    _add_located_chunk(database, "v1")
    _approve(database, "v1")
    database.add_source(_source("v2", supersedes="v1"))
    _add_located_chunk(database, "v2")
    _approve(database, "v2")
    assert database.get_source("v1")["review_status"] == "outdated"
    assert database.get_source("v2")["review_status"] == "approved"
    events = database.list_source_status_events("v1")
    assert events[0]["new_status"] == "outdated"


def test_empty_source_cannot_pass_publication_gate(tmp_path) -> None:
    database = Database(tmp_path / "empty.db")
    database.add_source(_source("empty"))
    for dimension in REQUIRED_REVIEW_DIMENSIONS[:-1]:
        database.review_source("empty", dimension, "approved", "Reviewer", "完成合成资料审核。")
    import pytest

    with pytest.raises(ValueError, match="at least one evidence chunk"):
        database.review_source(
            "empty", REQUIRED_REVIEW_DIMENSIONS[-1], "approved", "Reviewer", "完成合成资料审核。"
        )
