from datetime import UTC, date, datetime

from backend.app.schemas import CancerType, PatientProfile
from backend.app.storage import Database


def test_patient_roundtrip(tmp_path) -> None:
    database = Database(tmp_path / "test.db")
    expected = PatientProfile(
        patient_id="patient-1",
        cancer_type=CancerType.COLON,
        surgery_date=date(2026, 8, 20),
    )
    database.save_patient(expected)
    actual = database.get_patient("patient-1")
    assert actual is not None
    assert actual.cancer_type is CancerType.COLON


def test_delete_patient_record(tmp_path) -> None:
    database = Database(tmp_path / "delete.db")
    profile = PatientProfile(patient_id="delete-me", cancer_type=CancerType.RECTAL)
    database.save_patient(profile)
    database.add_reminder(
        {
            "reminder_id": "delete-reminder",
            "patient_id": "delete-me",
            "title": "Follow-up visit",
            "due_at": datetime(2026, 9, 10, tzinfo=UTC).isoformat(),
            "source_note": "Appointment notice",
            "status": "pending",
        }
    )
    database.log_event("patient_saved", "delete-me", {"test": True})
    assert database.count_audit_events("delete-me") == 1
    assert database.delete_patient("delete-me") is True
    assert database.get_patient("delete-me") is None
    assert database.list_reminders("delete-me") == []
    assert database.count_audit_events("delete-me") == 0


def test_foreign_keys_are_enforced_on_every_connection(tmp_path) -> None:
    database = Database(tmp_path / "foreign-keys.db")
    try:
        database.add_reminder(
            {
                "reminder_id": "orphan",
                "patient_id": "missing-patient",
                "title": "Invalid reminder",
                "due_at": datetime(2026, 9, 10, tzinfo=UTC).isoformat(),
                "source_note": "Synthetic test",
                "status": "pending",
            }
        )
    except KeyError:
        pass
    else:
        raise AssertionError("an orphan reminder must violate the patient foreign key")


def test_reingestion_invalidates_prior_chunks_and_reviews(tmp_path) -> None:
    database = Database(tmp_path / "reingest.db")
    source = {
        "source_id": "versioned-source", "title": "测试来源", "evidence_type": "guideline",
        "version": "1", "publication_date": None, "cancer_types": ["colon"],
        "intended_audience": "clinician", "copyright_status": "test_only",
        "license_name": None, "public_url": None, "local_filename": "source.pdf",
        "sha256": "old", "supersedes_source_id": None,
        "metadata": {"extraction_audit": {"pages": 1, "pages_needing_ocr": 0}},
    }
    database.add_source(source)
    database.add_chunk(
        {
            "chunk_id": "old-chunk", "source_id": "versioned-source", "ordinal": 0,
            "text": "旧内容", "page_start": 1, "page_end": 1,
            "timestamp_start_seconds": None, "timestamp_end_seconds": None,
            "section_path": [], "cancer_types": ["colon"], "tags": [],
            "extraction_method": "test", "review_status": "quarantined", "content_hash": "old",
        }
    )
    database.review_source(
        "versioned-source", "copyright", "approved", "Reviewer A", "测试版权审核完成。"
    )

    database.reset_source_for_ingestion("versioned-source")

    assert database.list_source_chunks("versioned-source")[0] == 0
    assert database.get_review_state("versioned-source")["latest_reviews"] == []
    assert database.get_source("versioned-source")["review_status"] == "quarantined"
