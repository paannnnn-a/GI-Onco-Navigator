from __future__ import annotations

import re
from collections import Counter
from math import sqrt

from backend.app.schemas import Citation, EvidenceType
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
        fused.append(row)
    fused.sort(
        key=lambda row: (
            evidence_type_priority(str(row["evidence_type"])),
            -float(row["retrieval_score"]),
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
            int(row["timestamp_start_seconds"]) if row.get("timestamp_start_seconds") else None
        ),
        excerpt=str(row["text"])[:500],
        public_url=str(row["public_url"]) if row.get("public_url") else None,
        review_status=str(row["review_status"]),
    )
