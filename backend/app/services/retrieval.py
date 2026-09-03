from __future__ import annotations

import json
import re
from collections import Counter
from math import sqrt

from backend.app.schemas import Citation, EvidenceType, TreatmentStatus
from backend.app.storage import Database, evidence_type_priority

CONCEPT_ALIASES = {
    "复查": "复诊随访",
    "复诊": "复诊随访",
    "回医院": "复诊随访",
    "检查报告": "病理检查资料",
    "病理报告": "病理检查资料",
    "吃饭": "饮食营养",
    "食谱": "饮食营养",
    "锻炼": "运动活动",
}

# These vocabularies are navigation topics, not treatment rules. They provide a
# small, auditable reranking signal while the evidence hierarchy remains the
# primary ordering constraint.
PHASE_TOPICS: dict[TreatmentStatus, str] = {
    TreatmentStatus.POSTOPERATIVE_RECOVERY: (
        "early postoperative recovery discharge wound stoma pain symptoms nutrition "
        "hydration activity 术后恢复 出院 伤口 造口 疼痛 症状 营养 饮水 活动"
    ),
    TreatmentStatus.PATHOLOGY_REVIEW: (
        "pathology report operative note margin lymph node stage MMR MSI molecular test "
        "病理报告 手术记录 切缘 淋巴结 分期 错配修复 微卫星 分子检测"
    ),
    TreatmentStatus.ADJUVANT_EVALUATION: (
        "postoperative evaluation pathology stage molecular test multidisciplinary visit "
        "questions discussion preparation 术后评估 病理 分期 分子检测 多学科 复诊 问题准备"
    ),
    TreatmentStatus.ACTIVE_TREATMENT: (
        "treatment monitoring adverse effects symptom log laboratory test contact care team "
        "治疗监测 不良反应 症状记录 实验室检查 联系医疗团队"
    ),
    TreatmentStatus.SURVEILLANCE: (
        "surveillance follow-up recurrence monitoring appointment records long-term health "
        "随访 复查 复诊 复发监测 就诊记录 长期健康"
    ),
    TreatmentStatus.REHABILITATION: (
        "rehabilitation recovery nutrition activity function quality of life psychosocial support "
        "康复 恢复 营养 活动 功能 生活质量 心理支持"
    ),
    TreatmentStatus.UNKNOWN: (
        "surgery date pathology report current treatment medical records visit preparation "
        "手术日期 病理报告 当前治疗 医疗记录 就诊准备"
    ),
}


def normalize_concepts(text: str) -> str:
    normalized = text.lower().strip()
    for alias, canonical in CONCEPT_ALIASES.items():
        normalized = normalized.replace(alias, f" {canonical} ")
    return normalized


def semantic_features(text: str) -> Counter[str]:
    normalized = normalize_concepts(text)
    features: list[str] = re.findall(r"[a-z0-9_.+-]+", normalized)
    for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
        features.extend(run[index : index + 2] for index in range(len(run) - 1))
    return Counter(features)


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    norm_left = sqrt(sum(value * value for value in left.values()))
    norm_right = sqrt(sum(value * value for value in right.values()))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


def phase_relevance(row: dict[str, object], journey_status: str | None) -> float:
    if not journey_status:
        return 0.0
    try:
        status = TreatmentStatus(journey_status)
    except ValueError:
        return 0.0
    tags = " ".join(json.loads(str(row.get("tags_json") or "[]")))
    candidate = semantic_features(f"{row.get('text', '')} {tags}")
    return cosine_similarity(semantic_features(PHASE_TOPICS[status]), candidate)


def to_fts_query(question: str) -> str:
    latin_terms = re.findall(r"[A-Za-z0-9_.+-]+", question)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", question)
    cjk_terms = [run[index : index + 2] for run in cjk_runs for index in range(len(run) - 1)]
    terms = latin_terms + cjk_terms
    return " OR ".join(f'"{term}"' for term in terms[:12]) or '"empty"'


def retrieve(
    database: Database,
    question: str,
    cancer_type: str | None,
    limit: int = 6,
    approved_only: bool = True,
    journey_status: str | None = None,
) -> list[dict[str, object]]:
    lexical_rows = database.search(
        to_fts_query(normalize_concepts(question)),
        cancer_type=cancer_type,
        limit=max(limit * 3, 12),
        approved_only=approved_only,
    )
    if not approved_only:
        lexical_rows.sort(
            key=lambda row: (evidence_type_priority(str(row["evidence_type"])), row["lexical_score"])
        )
        return lexical_rows[:limit]

    candidates = database.approved_candidates(cancer_type)
    query_features = semantic_features(question)
    semantic_rows = sorted(
        candidates,
        key=lambda row: cosine_similarity(query_features, semantic_features(str(row["text"]))),
        reverse=True,
    )[: max(limit * 4, 20)]
    lexical_rank = {str(row["chunk_id"]): rank for rank, row in enumerate(lexical_rows, start=1)}
    semantic_rank = {str(row["chunk_id"]): rank for rank, row in enumerate(semantic_rows, start=1)}
    by_id = {str(row["chunk_id"]): row for row in candidates}
    fused: list[dict[str, object]] = []
    for chunk_id in set(lexical_rank) | set(semantic_rank):
        row = dict(by_id[chunk_id])
        similarity = cosine_similarity(query_features, semantic_features(str(row["text"])))
        if chunk_id not in lexical_rank and similarity <= 0:
            continue
        rrf = (1 / (60 + lexical_rank[chunk_id]) if chunk_id in lexical_rank else 0) + (
            1 / (60 + semantic_rank[chunk_id]) if chunk_id in semantic_rank else 0
        )
        row["retrieval_score"] = rrf + similarity * 0.1
        row["phase_relevance"] = phase_relevance(row, journey_status)
        fused.append(row)
    fused.sort(
        key=lambda row: (
            evidence_type_priority(str(row["evidence_type"])),
            -(float(row["retrieval_score"]) + float(row["phase_relevance"]) * 0.05),
        )
    )
    return fused[:limit]


def citation_from_row(row: dict[str, object]) -> Citation:
    return Citation(
        source_id=str(row["source_id"]),
        title=str(row["title"]),
        evidence_type=EvidenceType(str(row["evidence_type"])),
        version=str(row["version"]) if row.get("version") else None,
        page_start=int(row["page_start"]) if row.get("page_start") else None,
        page_end=int(row["page_end"]) if row.get("page_end") else None,
        timestamp_start_seconds=(
            int(row["timestamp_start_seconds"])
            if row.get("timestamp_start_seconds") is not None
            else None
        ),
        excerpt=str(row["text"])[:500],
        public_url=str(row["public_url"]) if row.get("public_url") else None,
        section_path=json.loads(str(row.get("section_path_json") or "[]")),
        review_status=str(row["review_status"]),
    )
