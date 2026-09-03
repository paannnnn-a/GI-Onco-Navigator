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
CREATE TABLE IF NOT EXISTS patient_reminders (
  reminder_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  due_at TEXT NOT NULL,
  source_note TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_patient_reminders_due ON patient_reminders(patient_id, due_at);
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
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_source_reviews_source ON source_reviews(source_id, review_id);
CREATE TABLE IF NOT EXISTS source_status_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
  previous_status TEXT NOT NULL,
  new_status TEXT NOT NULL,
  actor TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_source_status_events_source
  ON source_status_events(source_id, event_id);
CREATE TABLE IF NOT EXISTS facilities (
  facility_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  province TEXT NOT NULL,
  city TEXT NOT NULL,
  official_registration_url TEXT NOT NULL,
  official_website TEXT,
  cancer_types_json TEXT NOT NULL,
  service_tags_json TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  verified_at TEXT NOT NULL,
  verification_note TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facilities_location ON facilities(province, city);
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
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(source_reviews)").fetchall()
            }
            if "active" not in columns:
                connection.execute(
                    "ALTER TABLE source_reviews ADD COLUMN active INTEGER NOT NULL DEFAULT 1"
                )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
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

    def ping(self) -> bool:
        try:
            with self.connect() as connection:
                return connection.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def get_patient(self, patient_id: str) -> PatientProfile | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM patients WHERE patient_id = ?", (patient_id,)
            ).fetchone()
        return PatientProfile.model_validate_json(row["payload_json"]) if row else None

    def delete_patient(self, patient_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
            connection.execute("DELETE FROM audit_events WHERE subject_id = ?", (patient_id,))
        return cursor.rowcount > 0

    def count_audit_events(self, subject_id: str | None) -> int:
        with self.connect() as connection:
            if subject_id is None:
                row = connection.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE subject_id IS NULL"
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE subject_id = ?", (subject_id,)
                ).fetchone()
        return int(row[0])

    def add_reminder(self, reminder: dict[str, object]) -> dict[str, object]:
        with self.connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO patient_reminders(
                      reminder_id,patient_id,title,due_at,source_note,status
                    ) VALUES (:reminder_id,:patient_id,:title,:due_at,:source_note,:status)""",
                    reminder,
                )
            except sqlite3.IntegrityError as exc:
                raise KeyError(str(reminder["patient_id"])) from exc
            row = connection.execute(
                "SELECT * FROM patient_reminders WHERE reminder_id = ?", (reminder["reminder_id"],)
            ).fetchone()
        return dict(row)

    def list_reminders(self, patient_id: str) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM patient_reminders WHERE patient_id = ? ORDER BY due_at, created_at",
                (patient_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_reminder_status(
        self, patient_id: str, reminder_id: str, status: str
    ) -> dict[str, object] | None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE patient_reminders SET status = ? WHERE reminder_id = ? AND patient_id = ?",
                (status, reminder_id, patient_id),
            )
            row = connection.execute(
                "SELECT * FROM patient_reminders WHERE reminder_id = ? AND patient_id = ?",
                (reminder_id, patient_id),
            ).fetchone()
        return dict(row) if row else None

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

    def reset_source_for_ingestion(self, source_id: str) -> None:
        """Invalidate prior chunks and reviews before replacing source content."""
        with self.connect() as connection:
            chunk_ids = connection.execute(
                "SELECT chunk_id FROM evidence_chunks WHERE source_id = ?", (source_id,)
            ).fetchall()
            connection.executemany(
                "DELETE FROM evidence_fts WHERE chunk_id = ?",
                ((row["chunk_id"],) for row in chunk_ids),
            )
            connection.execute("DELETE FROM evidence_chunks WHERE source_id = ?", (source_id,))
            connection.execute(
                "UPDATE source_reviews SET active = 0 WHERE source_id = ?", (source_id,)
            )
            connection.execute(
                "UPDATE sources SET review_status = 'quarantined' WHERE source_id = ?", (source_id,)
            )

    def review_source(
        self, source_id: str, dimension: str, decision: str, reviewer: str, reason: str
    ) -> dict[str, object]:
        if dimension not in REQUIRED_REVIEW_DIMENSIONS:
            raise ValueError("unsupported review dimension")
        if decision not in {"approved", "rejected"}:
            raise ValueError("unsupported review decision")
        with self.connect() as connection:
            source = connection.execute(
                "SELECT source_id,local_filename,metadata_json FROM sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if source is None:
                raise KeyError(source_id)
            if dimension == "extraction_quality" and decision == "approved":
                filename = str(source["local_filename"] or "").lower()
                if filename.endswith(".pdf"):
                    metadata = json.loads(str(source["metadata_json"] or "{}"))
                    audit = metadata.get("extraction_audit")
                    if not isinstance(audit, dict):
                        raise ValueError("PDF extraction quality requires a recorded page audit")
                    if int(audit.get("pages_needing_ocr", 0)) > 0:
                        raise ValueError(
                            "PDF extraction quality cannot pass while pages still need OCR"
                        )
            connection.execute(
                """INSERT INTO source_reviews(source_id,dimension,decision,reviewer,reason)
                VALUES (?,?,?,?,?)""",
                (source_id, dimension, decision, reviewer, reason),
            )
            latest = connection.execute(
                """SELECT r.dimension, r.decision FROM source_reviews r
                JOIN (
                  SELECT dimension, MAX(review_id) review_id FROM source_reviews
                  WHERE source_id = ? AND active = 1 GROUP BY dimension
                ) current ON current.review_id = r.review_id""",
                (source_id,),
            ).fetchall()
            decisions = {row["dimension"]: row["decision"] for row in latest}
            if "rejected" in decisions.values():
                status = "rejected"
            elif all(decisions.get(item) == "approved" for item in REQUIRED_REVIEW_DIMENSIONS):
                source_details = connection.execute(
                    "SELECT copyright_status FROM sources WHERE source_id = ?", (source_id,)
                ).fetchone()
                if source_details["copyright_status"] in {"unknown", "metadata_only"}:
                    raise ValueError("patient publication requires a resolved copyright status")
                chunk_quality = connection.execute(
                    """SELECT COUNT(*) total,
                      SUM(CASE WHEN page_start IS NULL AND timestamp_start_seconds IS NULL
                        AND section_path_json = '[]' THEN 1 ELSE 0 END) missing_locator
                    FROM evidence_chunks WHERE source_id = ?""",
                    (source_id,),
                ).fetchone()
                if chunk_quality["total"] == 0:
                    raise ValueError("patient publication requires at least one evidence chunk")
                if chunk_quality["missing_locator"]:
                    raise ValueError("every patient-facing evidence chunk requires a locator")
                status = "approved"
            else:
                status = "review_in_progress"
            connection.execute("UPDATE sources SET review_status = ? WHERE source_id = ?", (status, source_id))
            connection.execute(
                "UPDATE evidence_chunks SET review_status = ? WHERE source_id = ?", (status, source_id)
            )
            if status == "approved":
                superseded = connection.execute(
                    "SELECT supersedes_source_id FROM sources WHERE source_id = ?", (source_id,)
                ).fetchone()["supersedes_source_id"]
                if superseded and superseded != source_id:
                    old = connection.execute(
                        "SELECT review_status FROM sources WHERE source_id = ?", (superseded,)
                    ).fetchone()
                    if old and old["review_status"] == "approved":
                        connection.execute(
                            "UPDATE sources SET review_status = 'outdated' WHERE source_id = ?",
                            (superseded,),
                        )
                        connection.execute(
                            "UPDATE evidence_chunks SET review_status = 'outdated' WHERE source_id = ?",
                            (superseded,),
                        )
                        connection.execute(
                            "UPDATE source_reviews SET active = 0 WHERE source_id = ?", (superseded,)
                        )
                        connection.execute(
                            """INSERT INTO source_status_events(
                              source_id,previous_status,new_status,actor,reason
                            ) VALUES (?,?,?,?,?)""",
                            (
                                superseded, "approved", "outdated", reviewer,
                                f"Explicitly superseded by reviewed source {source_id}.",
                            ),
                        )
        return self.get_review_state(source_id)

    def transition_source_status(
        self, source_id: str, new_status: str, actor: str, reason: str
    ) -> dict[str, object]:
        if new_status not in {"quarantined", "outdated", "withdrawn"}:
            raise ValueError("unsupported lifecycle status")
        with self.connect() as connection:
            source = connection.execute(
                "SELECT review_status FROM sources WHERE source_id = ?", (source_id,)
            ).fetchone()
            if source is None:
                raise KeyError(source_id)
            previous = str(source["review_status"])
            connection.execute(
                "UPDATE sources SET review_status = ? WHERE source_id = ?", (new_status, source_id)
            )
            connection.execute(
                "UPDATE evidence_chunks SET review_status = ? WHERE source_id = ?",
                (new_status, source_id),
            )
            connection.execute(
                "UPDATE source_reviews SET active = 0 WHERE source_id = ?", (source_id,)
            )
            connection.execute(
                """INSERT INTO source_status_events(
                  source_id,previous_status,new_status,actor,reason
                ) VALUES (?,?,?,?,?)""",
                (source_id, previous, new_status, actor, reason),
            )
        return {
            "source_id": source_id, "previous_status": previous, "new_status": new_status,
            "actor": actor, "reason": reason,
        }

    def list_source_status_events(self, source_id: str) -> list[dict[str, object]]:
        if self.get_source(source_id) is None:
            raise KeyError(source_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM source_status_events WHERE source_id = ? ORDER BY event_id DESC",
                (source_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_source_chunks(
        self, source_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[int, list[dict[str, object]]]:
        if self.get_source(source_id) is None:
            raise KeyError(source_id)
        with self.connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM evidence_chunks WHERE source_id = ?", (source_id,)
            ).fetchone()[0]
            rows = connection.execute(
                """SELECT chunk_id,ordinal,text,page_start,page_end,timestamp_start_seconds,
                  timestamp_end_seconds,section_path_json,extraction_method,review_status,content_hash
                FROM evidence_chunks WHERE source_id = ? ORDER BY ordinal LIMIT ? OFFSET ?""",
                (source_id, limit, offset),
            ).fetchall()
        items: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            item["section_path"] = json.loads(str(item.pop("section_path_json")))
            items.append(item)
        return int(total), items

    def get_review_state(self, source_id: str) -> dict[str, object]:
        source = self.get_source(source_id)
        if source is None:
            raise KeyError(source_id)
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT r.* FROM source_reviews r JOIN (
                  SELECT dimension, MAX(review_id) review_id FROM source_reviews
                  WHERE source_id = ? AND active = 1 GROUP BY dimension
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

    def approved_candidates(
        self, cancer_type: str | None = None, limit: int = 500
    ) -> list[dict[str, object]]:
        filters = ["c.review_status = 'approved'", "s.review_status = 'approved'"]
        params: list[object] = []
        if cancer_type:
            filters.append("c.cancer_types_json LIKE ?")
            params.append(f'%"{cancer_type}"%')
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT c.*, s.title, s.evidence_type, s.version, s.public_url
                FROM evidence_chunks c JOIN sources s ON s.source_id = c.source_id
                WHERE {' AND '.join(filters)} ORDER BY c.chunk_id LIMIT ?""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def add_facility(self, facility: dict[str, object]) -> None:
        values = {
            **facility,
            "cancer_types_json": json.dumps(facility.get("cancer_types", []), ensure_ascii=False),
            "service_tags_json": json.dumps(facility.get("service_tags", []), ensure_ascii=False),
        }
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO facilities(
                  facility_id,name,province,city,official_registration_url,official_website,
                  cancer_types_json,service_tags_json,verification_status,verified_at,verification_note
                ) VALUES (
                  :facility_id,:name,:province,:city,:official_registration_url,:official_website,
                  :cancer_types_json,:service_tags_json,:verification_status,:verified_at,:verification_note
                ) ON CONFLICT(facility_id) DO UPDATE SET
                  name=excluded.name, province=excluded.province, city=excluded.city,
                  official_registration_url=excluded.official_registration_url,
                  official_website=excluded.official_website,
                  cancer_types_json=excluded.cancer_types_json,
                  service_tags_json=excluded.service_tags_json,
                  verification_status=excluded.verification_status,
                  verified_at=excluded.verified_at,
                  verification_note=excluded.verification_note""",
                values,
            )

    def list_verified_facilities(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM facilities WHERE verification_status = 'verified'
                ORDER BY province, city, name"""
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            item["cancer_types"] = json.loads(str(item.pop("cancer_types_json")))
            item["service_tags"] = json.loads(str(item.pop("service_tags_json")))
            result.append(item)
        return result


def evidence_type_priority(value: str) -> int:
    order = {
        EvidenceType.GUIDELINE.value: 0,
        EvidenceType.PEER_REVIEWED.value: 1,
        EvidenceType.PATIENT_EDUCATION.value: 2,
        EvidenceType.EXPERT_VIDEO.value: 3,
        EvidenceType.OTHER.value: 4,
    }
    return order.get(value, 99)
