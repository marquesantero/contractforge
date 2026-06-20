from contractforge_ai.validation import validate_generated_contract


def test_validate_generated_contract_passes_reviewable_append_contract():
    result = validate_generated_contract(
        {
            "_metadata": {"draft": True, "review_required": True},
            "source": {"type": "connector", "connector": "files", "path": "/landing/orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
            "mode": "scd0_append",
            "quality_rules": {"not_null": ["order_id"]},
            "operations": {"technical_owner": "data-engineering"},
        }
    )

    assert result.status == "PASS"
    assert result.findings == []
    assert result.traceability.confidence == 1.0


def test_validate_generated_contract_fails_when_required_structure_is_missing():
    result = validate_generated_contract({"mode": "scd1_hash_diff"})

    assert result.status == "FAIL"
    codes = {finding.code for finding in result.findings}
    assert "generated.source.missing" in codes
    assert "generated.target.table_missing" in codes
    assert "generated.merge_keys.missing" in codes
    assert result.traceability.review_required is True


def test_validate_generated_contract_warns_about_review_placeholders():
    result = validate_generated_contract(
        {
            "_metadata": {"draft": True, "review_required": True},
            "source": {"type": "connector", "connector": "files", "path": "/landing/orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
            "mode": "scd0_append",
            "operations": {"technical_owner": "REVIEW_REQUIRED"},
        }
    )

    assert result.status == "WARN"
    assert any(finding.code == "generated.review_placeholder" for finding in result.findings)
