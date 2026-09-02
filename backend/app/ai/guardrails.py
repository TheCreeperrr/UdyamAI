import re
from typing import Any

_REQUIRED_FIELDS = {
    "summary",
    "recommendation",
    "reasoning",
    "financial_advice",
    "market_advice",
    "competition_advice",
    "scheme_advice",
    "risks",
    "next_steps",
    "disclaimers",
    "sources",
    "confidence",
    "model_name",
    "prompt_version",
    "language",
}
_ALLOWED_LANGUAGES = {"en", "hi", "mr"}
_ALLOWED_CONFIDENCE = {"high", "medium", "low", "unverified"}
_ALLOWED_SOURCE_TYPES = {"document", "scheme_rule", "data_source"}


def _contains_invented_financial_claim(text: str, context: dict[str, Any]) -> bool:
    if not isinstance(text, str):
        return False

    lower_text = text.lower()
    percent_pattern = re.compile(r"(?<!\w)\d+(?:,\d{3})*(?:\.\d+)?\s*%")
    currency_pattern = re.compile(
        r"(?:₹|rs\.?|rupees?)\s*\d+(?:,\d{3})*(?:\.\d+)?|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:lakhs?|crores?|cr|lakh|crore)\b",
        re.IGNORECASE,
    )
    number_pattern = re.compile(r"(?<!\w)\d+(?:,\d{3})*(?:\.\d+)?(?!\w)")

    if any(keyword in lower_text for keyword in ["subsidy", "loan", "interest", "emi", "price"]):
        if percent_pattern.search(lower_text) or currency_pattern.search(lower_text):
            return True

    if any(keyword in lower_text for keyword in ["project cost", "capital requirement", "monthly emi", "cost", "price"]):
        if number_pattern.search(lower_text) and "backend" not in lower_text and "verified" not in lower_text:
            return True

    if any(keyword in lower_text for keyword in ["guaranteed", "definitely", "assured", "certainly"]):
        return True

    if ("approved" in lower_text or "approval" in lower_text) and "not" not in lower_text:
        if "requires verification" not in lower_text and "potentially" not in lower_text:
            return True

    if "market price" in lower_text and currency_pattern.search(lower_text):
        return True

    if "per unit" in lower_text and number_pattern.search(lower_text):
        return True

    return False


def _validate_source_entry(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError(
            "Each source entry must be an object with claim, source_type and reference_id."
        )

    required_fields = {"claim", "source_type", "reference_id"}
    missing = sorted(required_fields - set(source.keys()))
    if missing:
        raise ValueError(f"Source entry is missing required fields: {', '.join(missing)}")

    claim = str(source.get("claim", "")).strip()
    if not claim:
        raise ValueError("Source claim cannot be empty.")

    source_type = str(source.get("source_type", "")).lower()
    if source_type not in _ALLOWED_SOURCE_TYPES:
        raise ValueError("Source type must be one of: document, scheme_rule, data_source.")

    reference_id = source.get("reference_id")
    if reference_id is None or str(reference_id).strip() == "":
        raise ValueError("Source reference_id cannot be empty.")

    return {
        "claim": claim,
        "source_type": source_type,
        "reference_id": reference_id,
    }


def validate(raw_output: dict, context: dict) -> dict:
    """Validate and normalize AI output before returning it to the backend."""
    if not isinstance(raw_output, dict):
        raise ValueError("AI output must be a JSON object.")

    missing = sorted(_REQUIRED_FIELDS - set(raw_output.keys()))
    if missing:
        raise ValueError(f"AI output is missing required fields: {', '.join(missing)}")

    for field in [
        "summary",
        "recommendation",
    ]:
        value = raw_output.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"AI field '{field}' must be a non-empty string.")

    for field in [
        "reasoning",
        "financial_advice",
        "market_advice",
        "competition_advice",
        "scheme_advice",
        "risks",
        "next_steps",
        "disclaimers",
    ]:
        items = raw_output.get(field, [])
        if not isinstance(items, list):
            raise ValueError(f"AI field '{field}' must be a list.")

    sources = raw_output.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("AI field 'sources' must be a list.")
    normalized_sources = [_validate_source_entry(item) for item in sources]

    normalized = dict(raw_output)
    normalized["summary"] = str(raw_output["summary"]).strip()
    normalized["recommendation"] = str(raw_output["recommendation"]).strip()
    normalized["sources"] = normalized_sources

    normalized["language"] = str(raw_output.get("language", "en")).lower()
    if normalized["language"] not in _ALLOWED_LANGUAGES:
        raise ValueError("AI language must be one of: en, hi, mr.")

    normalized["confidence"] = str(raw_output.get("confidence", "unverified")).lower()
    if normalized["confidence"] not in _ALLOWED_CONFIDENCE:
        raise ValueError("AI confidence must be one of: high, medium, low, unverified.")

    normalized["model_name"] = str(raw_output.get("model_name", "unknown-model"))
    normalized["prompt_version"] = str(raw_output.get("prompt_version", "unknown-v1"))

    text_items = [
        normalized["summary"],
        normalized["recommendation"],
        *[
            item
            for field in [
                "reasoning",
                "financial_advice",
                "market_advice",
                "competition_advice",
                "scheme_advice",
                "risks",
                "next_steps",
                "disclaimers",
            ]
            for item in normalized.get(field, [])
            if isinstance(item, str)
        ],
    ]
    for text in text_items:
        if _contains_invented_financial_claim(text, context):
            raise ValueError(
                "AI output contains invented financial or subsidy claims not supported by backend context."
            )

    return normalized
