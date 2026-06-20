import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.presets import apply_preset, get_preset, list_presets, preset_details, register_preset


def test_databricks_presets_cover_mature_contractforge_scenarios() -> None:
    names = set(list_presets())

    assert {
        "bronze_autoloader_append",
        "bronze_partition_overwrite",
        "bronze_table_append",
        "silver_scd1_upsert",
        "silver_scd1_partition_upsert",
        "silver_replace_partitions",
        "silver_incremental_watermark_upsert",
        "silver_hash_diff_append",
        "silver_quarantine_ingestion",
        "silver_snapshot_soft_delete",
            "silver_historical",
        "gold_full_refresh",
        "gold_partition_refresh",
        "gold_replace_partitions",
            "gold_current_state_serving",
        "gold_snapshot_serving",
        "quality_strict",
        "quality_quarantine",
        "delta_cdf_enabled",
        "delta_optimized_writes",
        "delta_liquid_clustering",
        "governance_uc_basic",
        "runtime_databricks_serverless",
        "runtime_spark_delta_local",
        "write_engine_native_auto_preview",
        "write_engine_databricks_sql_merge_preview",
        "write_engine_lakeflow_auto_cdc_preview",
    } <= names
    assert len(names) >= 29


def test_get_preset_returns_defensive_copy() -> None:
    preset = get_preset("delta_optimized_writes")
    preset["extensions"]["databricks"]["delta_properties"]["delta.autoOptimize.optimizeWrite"] = "false"

    assert (
        get_preset("delta_optimized_writes")["extensions"]["databricks"]["delta_properties"][
            "delta.autoOptimize.optimizeWrite"
        ]
        == "true"
    )


def test_register_preset_adds_custom_databricks_preset() -> None:
    register_preset(
        "custom_quality_warn",
        {"on_quality_fail": "warn", "_preset": {"description": "Warn on quality failures."}},
        override=True,
    )

    assert "custom_quality_warn" in list_presets()
    assert preset_details("custom_quality_warn")["category"] == "custom"
    assert apply_preset({"preset": "custom_quality_warn", "target": {"table": "orders"}})["on_quality_fail"] == "warn"


def test_register_preset_rejects_duplicate_without_override() -> None:
    register_preset("custom_duplicate_guard", {"schema_policy": "strict"}, override=True)

    with pytest.raises(ValueError, match="Preset already registered"):
        register_preset("custom_duplicate_guard", {"schema_policy": "permissive"})


def test_apply_preset_merges_defaults_and_explicit_values() -> None:
    contract = apply_preset(
        {
            "preset": ["silver_incremental_watermark_upsert", "quality_quarantine"],
            "target": {"table": "main.curated.orders"},
            "merge_keys": ["order_id"],
            "watermark_columns": ["updated_at"],
            "schema_policy": "strict",
        }
    )

    assert contract["mode"] == "upsert"
    assert contract["on_quality_fail"] == "quarantine"
    assert contract["schema_policy"] == "strict"
    assert contract["applied_presets"] == ["silver_incremental_watermark_upsert", "quality_quarantine"]


def test_apply_preset_result_is_accepted_by_core_contract_normalization() -> None:
    contract = apply_preset(
        {
            "preset": "quality_quarantine",
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
        }
    )

    semantic = semantic_contract_from_mapping(contract)

    assert semantic.operations is not None
    assert semantic.operations.metadata is not None
    assert semantic.operations.metadata["applied_presets"] == ["quality_quarantine"]


def test_apply_preset_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="silver_historical:merge_keys"):
        apply_preset({"preset": "silver_historical", "target": {"table": "main.curated.customers"}})


def test_preset_details_are_metadata_only() -> None:
    details = preset_details("silver_historical")

    assert details["category"] == "silver"
    assert details["kind"] == "ingestion"
    assert "mode" in details["sets"]


def test_hash_diff_preset_does_not_assume_legacy_ingestion_date_column() -> None:
    preset = get_preset("silver_hash_diff_append")

    assert "ingestion_date" not in preset["hash_exclude_columns"]
    assert {"ingestion_ts_utc", "__run_id"} <= set(preset["hash_exclude_columns"])
    assert "source_system" not in preset["hash_exclude_columns"]


def test_partition_and_write_engine_presets_expand_canonical_databricks_fields() -> None:
    replace = apply_preset(
        {
            "preset": "silver_replace_partitions",
            "target": {"table": "main.curated.orders"},
            "extensions": {"databricks": {"merge_partition_column": "dt"}},
        }
    )

    replace_extensions = replace["extensions"]["databricks"]
    assert replace_extensions["merge_strategy"] == "replace_partitions"
    assert replace_extensions["merge_partition_column"] == "dt"
    assert replace_extensions["replace_partitions_source_complete"] is True

    write_engine = apply_preset(
        {
            "preset": "write_engine_lakeflow_auto_cdc_preview",
            "target": {"table": "main.curated.orders"},
            "merge_keys": ["order_id"],
        }
    )

    write_engine_request = write_engine["extensions"]["databricks"]["write_engine"]
    assert write_engine_request["requested"] == "lakeflow_auto_cdc"
    assert write_engine_request["fallback_policy"] == "preview_only"


def test_runtime_local_and_delta_cdf_presets_are_databricks_specific_modifiers() -> None:
    runtime = get_preset("runtime_spark_delta_local")
    cdf = get_preset("delta_cdf_enabled")

    runtime_extensions = runtime["extensions"]["databricks"]
    assert runtime_extensions["lock_enabled"] is False
    assert runtime_extensions["cache_source"] is False
    assert "use_cache" not in runtime
    assert cdf["extensions"]["databricks"]["delta_properties"]["delta.enableChangeDataFeed"] == "true"
