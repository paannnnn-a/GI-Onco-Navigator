from datetime import UTC, date, datetime

from backend.app.schemas import (
    JourneyAssessment,
    MissingInformation,
    PatientProfile,
    TreatmentStatus,
)

REQUIRED_PATHOLOGY_FIELDS = (
    ("pathological_stage", "病理分期", "用于定位术后风险评估和随访讨论范围"),
    ("margin_status", "切缘状态", "用于确认手术病理信息是否完整"),
    ("mismatch_repair_status", "MMR/MSI 状态", "可能影响后续风险评估和讨论内容"),
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
        explanation = "档案显示目前正在接受后续治疗，应围绕治疗期间监测和复诊问题导航。"
    elif days_since_surgery is None:
        status = TreatmentStatus.UNKNOWN
        explanation = "尚未记录手术日期，系统无法可靠判断当前术后阶段。"
    elif days_since_surgery < 0:
        status = TreatmentStatus.UNKNOWN
        explanation = "手术日期晚于当前日期，请核对档案。"
    elif days_since_surgery <= 14:
        status = TreatmentStatus.POSTOPERATIVE_RECOVERY
        explanation = "当前处于早期术后恢复窗口，导航重点是恢复情况和病理资料准备。"
    elif missing:
        status = TreatmentStatus.PATHOLOGY_REVIEW
        explanation = "已进入术后病理信息整理阶段，但关键资料仍不完整。"
    elif days_since_surgery <= 56:
        status = TreatmentStatus.ADJUVANT_EVALUATION
        explanation = "档案信息提示处于术后进一步治疗评估窗口，应与诊疗团队核对完整病理和检查资料。"
    else:
        status = TreatmentStatus.SURVEILLANCE
        explanation = "距离手术已有一段时间，系统将优先检索与当前治疗记录和随访阶段相关的信息。"

    topics = ["确认病理报告和手术记录是否完整", "向主管医生核对当前阶段和复诊计划"]
    if missing:
        topics.append("补充系统标出的关键病理或分子检测信息")

    return JourneyAssessment(
        current_status=status,
        confidence="low" if status is TreatmentStatus.UNKNOWN or missing else "moderate",
        explanation=explanation,
        missing_information=missing,
        next_discussion_topics=topics,
        emergency_notice=None,
    )
