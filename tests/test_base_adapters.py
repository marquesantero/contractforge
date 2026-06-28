from contractforge_core.adapters import append_only_adapter, full_feature_adapter
from contractforge_core.contracts import semantic_contract_from_mapping


def test_append_only_adapter_plans_append_contract() -> None:
    adapter = append_only_adapter()
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "scd0_append",
        }
    )

    result = adapter.plan(contract)

    assert result.status == "SUPPORTED"
    assert result.plan is not None


def test_append_only_adapter_rejects_scd2() -> None:
    adapter = append_only_adapter()
    contract = semantic_contract_from_mapping(
            {
                "source": {"type": "connector", "connector": "postgres"},
                "target": {"table": "orders_history"},
                "mode": "scd2_historical",
                "merge_keys": ["order_id"],
            }
        )

    result = adapter.plan(contract)

    assert result.status == "UNSUPPORTED"
    assert "SCD2_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_full_feature_adapter_renders_neutral_artifacts() -> None:
    adapter = full_feature_adapter()
    contract = semantic_contract_from_mapping(
            {
                "source": {"type": "connector", "connector": "postgres"},
                "target": {"table": "orders_history"},
                "mode": "scd2_historical",
                "merge_keys": ["order_id"],
            }
        )

    result = adapter.plan(contract)
    assert result.plan is not None

    artifacts = adapter.render_contract(contract)

    assert set(artifacts.artifacts) == {"review.md"}
    assert "Execution plan for full-feature-generic" in artifacts.artifacts["review.md"]
