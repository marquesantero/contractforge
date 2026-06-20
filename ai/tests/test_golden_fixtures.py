"""Golden fixtures for deterministic ContractForge AI behavior."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractforge_ai.explainers.failure import explain_failure
from contractforge_ai.generators.contract import generate_contract_draft
from contractforge_ai.generators.metadata import suggest_metadata
from contractforge_ai.generators.shape import suggest_shape
from contractforge_ai.reviewers.contract import review_contract

FIXTURES = Path(__file__).parent / "fixtures" / "golden"


def test_golden_contract_review_high_risk_key_quality():
    contract = FIXTURES / "review" / "high_risk_missing_key_quality.yaml"
    expected = _load_expected(FIXTURES / "review" / "high_risk_missing_key_quality.expected.json")

    result = review_contract(contract)

    assert {
        "status": result.status,
        "risk": result.risk,
        "summary": result.summary,
        "finding_codes": [finding.code for finding in result.findings],
    } == expected


def test_golden_failure_explainer_network_egress():
    evidence = FIXTURES / "explain" / "network_egress_failure.json"
    expected = _load_expected(FIXTURES / "explain" / "network_egress_failure.expected.json")

    result = explain_failure(evidence)

    assert {
        "status": result.status,
        "primary_category": result.primary_category,
        "risk": result.risk,
        "finding_codes": [finding.code for finding in result.findings],
        "recommended_action_count": len(result.recommended_actions),
    } == expected


def test_golden_metadata_suggestions_for_orders_schema():
    schema = FIXTURES / "suggest" / "orders_schema.json"
    expected = _load_expected(FIXTURES / "suggest" / "orders_metadata.expected.json")

    result = suggest_metadata(schema)

    assert {
        "quality_not_null": result.quality_rules["not_null"],
        "accepted_values": result.quality_rules["accepted_values"],
        "expression_names": [item["name"] for item in result.quality_rules["expressions"]],
        "pii_columns": [
            name
            for name, metadata in result.annotations["columns"].items()
            if metadata.get("pii", {}).get("enabled") is True
        ],
        "tagged_columns": [
            name
            for name, metadata in result.annotations["columns"].items()
            if metadata.get("tags")
        ],
    } == expected


def test_golden_shape_suggestions_for_nested_order_sample():
    sample = FIXTURES / "suggest" / "nested_order_sample.json"
    expected = _load_expected(FIXTURES / "suggest" / "nested_shape.expected.json")

    result = suggest_shape(sample)
    shape = result.shape

    actual = {
        "select_aliases": [item["alias"] for item in shape["select"]],
        "flatten_paths": [item["path"] for item in shape.get("flatten", [])],
        "explode_paths": [item["path"] for item in shape.get("explode", [])],
        "warning_fragments": [
            fragment
            for fragment in expected["warning_fragments"]
            if any(fragment in warning for warning in result.warnings)
        ],
        "decision_count": len(result.decisions_required),
    }
    assert actual == expected


def test_golden_contract_generation_for_silver_hash_diff():
    schema = FIXTURES / "suggest" / "orders_schema.json"
    expected = _load_expected(FIXTURES / "generate" / "orders_contract.expected.json")

    result = generate_contract_draft(
        schema,
        connector="files",
        source_path="/landing/orders",
        target_catalog="main",
        target_schema="silver",
        target_table="s_orders",
        layer="silver",
        owner="data-engineering",
    )
    contract = result.contract

    assert {
        "mode": contract["mode"],
        "merge_keys": contract["merge_keys"],
        "target": contract["target"],
        "source": {
            "connector": contract["source"]["connector"],
            "path": contract["source"]["path"],
            "schema": contract["source"]["read"]["schema"],
        },
        "quality_not_null": contract["quality_rules"]["not_null"],
        "validation_status": result.validation.status if result.validation else None,
    } == expected


def _load_expected(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
