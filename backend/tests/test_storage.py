from datetime import date

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
    database.log_event("patient_saved", "delete-me", {"test": True})
    assert database.count_audit_events("delete-me") == 1
    assert database.delete_patient("delete-me") is True
    assert database.get_patient("delete-me") is None
    assert database.count_audit_events("delete-me") == 0
