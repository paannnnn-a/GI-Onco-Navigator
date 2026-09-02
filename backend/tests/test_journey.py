from datetime import date

from backend.app.schemas import CancerType, PatientProfile, TreatmentStatus
from backend.app.services.journey import assess_journey


def test_early_postoperative_stage() -> None:
    profile = PatientProfile(
        patient_id="case-001",
        cancer_type=CancerType.COLON,
        surgery_date=date(2026, 8, 28),
    )
    result = assess_journey(profile, today=date(2026, 9, 2))
    assert result.current_status is TreatmentStatus.POSTOPERATIVE_RECOVERY
    assert {item.field for item in result.missing_information} == {
        "pathological_stage",
        "margin_status",
        "mismatch_repair_status",
    }


def test_active_treatment_takes_precedence() -> None:
    profile = PatientProfile(
        patient_id="case-002",
        cancer_type=CancerType.RECTAL,
        surgery_date=date(2026, 1, 1),
        current_treatment="patient-entered treatment record",
    )
    result = assess_journey(profile, today=date(2026, 9, 2))
    assert result.current_status is TreatmentStatus.ACTIVE_TREATMENT

