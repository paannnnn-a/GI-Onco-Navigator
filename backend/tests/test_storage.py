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

