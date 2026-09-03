import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    category: str
    message: str | None = None


PRESCRIPTIVE_PATTERNS = (
    "给我开",
    "替我决定",
    "我该吃什么药",
    "我该用什么化疗",
    "具体剂量",
    "停药",
    "换药",
    "加大剂量",
    "减少剂量",
    "替我选方案",
)

EMERGENCY_PATTERNS = (
    "呼吸困难",
    "意识不清",
    "大量出血",
    "持续高热",
    "无法进食饮水",
    "胸痛",
    "晕厥",
    "伤口裂开",
    "反复呕吐无法进食",
    "剧烈腹痛",
)


def classify_question(question: str, symptoms: Iterable[str] = ()) -> SafetyDecision:
    normalized = re.sub(r"\s+", "", question.strip().lower())
    symptom_text = " ".join(str(item).strip().lower() for item in symptoms)
    combined = f"{normalized} {symptom_text}"
    if any(pattern in combined for pattern in EMERGENCY_PATTERNS):
        return SafetyDecision(
            allowed=False,
            category="possible_emergency",
            message="The situation you described may require immediate medical assessment. Contact local emergency services or go to an emergency department promptly; do not wait for an online answer.",
        )
    if any(pattern in normalized for pattern in PRESCRIPTIVE_PATTERNS):
        return SafetyDecision(
            allowed=False,
            category="individual_treatment_instruction",
            message="The system cannot replace a clinician in selecting a medicine, regimen, or dose for an individual patient. It can help organize questions and relevant evidence for discussion with the care team.",
        )
    return SafetyDecision(allowed=True, category="education_navigation")
