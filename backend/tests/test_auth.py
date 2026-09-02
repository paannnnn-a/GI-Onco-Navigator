
import pytest

from backend.app.auth import InvalidPatientToken, issue_patient_token, verify_patient_token


def test_patient_token_is_bound_to_one_patient() -> None:
    patient_id, token, _ = issue_patient_token("test-secret")
    verify_patient_token(token, "test-secret", patient_id)
    with pytest.raises(InvalidPatientToken):
        verify_patient_token(token, "test-secret", "another-patient")


def test_patient_token_rejects_tampering_and_expiry() -> None:
    patient_id, token, _ = issue_patient_token("test-secret", ttl_seconds=-1)
    with pytest.raises(InvalidPatientToken, match="expired"):
        verify_patient_token(token, "test-secret", patient_id)
    patient_id, token, _ = issue_patient_token("test-secret")
    payload, signature = token.split(".")
    with pytest.raises(InvalidPatientToken):
        verify_patient_token(f"{payload}.{signature[:-1]}x", "test-secret", patient_id)
