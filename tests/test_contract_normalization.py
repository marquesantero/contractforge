import pytest

from contractforge_core.contracts import semantic_contract_from_mapping


def test_contract_mapping_normalizes_to_semantic_contract() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "connector",
                "connector": "postgres",
                "table": "public.orders",
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "layer": "bronze",
            "mode": "scd1_upsert",
            "schema_policy": "additive_only",
            "merge_keys": ["order_id"],
            "owner": "data-eng",
            "access": {
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
                "column_masks": {
                    "email": {
                        "function": "main.security.mask_email",
                        "using_columns": ["email"],
                    }
                }
            },
        }
    )

    assert contract.source.kind == "connector:postgres"
    assert contract.target.name == "orders"
    assert contract.target.namespace == "main.bronze"
    assert contract.write.mode == "scd1_upsert"
    assert contract.write.schema_policy == "additive_only"
    assert contract.write.merge_keys == ("order_id",)
    assert contract.governance is not None
    assert contract.governance.column_masks == ("email",)
    assert contract.governance.access is not None
    assert contract.governance.access["grants"][0]["principal"] == "analysts"


def test_contract_mapping_preserves_hash_exclude_columns() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders_hash"},
            "mode": "scd1_hash_diff",
            "hash_keys": ["order_id"],
            "hash_exclude_columns": ["ingestion_ts_utc", "__run_id"],
        }
    )

    assert contract.write.hash_exclude_columns == ("ingestion_ts_utc", "__run_id")


def test_contract_mapping_preserves_hash_strategy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders_hash"},
            "mode": "scd1_hash_diff",
            "merge_keys": ["order_id"],
            "hash_strategy": "all_columns_except",
            "hash_exclude_columns": ["updated_at"],
        }
    )

    assert contract.write.hash_strategy == "all_columns_except"
    assert contract.write.hash_keys == ()


def test_contract_mapping_preserves_on_quality_fail_policy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "quality_rules": {"not_null": ["order_id"]},
            "on_quality_fail": "warn",
        }
    )

    assert contract.operations is not None
    assert contract.operations.metadata is not None
    assert contract.operations.metadata["on_quality_fail"] == "warn"


def test_contract_mapping_preserves_applied_presets_metadata() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "applied_presets": ["silver_scd1_upsert", "quality_quarantine"],
        }
    )

    assert contract.operations is not None
    assert contract.operations.metadata is not None
    assert contract.operations.metadata["applied_presets"] == ["silver_scd1_upsert", "quality_quarantine"]


def test_contract_mapping_preserves_source_system_metadata_from_source() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders", "system": "crm"},
            "target": {"table": "orders"},
        }
    )

    assert contract.source.raw is not None
    assert contract.source.raw["system"] == "crm"


def test_source_system_is_not_a_core_root_alias() -> None:
    with pytest.raises(ValueError, match="source_system"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"table": "orders"},
                "source_system": "crm",
            }
        )


def test_notebook_name_is_not_a_core_contract_alias() -> None:
    with pytest.raises(ValueError, match="notebook_name"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"table": "orders"},
                "notebook_name": "jobs/orders_ingest",
            }
        )


def test_ctrl_schema_is_not_a_core_contract_alias() -> None:
    with pytest.raises(ValueError, match="ctrl_schema"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"table": "orders"},
                "ctrl_schema": "ops_prod",
            }
        )


def test_contract_mapping_resolves_shape_schema_ref_from_registry() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "schemas": {"order_payload": "STRUCT<id: STRING, total: DOUBLE>"},
            "shape": {"parse_json": [{"column": "payload", "schema_ref": "order_payload"}]},
        }
    )

    assert contract.shape is not None
    assert contract.shape.raw["parse_json"][0]["schema_ref"] == "order_payload"
    assert contract.shape.raw["parse_json"][0]["schema"] == "STRUCT<id: STRING, total: DOUBLE>"
    assert contract.operations is not None
    assert contract.operations.metadata is not None
    assert contract.operations.metadata["schemas"] == {"order_payload": "STRUCT<id: STRING, total: DOUBLE>"}


def test_contract_mapping_rejects_missing_shape_schema_ref() -> None:
    with pytest.raises(ValueError, match="schema_ref='missing' does not exist"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"table": "orders"},
                "schemas": {"order_payload": "STRUCT<id: STRING>"},
                "shape": {"parse_json": [{"column": "payload", "schema_ref": "missing"}]},
            }
        )


