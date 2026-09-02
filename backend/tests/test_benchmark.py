from backend.app.benchmark import run_benchmark


def test_benchmark_fixtures() -> None:
    result = run_benchmark("benchmarks/cases")
    assert result.cases >= 2
    assert result.journey_accuracy == 1
    assert result.safety_accuracy == 1
