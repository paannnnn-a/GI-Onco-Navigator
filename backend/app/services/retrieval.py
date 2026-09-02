from __future__ import annotations

import re

from backend.app.schemas import Citation, EvidenceType
from backend.app.storage import Database, evidence_type_priority


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
    rows = database.search(
        to_fts_query(question),
        cancer_type=cancer_type,
        limit=max(limit * 3, 12),
        approved_only=approved_only,
    )
    rows.sort(key=lambda row: (evidence_type_priority(str(row["evidence_type"])), row["lexical_score"]))
    return rows[:limit]


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
