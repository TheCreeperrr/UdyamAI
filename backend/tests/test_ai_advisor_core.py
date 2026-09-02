import pytest

from app.ai import advisor, context_builder, guardrails, llm, prompts, recommendation


def test_context_builder_builds_safe_prompt_payload():
    analysis_context = {
        "location": {"village": {"name": "Khed"}, "district": {"name": "Pune"}},
        "business": {"category": {"name": "Dairy Farming"}},
        "financial": {
            "available_capital": 50000,
            "required_contribution": 60000,
            "shortfall": 10000,
            "desired_project_cost": 200000,
            "potential_loan": 150000,
        },
        "market": {
            "overall_market_score": 82,
            "demand_level": "High",
            "estimated_target_customers": 500,
        },
        "competition": {
            "total_competitors_count": 6,
            "threat_level": "low",
        },
        "schemes": [
            {"scheme": {"name": "PM FME"}, "match_status": "potential_match", "match_score": 0.8}
        ],
        "feasibility": {
            "overall_score": 76,
            "market_score": 80,
            "financial_score": 74,
            "risk_score": 35,
            "recommendation": "Moderately feasible",
        },
        "risks": [{"title": "Feed cost risk"}],
        "language": "en",
    }

    payload = context_builder.build(analysis_context)

    assert payload["business"]["category_name"] == "Dairy Farming"
    assert payload["financial"]["shortfall"] == 10000
    assert payload["feasibility"]["overall_score"] == 76
    assert "verified" in payload["summary"]["source_note"].lower()


def test_advisor_prompt_mentions_verified_data_and_json_output():
    payload = {
        "business": {"category_name": "Dairy Farming"},
        "financial": {"shortfall": 0},
        "feasibility": {"overall_score": 82},
    }

    prompt = prompts.build_advisor_prompt(payload, language="en")

    assert "verified backend data" in prompt.lower()
    assert "json" in prompt.lower()
    assert "dairy farming" in prompt.lower()


def test_guardrails_validate_keeps_valid_output_and_rejects_invented_numbers():
    good_output = {
        "summary": "Based on verified backend data, the business is feasible.",
        "recommendation": "Proceed with the plan using current risk controls.",
        "reasoning": ["Scores and funding values are based on backend analysis."],
        "financial_advice": ["Use the verified contribution requirement."],
        "market_advice": ["Use the verified market conditions."],
        "competition_advice": ["Account for local competition."],
        "scheme_advice": ["Review the matched schemes."],
        "risks": ["Cost volatility remains a key risk."],
        "next_steps": ["Validate demand before launch."],
        "disclaimers": ["This advice is based on available backend data."],
        "sources": [],
        "confidence": "medium",
        "model_name": "demo-model",
        "prompt_version": "v1",
        "language": "en",
    }

    cleaned = guardrails.validate(good_output, {"financial": {"shortfall": 0}})
    assert cleaned["summary"] == good_output["summary"]

    bad_output = dict(good_output)
    bad_output["summary"] = "The subsidy will cover 90% of the project cost."

    try:
        guardrails.validate(bad_output, {"financial": {"shortfall": 0}})
        raise AssertionError("Expected guardrail validation to reject invented subsidy claims")
    except ValueError:
        pass


def test_guardrails_reject_unsupported_scheme_price_and_approval_claims():
    bad_output = {
        "summary": "The scheme guarantees a 95% subsidy and approval for a market price of ₹150 per unit.",
        "recommendation": "Proceed with the plan using current risk controls.",
        "reasoning": ["Scores and funding values are based on backend analysis."],
        "financial_advice": ["Use the verified contribution requirement."],
        "market_advice": ["Use the verified market conditions."],
        "competition_advice": ["Account for local competition."],
        "scheme_advice": ["Review the matched schemes."],
        "risks": ["Cost volatility remains a key risk."],
        "next_steps": ["Validate demand before launch."],
        "disclaimers": ["This advice is based on available backend data."],
        "sources": [],
        "confidence": "medium",
        "model_name": "demo-model",
        "prompt_version": "v1",
        "language": "en",
    }

    with pytest.raises(ValueError):
        guardrails.validate(bad_output, {"financial": {"shortfall": 0}})


