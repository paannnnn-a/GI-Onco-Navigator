from backend.app.services.retrieval import citation_from_row, retrieve
from backend.app.storage import REQUIRED_REVIEW_DIMENSIONS, Database


def test_citation_preserves_video_timestamp_at_zero_seconds() -> None:
    citation = citation_from_row(
        {
            "source_id": "video", "title": "合成视频", "evidence_type": "expert_video",
            "version": "1", "page_start": None, "page_end": None,
            "timestamp_start_seconds": 0, "text": "片头即出现的合成测试内容。",
            "public_url": None, "section_path_json": "[]", "review_status": "approved",
        }
    )
    assert citation.timestamp_start_seconds == 0


def _approved_fixture(database: Database, source_id: str, text: str, evidence_type: str = "patient_education") -> None:
    database.add_source(
        {
            "source_id": source_id, "title": source_id, "evidence_type": evidence_type,
            "version": "1", "publication_date": "2026-01-01", "cancer_types": ["colon"],
            "intended_audience": "patient", "copyright_status": "test", "license_name": None,
            "public_url": None, "local_filename": None, "sha256": None, "supersedes_source_id": None,
            "review_status": "quarantined", "metadata": {},
        }
    )
    database.add_chunk(
        {
            "chunk_id": f"{source_id}:0", "source_id": source_id, "ordinal": 0, "text": text,
            "page_start": 1, "page_end": 1, "timestamp_start_seconds": None,
            "timestamp_end_seconds": None, "section_path": [], "cancer_types": ["colon"],
            "tags": [], "extraction_method": "test", "review_status": "quarantined",
            "content_hash": source_id,
        }
    )
    for dimension in REQUIRED_REVIEW_DIMENSIONS:
        database.review_source(source_id, dimension, "approved", "Test Reviewer", "测试审核依据充分。")


def test_hybrid_retrieval_matches_patient_synonym(tmp_path) -> None:
    database = Database(tmp_path / "retrieval.db")
    _approved_fixture(database, "followup", "复诊前应整理病理检查资料，并记录准备咨询的问题。")
    _approved_fixture(database, "nutrition", "饮食营养内容应结合恢复情况。")
    rows = retrieve(database, "回医院复查要带什么报告", "colon", limit=2)
    assert rows[0]["source_id"] == "followup"
    assert float(rows[0]["retrieval_score"]) > 0


def test_hybrid_retrieval_still_excludes_quarantined_content(tmp_path) -> None:
    database = Database(tmp_path / "quarantine.db")
    database.add_source(
        {
            "source_id": "unsafe", "title": "unsafe", "evidence_type": "other", "version": None,
            "publication_date": None, "cancer_types": ["colon"], "intended_audience": "patient",
            "copyright_status": "unknown", "license_name": None, "public_url": None,
            "local_filename": None, "sha256": None, "supersedes_source_id": None,
            "review_status": "quarantined", "metadata": {},
        }
    )
    assert retrieve(database, "任何问题", "colon") == []
