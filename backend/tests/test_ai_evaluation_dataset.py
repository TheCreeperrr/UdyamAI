from app.ai.evaluation.dataset import EVALUATION_DATASET, EXPECTED_CASE_IDS


def test_evaluation_dataset_contains_expected_ai_safety_cases():
    assert len(EVALUATION_DATASET) >= 6
    assert EXPECTED_CASE_IDS == [
        "case_01_sufficient_capital",
        "case_02_insufficient_margin",
        "case_03_high_competition",
        "case_04_missing_market_data",
        "case_05_potential_scheme_match",
        "case_06_no_scheme_match",
        "case_07_conflicting_information",
    ]

    for case in EVALUATION_DATASET:
        assert case["id"]
        assert case["name"]
        assert case["scenario"]
        assert case["expected_quality"]["factual_consistency"] in {"high", "medium"}
        assert case["expected_quality"]["safety"] == "high"
        assert case["expected_quality"]["source_preservation"] == "required"
