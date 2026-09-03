from datetime import UTC, date, datetime

from backend.app.schemas import (
    JourneyAssessment,
    MissingInformation,
    PatientProfile,
    TreatmentStatus,
)

REQUIRED_PATHOLOGY_FIELDS = (
    ("pathological_stage", "Pathological stage", "Helps define the scope of postoperative risk and follow-up discussions"),
    ("margin_status", "Margin status", "Helps confirm whether the surgical pathology record is complete"),
    ("mismatch_repair_status", "MMR/MSI status", "May affect subsequent risk assessment and discussion topics"),
)


def assess_journey(profile: PatientProfile, today: date | None = None) -> JourneyAssessment:
    today = today or datetime.now(UTC).date()
    missing = [
        MissingInformation(field=field, patient_friendly_label=label, reason=reason)
        for field, label, reason in REQUIRED_PATHOLOGY_FIELDS
        if not getattr(profile, field)
    ]

    days_since_surgery: int | None = None
    if profile.surgery_date:
        days_since_surgery = (today - profile.surgery_date).days

    if profile.current_treatment:
        status = TreatmentStatus.ACTIVE_TREATMENT
        explanation = "The profile records active postoperative treatment, so navigation should focus on monitoring and follow-up questions during treatment."
    elif days_since_surgery is None:
        status = TreatmentStatus.UNKNOWN
        explanation = "No surgery date is recorded, so the current postoperative stage cannot be assessed reliably."
    elif days_since_surgery < 0:
        status = TreatmentStatus.UNKNOWN
        explanation = "The surgery date is in the future. Check the patient profile."
    elif days_since_surgery <= 14:
        status = TreatmentStatus.POSTOPERATIVE_RECOVERY
        explanation = "The patient is in the early postoperative recovery window; navigation focuses on recovery and pathology-record preparation."
    elif missing:
        status = TreatmentStatus.PATHOLOGY_REVIEW
        explanation = "The patient has entered postoperative pathology review, but essential information is still incomplete."
    elif days_since_surgery <= 56:
        status = TreatmentStatus.ADJUVANT_EVALUATION
        explanation = "The profile indicates a postoperative evaluation window. Complete pathology and test records should be reviewed with the care team."
    else:
        status = TreatmentStatus.SURVEILLANCE
        explanation = "More time has elapsed since surgery, so the system prioritizes information relevant to the recorded treatment and surveillance stage."

    topics = ["Confirm that the pathology report and operative note are complete", "Confirm the current stage and follow-up plan with the responsible clinician"]
    if missing:
        topics.append("Add the essential pathology or molecular-test information flagged by the system")

    return JourneyAssessment(
        current_status=status,
        confidence="low" if status is TreatmentStatus.UNKNOWN or missing else "moderate",
        explanation=explanation,
        missing_information=missing,
        next_discussion_topics=topics,
        emergency_notice=None,
    )
