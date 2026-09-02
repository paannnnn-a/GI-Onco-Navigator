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


def test_approved_new_version_marks_declared_predecessor_outdated(tmp_path) -> None:
    database = Database(tmp_path / "versions.db")
    database.add_source(_source("v1"))
    _approve(database, "v1")
    database.add_source(_source("v2", supersedes="v1"))
    _approve(database, "v2")
    assert database.get_source("v1")["review_status"] == "outdated"
    assert database.get_source("v2")["review_status"] == "approved"
    events = database.list_source_status_events("v1")
    assert events[0]["new_status"] == "outdated"