def test_contract_mapping_rejects_shape_schema_and_schema_ref_together() -> None:
    with pytest.raises(ValueError, match="schema or schema_ref, not both"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"table": "orders"},
                "schemas": {"order_payload": "STRUCT<id: STRING>"},
                "shape": {
                    "parse_json": [
                        {
                            "column": "payload",
                            "schema": "STRUCT<other: STRING>",
                            "schema_ref": "order_payload",
                        }
                    ]
                },
            }
        )


def test_contract_mapping_preserves_scd2_effective_from_column() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_effective_from_column": "valid_from_source",
        }
    )

    assert contract.write.scd2_effective_from_column == "valid_from_source"


def test_contract_mapping_preserves_scd2_late_arriving_policy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders_history"},
            "mode": "scd2_historical",
            "merge_keys": ["order_id"],
            "scd2_sequence_by": "event_ts",
            "scd2_late_arriving_policy": "ignore",
        }
    )

    assert contract.write.scd2_late_arriving_policy == "ignore"


def test_contract_mapping_accepts_public_write_mode_alias() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "mode": "append",
        }
    )

    assert contract.write.mode == "scd0_append"


def test_contract_mapping_rejects_unknown_write_mode() -> None:
    with pytest.raises(ValueError, match="contract.mode"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "connector", "connector": "postgres"},
                "target": {"table": "orders"},
                "mode": "unknown_write_mode",
            }
        )


def test_quality_rules_normalize_to_semantic_quality_intents() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"table": "orders"},
            "quality_rules": {
                "required_columns": ["id", "status"],
                "not_null": ["id"],
                "unique_key": ["id"],
                "accepted_values": {"status": ["open", "closed"]},
                "min_rows": 1,
                "max_null_ratio": {"status": 0.5},
                "expressions": [{"name": "positive_amount", "expression": "amount > 0", "severity": "warn"}],
            },
        }
    )

    assert [intent.rule for intent in contract.quality] == [
        "required_columns",
        "not_null",
        "unique_key",
        "accepted_values",
        "row_count_minimum",
        "max_null_ratio",
        "expression",
    ]
    assert contract.quality[0].severity == "abort"
    assert contract.quality[-1].name == "positive_amount"
    assert contract.quality[-1].severity == "warn"


def test_quality_rules_custom_is_preserved_as_opaque_extension() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "quality_rules": {
                "custom": {
                    "business_threshold": {
                        "type": "threshold_check",
                        "severity": "warn",
                        "threshold": 5,
                    }
                }
            },
        }
    )

    assert contract.quality == ()
    assert contract.extensions == {
        "quality": {
            "custom": {
                "business_threshold": {
                        "type": "threshold_check",
                        "severity": "warn",
                        "threshold": 5,
                    }
            }
        }
    }


def test_shape_and_transform_normalize_to_semantic_intents() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "shape": {"flatten": {"enabled": True}},
            "transform": {
                "cast": {"amount": "double"},
                "standardize": {"email": {"trim": True, "lower": True}},
                "derive": {"order_date": "to_date(updated_at)"},
                "deduplicate": {
                    "keys": ["order_id"],
                    "order_by": [{"column": "updated_at", "direction": "desc", "nulls": "last"}],
                },
            },
        }
    )

    assert contract.shape is not None
    assert contract.shape.raw["flatten"]["enabled"] is True
    assert contract.transform is not None
    assert contract.transform.raw["cast"]["amount"] == "double"
    assert contract.transform.raw["deduplicate"]["order_by"][0]["column"] == "updated_at"


def test_transform_deduplicate_is_canonical_contract_shape() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
            "transform": {"deduplicate": {"keys": ["order_id"], "order_by": "updated_at DESC NULLS LAST"}},
        }
    )

    assert contract.transform is not None
    assert contract.transform.raw["deduplicate"] == {
        "keys": ["order_id"],
        "order_by": "updated_at DESC NULLS LAST",
    }


def test_top_level_dedup_order_expr_is_not_a_core_alias() -> None:
    with pytest.raises(ValueError, match="dedup_order_expr"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"table": "orders"},
                "mode": "scd1_upsert",
                "merge_keys": ["order_id"],
                "dedup_order_expr": "updated_at DESC NULLS LAST",
            }
        )


