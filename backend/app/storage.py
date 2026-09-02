from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.app.schemas import EvidenceType, PatientProfile

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS patients (
  patient_id TEXT PRIMARY KEY,
  payload_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  version TEXT,
  publication_date TEXT,
  cancer_types_json TEXT NOT NULL,
  intended_audience TEXT NOT NULL,
  copyright_status TEXT NOT NULL,
  license_name TEXT,
  public_url TEXT,
  local_filename TEXT,
  sha256 TEXT,
  supersedes_source_id TEXT,
  review_status TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_chunks (
  chunk_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  text TEXT NOT NULL,
  page_start INTEGER,
  page_end INTEGER,
  timestamp_start_seconds INTEGER,
  timestamp_end_seconds INTEGER,
  section_path_json TEXT NOT NULL,
  cancer_types_json TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  review_status TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  UNIQUE(source_id, ordinal)
);
CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
  chunk_id UNINDEXED,
  text,
  tags,
  tokenize='unicode61'
);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON evidence_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_sources_evidence_type ON sources(evidence_type);
CREATE TABLE IF NOT EXISTS audit_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  subject_id TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS source_reviews (
  review_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
  dimension TEXT NOT NULL,
  decision TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_source_reviews_source ON source_reviews(source_id, review_id);
"""

REQUIRED_REVIEW_DIMENSIONS = (
    "copyright",
    "extraction_quality",
    "medical_accuracy",
    "patient_readability",
)


def fts_text(value: str) -> str:
    """Add CJK bigrams because SQLite unicode61 does not segment Chinese words."""
    runs = re.findall(r"[\u4e00-\u9fff]+", value)
    bigrams = [run[index : index + 2] for run in runs for index in range(len(run) - 1)]
    return f"{value} {' '.join(bigrams)}"


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def save_patient(self, profile: PatientProfile) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO patients(patient_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(patient_id) DO UPDATE SET
                  payload_json=excluded.payload_json,
                  updated_at=excluded.updated_at""",
                (
                    profile.patient_id,
                    profile.model_dump_json(),
                    profile.updated_at.isoformat(),
                ),
            )

    def get_patient(self, patient_id: str) -> PatientProfile | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM patients WHERE patient_id = ?", (patient_id,)
            ).fetchone()
        return PatientProfile.model_validate_json(row["payload_json"]) if row else None

    def add_source(self, source: dict[str, object]) -> None:
        values = {
            "cancer_types_json": json.dumps(source.get("cancer_types", []), ensure_ascii=False),
            "metadata_json": json.dumps(source.get("metadata", {}), ensure_ascii=False),
            **source,
        }
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT review_status FROM sources WHERE source_id = ?", (source["source_id"],)
            ).fetchone()
            # Registration and ingestion can never self-approve medical content.
            values["review_status"] = existing["review_status"] if existing else "quarantined"
            connection.execute(
                """INSERT INTO sources(
                  source_id,title,evidence_type,version,publication_date,cancer_types_json,
                  intended_audience,copyright_status,license_name,public_url,local_filename,sha256,
                  supersedes_source_id,review_status,metadata_json
                ) VALUES (
                  :source_id,:title,:evidence_type,:version,:publication_date,:cancer_types_json,
                  :intended_audience,:copyright_status,:license_name,:public_url,:local_filename,:sha256,
                  :supersedes_source_id,:review_status,:metadata_json
                ) ON CONFLICT(source_id) DO UPDATE SET
                  title=excluded.title, evidence_type=excluded.evidence_type,
                  version=excluded.version, publication_date=excluded.publication_date,
                  cancer_types_json=excluded.cancer_types_json,
                  intended_audience=excluded.intended_audience,
                  copyright_status=excluded.copyright_status, license_name=excluded.license_name,
                  public_url=excluded.public_url, local_filename=excluded.local_filename,
                  sha256=excluded.sha256, supersedes_source_id=excluded.supersedes_source_id,
                  metadata_json=excluded.metadata_json""",
                values,
            )

    def list_sources(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sources ORDER BY publication_date DESC, title ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_source(self, source_id: str) -> dict[str, object] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        return dict(row) if row else None

    def review_source(
        self, source_id: str, dimension: str, decision: str, reviewer: str, reason: str
    ) -> dict[str, object]:
        if dimension not in REQUIRED_REVIEW_DIMENSIONS:
            raise ValueError("unsupported review dimension")
        if decision not in {"approved", "rejected"}:
            raise ValueError("unsupported review decision")
        with self.connect() as connection:
            source = connection.execute(
                "SELECT source_id FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()
            if source is None:
                raise KeyError(source_id)
            connection.execute(
                """INSERT INTO source_reviews(source_id,dimension,decision,reviewer,reason)
                VALUES (?,?,?,?,?)""",
                (source_id, dimension, decision, reviewer, reason),
            )
            latest = connection.execute(
                """SELECT r.dimension, r.decision FROM source_reviews r
                JOIN (
                  SELECT dimension, MAX(review_id) review_id FROM source_reviews
                  WHERE source_id = ? GROUP BY dimension
                ) current ON current.review_id = r.review_id""",
                (source_id,),
            ).fetchall()
            decisions = {row["dimension"]: row["decision"] for row in latest}
            if "rejected" in decisions.values():
                status = "rejected"
            elif all(decisions.get(item) == "approved" for item in REQUIRED_REVIEW_DIMENSIONS):
                status = "approved"
            else:
                status = "review_in_progress"
            connection.execute("UPDATE sources SET review_status = ? WHERE source_id = ?", (status, source_id))
            connection.execute(
                "UPDATE evidence_chunks SET review_status = ? WHERE source_id = ?", (status, source_id)
            )
        return self.get_review_state(source_id)

    def get_review_state(self, source_id: str) -> dict[str, object]:
        source = self.get_source(source_id)
        if source is None:
            raise KeyError(source_id)
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT r.* FROM source_reviews r JOIN (
                  SELECT dimension, MAX(review_id) review_id FROM source_reviews
                  WHERE source_id = ? GROUP BY dimension
                ) current ON current.review_id = r.review_id ORDER BY r.dimension""",
                (source_id,),
            ).fetchall()
        return {
            "source_id": source_id,
            "review_status": source["review_status"],
            "required_dimensions": list(REQUIRED_REVIEW_DIMENSIONS),
            "latest_reviews": [dict(row) for row in rows],
        }

    def log_event(self, event_type: str, subject_id: str | None, payload: dict[str, object]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit_events(event_type,subject_id,payload_json) VALUES (?,?,?)",
                (event_type, subject_id, json.dumps(payload, ensure_ascii=False)),
            )

    def add_chunk(self, chunk: dict[str, object]) -> None:
        values = {
            "section_path_json": json.dumps(chunk.get("section_path", []), ensure_ascii=False),
            "cancer_types_json": json.dumps(chunk.get("cancer_types", []), ensure_ascii=False),
            "tags_json": json.dumps(chunk.get("tags", []), ensure_ascii=False),
            **chunk,
        }
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM evidence_fts WHERE chunk_id = ?", (chunk["chunk_id"],)
            )
            connection.execute(
                """INSERT OR REPLACE INTO evidence_chunks(
                  chunk_id,source_id,ordinal,text,page_start,page_end,timestamp_start_seconds,
                  timestamp_end_seconds,section_path_json,cancer_types_json,tags_json,
                  extraction_method,review_status,content_hash
                ) VALUES (
                  :chunk_id,:source_id,:ordinal,:text,:page_start,:page_end,:timestamp_start_seconds,
                  :timestamp_end_seconds,:section_path_json,:cancer_types_json,:tags_json,
                  :extraction_method,:review_status,:content_hash
                )""",
                values,
            )
            connection.execute(
                "INSERT INTO evidence_fts(chunk_id,text,tags) VALUES (?,?,?)",
                (
                    chunk["chunk_id"],
                    fts_text(str(chunk["text"])),
                    fts_text(" ".join(chunk.get("tags", []))),
                ),
            )

    def search(
        self,
        query: str,
        cancer_type: str | None = None,
        limit: int = 8,
        approved_only: bool = False,
    ) -> list[dict[str, object]]:
        filters = ["evidence_fts MATCH ?"]
        params: list[object] = [query]
        if cancer_type:
            filters.append("c.cancer_types_json LIKE ?")
            params.append(f'%"{cancer_type}"%')
        if approved_only:
            filters.append("c.review_status = 'approved'")
            filters.append("s.review_status = 'approved'")
        params.append(limit)
        sql = f"""
          SELECT c.*, s.title, s.evidence_type, s.version, s.public_url,
                 bm25(evidence_fts) AS lexical_score
          FROM evidence_fts
          JOIN evidence_chunks c ON c.chunk_id = evidence_fts.chunk_id
          JOIN sources s ON s.source_id = c.source_id
          WHERE {' AND '.join(filters)}
          ORDER BY lexical_score ASC
          LIMIT ?
        """
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def evidence_type_priority(value: str) -> int:
    order = {
        EvidenceType.GUIDELINE.value: 0,
        EvidenceType.PEER_REVIEWED.value: 1,
        EvidenceType.PATIENT_EDUCATION.value: 2,
        EvidenceType.EXPERT_VIDEO.value: 3,
        EvidenceType.OTHER.value: 4,
    }
    return order.get(value, 99)
