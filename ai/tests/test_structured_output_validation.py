import json

from contractforge_ai.evaluation import validate_model_output


def _valid_review_payload():
    return {
        "kind": "review",
        "summary": "Merge keys need not_null protection.",
        "recommendations": ["Add merge keys to quality_rules.not_null."],
        "evidence": ["Deterministic finding write.keys.nullable."],
        "assumptions": [],
        "decisions_required": [],
        "confidence": 0.86,
        "review_required": True,
    }


def test_validate_model_output_accepts_valid_payload():
    result = validate_model_output(json.dumps(_valid_review_payload()), prompt="review.enrichment.v1")

    assert result.status == "PASS"
    assert result.data == _valid_review_payload()
    assert result.findings == []


def test_validate_model_output_rejects_invalid_json_with_fallback():
    fallback = {"status": "WARN", "api_key": "secret-value"}

    result = validate_model_output("not-json", prompt="review.enrichment.v1", deterministic_fallback=fallback)

    assert result.status == "FAIL"
    assert result.findings[0].code == "structured_output.invalid_json"
    assert result.deterministic_fallback == {"status": "WARN", "api_key": "[REDACTED]"}


def test_validate_model_output_rejects_missing_required_field():
    payload = _valid_review_payload()
    payload.pop("review_required")

    result = validate_model_output(payload, prompt="review.enrichment.v1", deterministic_fallback={"status": "WARN"})

    assert result.status == "FAIL"
    assert result.data is None
    assert any(finding.code == "structured_output.required_missing" for finding in result.findings)
    assert result.deterministic_fallback == {"status": "WARN"}


def test_validate_model_output_rejects_additional_property():
    payload = _valid_review_payload()
    payload["unsafe_extra"] = "not allowed"

    result = validate_model_output(payload, prompt="review.enrichment.v1")

    assert result.status == "FAIL"
    assert any(finding.code == "structured_output.additional_property" for finding in result.findings)


def test_validate_model_output_rejects_wrong_kind_and_confidence_range():
    payload = _valid_review_payload()
    payload["kind"] = "explain"
    payload["confidence"] = 1.2

    result = validate_model_output(payload, prompt="review.enrichment.v1")

    assert result.status == "FAIL"
    assert any(finding.code == "structured_output.const_mismatch" for finding in result.findings)
    assert any(finding.code == "structured_output.number_above_maximum" for finding in result.findings)


def test_validate_model_output_redacts_secret_like_fields_on_success():
    payload = _valid_review_payload()
    payload["recommendations"] = ["Rotate token if it was exposed."]

    result = validate_model_output(payload, prompt="review.enrichment.v1")

    assert result.status == "PASS"
    assert "Rotate token" in result.data["recommendations"][0]