def test_generate_advice_returns_fallback_when_llm_fails(monkeypatch):
    def raise_llm_error(_prompt):
        raise llm.LLMError("Provider timeout", error_code="AI_TIMEOUT")

    monkeypatch.setattr(llm, "generate", raise_llm_error)

    result = advisor.generate_advice({
        "location": {"village": {"name": "Khed"}, "district": {"name": "Pune"}, "taluka": {"name": "Haveli"}},
        "business": {"category": {"name": "Dairy Farming"}, "model": {"name": "Commercial Dairy"}},
        "financial": {"available_capital": 50000, "required_contribution": 60000, "shortfall": 10000},
        "market": {"overall_market_score": 82, "demand_level": "High"},
        "competition": {"total_competitors_count": 3, "threat_level": "low"},
        "schemes": [],
        "feasibility": {"overall_score": 76, "market_score": 80, "financial_score": 74, "risk_score": 35, "recommendation": "Moderately feasible"},
        "language": "en",
    })

    assert result.summary.startswith("AI advisory guidance is temporarily unavailable")
    assert result.confidence == "unverified"


def test_guardrails_reject_market_price_claims_when_data_missing():
    bad_output = {
        "summary": "The market price is ₹150 per unit and the subsidy covers 95% of cost.",
        "recommendation": "Proceed with the plan using current risk controls.",
        "reasoning": ["Scores and funding values are based on backend analysis."],
        "financial_advice": ["Use the verified contribution requirement."],
        "market_advice": ["Use the verified market conditions."],
        "competition_advice": ["Account for local competition."],
        "scheme_advice": ["Review the matched schemes."],
        "risks": ["Cost volatility remains a key risk."],
        "next_steps": ["Validate demand before launch."],
        "disclaimers": ["This advice is based on available backend data."],
        "sources": [],
        "confidence": "medium",
        "model_name": "demo-model",
        "prompt_version": "v1",
        "language": "en",
    }

    with pytest.raises(ValueError):
        guardrails.validate(bad_output, {})


def test_generate_advice_preserves_rag_evidence_sources(monkeypatch):
    raw_response = {
        "summary": "The business appears feasible based on backend and scheme evidence.",
        "recommendation": "Proceed with the plan and verify scheme eligibility before committing capital.",
        "reasoning": ["The project is moderately feasible based on verified backend scores."],
        "financial_advice": ["Use the verified contribution requirement."],
        "market_advice": ["Use the verified market conditions."],
        "competition_advice": ["Account for local competition."],
        "scheme_advice": ["This scheme appears potentially relevant based on the reviewed document evidence."],
        "risks": ["Cost volatility remains a key risk."],
        "next_steps": ["Verify eligibility against the official scheme language."],
        "disclaimers": ["This advice is based on available backend and evidence data."],
        "sources": [],
        "confidence": "medium",
        "model_name": "demo-model",
        "prompt_version": "v1",
        "language": "en",
    }

    def fake_generate(_prompt):
        return raw_response

    monkeypatch.setattr(llm, "generate", fake_generate)

    analysis_context = {
        "location": {"village": {"name": "Khed"}, "district": {"name": "Pune"}, "taluka": {"name": "Haveli"}},
        "business": {"category": {"name": "Dairy Farming"}, "model": {"name": "Commercial Dairy"}},
        "financial": {"available_capital": 50000, "required_contribution": 60000, "shortfall": 10000},
        "market": {"overall_market_score": 82, "demand_level": "High"},
        "competition": {"total_competitors_count": 3, "threat_level": "low"},
        "schemes": [{"scheme": {"name": "PM-FME"}, "match_status": "potential_match", "verification_required": True}],
        "feasibility": {"overall_score": 76, "market_score": 80, "financial_score": 74, "risk_score": 35, "recommendation": "Moderately feasible"},
        "evidence": [{
            "document_id": "11111111-1111-1111-1111-111111111111",
            "title": "PM FME guideline",
            "page_number": 8,
            "section_title": "Eligibility",
            "source_name": "Government guideline",
            "score": 0.91,
            "text": "Eligibility is based on project type and contribution requirements.",
        }],
        "language": "en",
    }

    result = advisor.generate_advice(analysis_context)

    assert result.sources
    assert any(str(item.reference_id) == "11111111-1111-1111-1111-111111111111" for item in result.sources)
    assert any(item.source_type == "document" for item in result.sources)


def test_recommendation_explain_uses_verified_feasibility_scores():
    feasibility = {
        "overall_score": 76,
        "market_score": 80,
        "financial_score": 74,
        "risk_score": 35,
        "recommendation": "Moderately feasible",
    }

    explanation = recommendation.explain(feasibility)

    assert "76" in explanation or "Moderately feasible" in explanation
    assert "market" in explanation.lower()
    assert "financial" in explanation.lower()
