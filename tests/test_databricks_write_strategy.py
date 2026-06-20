from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.capabilities import evaluate_databricks_capabilities
from contractforge_databricks.write_modes import choose_write_strategy


def _contract(mode: str):
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": mode,
            "merge_keys": ["order_id"],
        }
    )


def _databricks_contract(payload: dict):
    return semantic_contract_from_mapping(payload)


def test_strategy_prefers_databricks_merge_for_scd1() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    strategy = choose_write_strategy(_contract("scd1_upsert"), caps)

    assert strategy.kind == "native_databricks"
    assert strategy.engine == "databricks_sql_merge"


def test_strategy_keeps_contractforge_algorithm_for_hash_diff() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    strategy = choose_write_strategy(_contract("scd1_hash_diff"), caps)

    assert strategy.kind == "contractforge_algorithm"
    assert strategy.engine == "core_managed_hash_diff_delta"


def test_strategy_does_not_claim_lakeflow_for_scd2_when_unknown() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    strategy = choose_write_strategy(_contract("scd2_historical"), caps)

    assert strategy.kind == "contractforge_algorithm"
    assert strategy.engine == "core_managed_scd2_delta_merge"


def test_strategy_preserves_snapshot_soft_delete_algorithm() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    strategy = choose_write_strategy(_contract("snapshot_soft_delete"), caps)

    assert strategy.kind == "contractforge_algorithm"
    assert strategy.engine == "core_managed_snapshot_soft_delete_delta_merge"


def test_strategy_honors_explicit_lakeflow_preview_fallback() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = _databricks_contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "extensions": {
                "databricks": {"write_engine": {"requested": "lakeflow_auto_cdc", "fallback_policy": "preview_only"}}
            },
        }
    )

    strategy = choose_write_strategy(contract, caps)

    assert strategy.kind == "contractforge_algorithm"
    assert strategy.engine == "core_managed_scd2_delta_merge"
    assert "fallback_policy=preview_only" in strategy.warnings
    assert strategy.blockers


def test_strategy_honors_explicit_lakeflow_fail_policy() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = _databricks_contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "extensions": {
                "databricks": {"write_engine": {"requested": "lakeflow_auto_cdc", "fallback_policy": "fail"}}
            },
        }
    )

    strategy = choose_write_strategy(contract, caps)

    assert strategy.kind == "unsupported"
    assert strategy.engine == "lakeflow_auto_cdc"
