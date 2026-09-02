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
            message="你描述的情况可能需要立即医疗评估。请联系当地急救服务或尽快前往急诊，不要等待在线回答。",
        )
    if any(pattern in normalized for pattern in PRESCRIPTIVE_PATTERNS):
        return SafetyDecision(
            allowed=False,
            category="individual_treatment_instruction",
            message="系统不能替代医生为具体患者选择药物、方案或剂量，但可以帮助整理需要与医生讨论的问题和相关循证资料。",
        )
    return SafetyDecision(allowed=True, category="education_navigation")
