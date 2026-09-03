from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from backend.app.schemas import PatientProfile
from backend.app.services.citation_guard import CitationValidationError, validate_citations
from backend.app.services.journey import assess_journey
from backend.app.services.retrieval import citation_from_row, retrieve
from backend.app.services.safety import classify_question
from backend.app.storage import REQUIRED_REVIEW_DIMENSIONS, Database


@dataclass(frozen=True)
class BenchmarkResult:
    cases: int
    journey_accuracy: float
    safety_accuracy: float
    retrieval_cases: int
    retrieval_recall_at_k: float
    citation_validity: float
    refusal_accuracy: float
    dangerous_advice_rate: float
    failures: list[dict[str, object]]


def _load_cases(case_dir: str | Path) -> list[tuple[str, dict[str, object]]]:
    cases: list[tuple[str, dict[str, object]]] = []
    for path in sorted(Path(case_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload if isinstance(payload, list) else [payload]
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                raise TypeError(f"{path} case {index} must be a JSON object")
            case_id = str(entry.get("case_id") or f"{path.stem}:{index}")
            cases.append((case_id, entry))
    return cases


def run_benchmark(case_dir: str | Path) -> BenchmarkResult:
    failures: list[dict[str, object]] = []
    journey_correct = safety_correct = 0
    retrieval_cases = retrieval_hits = citation_valid = 0
    refusal_cases = refusal_correct = safety_sensitive_cases = dangerous_allowed = 0
    cases = _load_cases(case_dir)
    with tempfile.TemporaryDirectory() as directory:
        database = Database(Path(directory) / "benchmark.db")
        for case_id, case in cases:
            profile = PatientProfile.model_validate(case["patient"])
            reference_date = date.fromisoformat(
                case.get("reference_date", datetime.now(UTC).date().isoformat())
            )
            journey = assess_journey(profile, today=reference_date).current_status.value
            decision = classify_question(case["question"], profile.symptoms)
            safety = decision.category
            journey_correct += journey == case["expected_journey"]
            safety_correct += safety == case["expected_safety"]
            if case.get("expected_safety") in {"possible_emergency", "individual_treatment_instruction"}:
                safety_sensitive_cases += 1
                dangerous_allowed += decision.allowed
            if "expected_refusal" in case:
                refusal_cases += 1
                refusal_correct += bool(case["expected_refusal"]) == (not decision.allowed)
            for evidence in case.get("evidence", []):
                source_id = evidence["source_id"]
                database.add_source(
                    {
                        "source_id": source_id, "title": evidence["title"],
                        "evidence_type": evidence.get("evidence_type", "patient_education"),
                        "version": evidence.get("version", "benchmark"), "publication_date": None,
                        "cancer_types": [profile.cancer_type.value], "intended_audience": "patient",
                        "copyright_status": "synthetic_benchmark", "license_name": None,
                        "public_url": None, "local_filename": None, "sha256": None,
                        "supersedes_source_id": None, "review_status": "quarantined", "metadata": {},
                    }
                )
                database.add_chunk(
                    {
                        "chunk_id": f"{case_id}:{source_id}", "source_id": source_id, "ordinal": 0,
                        "text": evidence["text"], "page_start": evidence.get("page_start", 1),
                        "page_end": evidence.get("page_start", 1), "timestamp_start_seconds": None,
                        "timestamp_end_seconds": None, "section_path": [],
                        "cancer_types": [profile.cancer_type.value], "tags": evidence.get("tags", []),
                        "extraction_method": "synthetic_benchmark", "review_status": "quarantined",
                        "content_hash": f"benchmark-{case_id}-{source_id}",
                    }
                )
                for dimension in REQUIRED_REVIEW_DIMENSIONS:
                    database.review_source(
                        source_id, dimension, "approved", "Benchmark fixture", "Synthetic benchmark evidence review marker."
                    )
            expected_sources = set(case.get("expected_source_ids", []))
            if expected_sources:
                retrieval_cases += 1
                rows = retrieve(database, case["question"], profile.cancer_type.value)
                returned = {str(row["source_id"]) for row in rows}
                retrieval_hits += bool(returned & expected_sources)
                try:
                    validate_citations([citation_from_row(row) for row in rows])
                    citation_valid += 1
                except CitationValidationError:
                    pass
            if journey != case["expected_journey"] or safety != case["expected_safety"]:
                failures.append({"case": case_id, "journey": journey, "safety": safety})
    count = len(cases)
    return BenchmarkResult(
        cases=count,
        journey_accuracy=journey_correct / count if count else 0,
        safety_accuracy=safety_correct / count if count else 0,
        retrieval_cases=retrieval_cases,
        retrieval_recall_at_k=retrieval_hits / retrieval_cases if retrieval_cases else 0,
        citation_validity=citation_valid / retrieval_cases if retrieval_cases else 0,
        refusal_accuracy=refusal_correct / refusal_cases if refusal_cases else 0,
        dangerous_advice_rate=(
            dangerous_allowed / safety_sensitive_cases if safety_sensitive_cases else 0
        ),
        failures=failures,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(asdict(run_benchmark(args.case_dir)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
