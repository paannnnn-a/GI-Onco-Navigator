from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.app.schemas import PatientProfile
from backend.app.services.journey import assess_journey
from backend.app.services.safety import classify_question


@dataclass(frozen=True)
class BenchmarkResult:
    cases: int
    journey_accuracy: float
    safety_accuracy: float
    failures: list[dict[str, object]]


def run_benchmark(case_dir: str | Path) -> BenchmarkResult:
    failures: list[dict[str, object]] = []
    journey_correct = safety_correct = 0
    paths = sorted(Path(case_dir).glob("*.json"))
    for path in paths:
        case = json.loads(path.read_text(encoding="utf-8"))
        profile = PatientProfile.model_validate(case["patient"])
        journey = assess_journey(profile).current_status.value
        safety = classify_question(case["question"]).category
        journey_correct += journey == case["expected_journey"]
        safety_correct += safety == case["expected_safety"]
        if journey != case["expected_journey"] or safety != case["expected_safety"]:
            failures.append({"case": path.stem, "journey": journey, "safety": safety})
    count = len(paths)
    return BenchmarkResult(
        cases=count,
        journey_accuracy=journey_correct / count if count else 0,
        safety_accuracy=safety_correct / count if count else 0,
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
