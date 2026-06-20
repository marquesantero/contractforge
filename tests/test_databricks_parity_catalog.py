import pytest

from contractforge_databricks.parity import (
    build_write_engine_parity_plan,
    get_write_engine_parity_scenario,
    list_write_engine_parity_scenarios,
    scenarios_for_engine,
    scenarios_for_mode,
)


def test_parity_catalog_covers_documented_scenarios() -> None:
    scenario_ids = set(list_write_engine_parity_scenarios())

    assert {
        "scd1_sql_merge_insert_update",
        "scd1_sql_merge_duplicate_keys",
        "scd1_sql_merge_null_keys",
        "scd2_auto_cdc_history_lifecycle",
        "scd2_auto_cdc_late_arriving",
        "scd2_auto_cdc_delete_semantics",
        "hash_diff_auto_cdc_non_equivalence",
        "snapshot_soft_delete_auto_cdc_difference",
    } <= scenario_ids


def test_parity_catalog_filters_by_engine_and_mode() -> None:
    sql_merge = scenarios_for_engine("databricks_sql_merge")
    scd2 = scenarios_for_mode("scd2_historical")

    assert {scenario.write_mode for scenario in sql_merge} == {"scd1_upsert"}
    assert {scenario.candidate_engine for scenario in scd2} == {"databricks_lakeflow_auto_cdc"}


def test_parity_plan_counts_expectations() -> None:
    plan = build_write_engine_parity_plan(engine="databricks_lakeflow_auto_cdc")

    assert plan["kind"] == "write_engine_parity_plan"
    assert plan["scenario_count"] == 5
    assert plan["expectation_counts"]["unsupported"] == 1
    assert plan["expectation_counts"]["intentional_difference"] == 1


def test_parity_catalog_rejects_unknown_scenario() -> None:
    with pytest.raises(ValueError, match="Write-engine parity scenario not found"):
        get_write_engine_parity_scenario("missing")

