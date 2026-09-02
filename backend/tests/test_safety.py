from backend.app.services.safety import classify_question


def test_blocks_prescriptive_question() -> None:
    decision = classify_question("我该用什么化疗方案？")
    assert decision.allowed is False
    assert decision.category == "individual_treatment_instruction"


def test_escalates_possible_emergency() -> None:
    decision = classify_question("术后大量出血怎么办")
    assert decision.allowed is False
    assert decision.category == "possible_emergency"


def test_allows_education_navigation() -> None:
    decision = classify_question("病理报告里通常需要关注哪些信息？")
    assert decision.allowed is True

