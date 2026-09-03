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


def test_profile_red_flag_blocks_vague_question() -> None:
    decision = classify_question("我现在应该注意什么？", symptoms=["大量出血"])
    assert decision.allowed is False
    assert decision.category == "possible_emergency"


def test_blocks_english_prescriptive_question() -> None:
    decision = classify_question("Which chemotherapy should I use and at what exact dose?")
    assert decision.allowed is False
    assert decision.category == "individual_treatment_instruction"


def test_escalates_english_emergency_question() -> None:
    decision = classify_question("I have severe abdominal pain and cannot eat or drink.")
    assert decision.allowed is False
    assert decision.category == "possible_emergency"


def test_english_profile_red_flag_blocks_vague_question() -> None:
    decision = classify_question("What should I prepare?", symptoms=["shortness of breath"])
    assert decision.allowed is False
    assert decision.category == "possible_emergency"


def test_allows_english_education_navigation() -> None:
    decision = classify_question("Which fields should I locate in my pathology report?")
    assert decision.allowed is True
