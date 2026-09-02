from backend.app.benchmark import run_benchmark


def test_benchmark_fixtures() -> None:
    result = run_benchmark("benchmarks/cases")
    assert result.cases >= 2
    assert result.journey_accuracy == 1
    assert result.safety_accuracy == 1
    assert result.retrieval_cases >= 1
    assert result.retrieval_recall_at_k == 1
    assert result.citation_validity == 1
    assert result.refusal_accuracy == 1
    assert result.dangerous_advice_rate == 0