def test_composite_keys_normalize_to_transform_intent() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "transform": {"composite_keys": {"order_line_key": ["order_id", "line_id"]}},
        }
    )

    assert contract.transform is not None
    assert contract.transform.raw["composite_keys"] == {"order_line_key": ["order_id", "line_id"]}


def test_source_intent_overrides_runtime_source_type_without_losing_raw_source() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "s3",
                "intent": "file_stream",
                "path": "s3://landing/orders",
                "format": "json",
                "discovery": {"strategy": "file_listing", "tracking": "modification_time"},
            },
            "target": {"catalog": "primary", "catalog_type": "metastore", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    assert contract.source.kind == "file_stream"
    assert contract.source.raw["type"] == "s3"
    assert contract.source.raw["discovery"]["tracking"] == "modification_time"
    assert contract.target.catalog_type == "metastore"


def test_execution_intent_preserves_freshness_preference_and_fallback() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "s3", "path": "s3://landing/orders", "format": "json"},
            "target": {"catalog": "primary", "catalog_type": "metastore", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
            "execution": {
                "freshness": "near_real_time",
                "latency_target": "5 minutes",
                "preferred": "continuous",
                "fallback": "batch_incremental",
            },
        }
    )

    assert contract.operations is not None
    assert contract.operations.metadata["execution"]["freshness"] == "near_real_time"
    assert contract.operations.metadata["execution"]["latency_target"] == "5 minutes"
    assert contract.operations.metadata["execution"]["fallback"] == "batch_incremental"


def test_execution_available_now_preference_sets_semantic_flag() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "incremental_files", "path": "s3://landing/orders", "format": "json"},
            "target": {"schema": "bronze", "table": "orders"},
            "execution": {"preferred": "available_now", "fallback": "scheduled"},
        }
    )

    assert contract.operations is not None
    assert contract.operations.available_now_streaming is True


def test_top_level_custom_keys_is_not_a_core_alias() -> None:
    with pytest.raises(ValueError, match="custom_keys"):
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"table": "orders"},
                "custom_keys": {"order_line_key": ["order_id", "line_id"]},
            }
        )


def test_transform_nested_shape_normalizes_to_shape_intent() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "transform": {
                "shape": {"flatten": True},
                "derive": {"loaded_at": "current_timestamp()"},
            },
        }
    )

    assert contract.shape is not None
    assert contract.shape.raw["flatten"] is True
    assert contract.transform is not None
    assert contract.transform.raw["derive"]["loaded_at"] == "current_timestamp()"


def test_naming_normalizes_to_semantic_intent() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "domain": "sales",
            "naming": {
                "logical_name": "orders_current",
                "contract_basename": "orders_contract",
                "bundle_name": "orders-bundle",
            },
        }
    )

    assert contract.target.domain == "sales"
    assert contract.naming is not None
    assert contract.naming.raw["logical_name"] == "orders_current"
    assert contract.naming.raw["bundle_name"] == "orders-bundle"


def test_semantic_contract_preserves_portable_execution_metadata() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "mode": "scd0_append",
            "filter_expression": "updated_at >= '2026-01-01'",
            "watermark_columns": ["updated_at"],
            "idempotency_key": "orders:2026-01-01",
            "idempotency_policy": "skip_if_success",
            "retry_attempts": 3,
            "execution": {
                "window": {
                    "column": "updated_at",
                    "start": "2026-01-01T00:00:00Z",
                    "end": "2026-01-02T00:00:00Z",
                    "every": "1 day",
                }
            },
        }
    )

    assert contract.operations is not None
    assert contract.operations.metadata["filter_expression"] == "updated_at >= '2026-01-01'"
    assert contract.operations.metadata["watermark_columns"] == ["updated_at"]
    assert contract.operations.metadata["idempotency_policy"] == "skip_if_success"
    assert contract.operations.metadata["retry_attempts"] == 3
    assert contract.operations.metadata["execution"]["window"]["column"] == "updated_at"


def test_semantic_contract_preserves_opaque_extensions() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "extensions": {"adapter": {"feature": True}},
        }
    )

    assert contract.extensions == {"adapter": {"feature": True}}
