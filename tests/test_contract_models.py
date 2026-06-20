from __future__ import annotations

import pytest

from contractforge_core.contracts import (
    contract_model_schemas,
    yaml_schema,
    validate_environment_contract,
    validate_access_contract,
    validate_annotations_contract,
    validate_contract,
    validate_operations_contract,
    validate_quality_rules_contract,
    validate_shape_contract,
    validate_source_contract,
    validate_transform_contract,
)


def test_source_contract_rejects_unknown_connector_field() -> None:
    with pytest.raises(ValueError, match="source.typo"):
        validate_source_contract({"type": "connector", "connector": "postgres", "typo": True})


def test_source_contract_rejects_invalid_port() -> None:
    with pytest.raises(ValueError, match="source.port"):
        validate_source_contract({"type": "connector", "connector": "sftp", "port": 70000})


def test_source_contract_allows_connector_extension_maps() -> None:
    source = validate_source_contract(
        {
            "type": "connector",
            "connector": "postgres",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "options": {"customProviderOption": "x"},
            "auth": {"type": "basic", "username": "u"},
            "limits": {"fetchsize": 1000},
        }
    )

    assert source["options"]["customProviderOption"] == "x"
    assert source["auth"]["username"] == "u"
    assert source["limits"]["fetchsize"] == 1000


def test_validate_contract_rejects_legacy_top_level_target_fields() -> None:
    with pytest.raises(ValueError, match="target_table"):
        validate_contract(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target_table": "orders",
                "catalog": "main",
                "target_schema": "silver",
            }
        )

    with pytest.raises(ValueError, match="ctrl_schema"):
        validate_contract(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "ctrl_schema": "ops",
            }
        )


def test_validate_contract_rejects_legacy_top_level_databricks_fields() -> None:
    with pytest.raises(ValueError, match="delta_properties"):
        validate_contract(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "delta_properties": {"delta.enableChangeDataFeed": "true"},
            }
        )

    with pytest.raises(ValueError, match="cluster_columns"):
        validate_contract(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "cluster_columns": ["brand"],
            }
        )


def test_validate_contract_rejects_legacy_top_level_source_system() -> None:
    with pytest.raises(ValueError, match="source_system"):
        validate_contract(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "silver", "table": "orders"},
                "source_system": "supabase",
            }
        )


def test_contract_layer_name_is_portable_but_stable() -> None:
    contract = validate_contract(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "curated", "table": "orders"},
            "layer": "raw_ops-1",
        }
    )

    assert contract["layer"] == "raw_ops-1"

    with pytest.raises(ValueError, match="layer"):
        validate_contract(
            {
                "source": {"type": "table", "table": "main.raw.orders"},
                "target": {"catalog": "main", "schema": "curated", "table": "orders"},
                "layer": "1 raw",
            }
        )


def test_source_contract_rejects_top_level_schema_alias() -> None:
    with pytest.raises(ValueError, match="source.schema"):
        validate_source_contract(
            {
                "type": "connector",
                "connector": "http_file",
                "url": "https://example.com/orders.csv",
                "format": "csv",
                "schema": "id STRING, amount DOUBLE",
            }
        )


def test_source_contract_preserves_canonical_read_schema() -> None:
    source = validate_source_contract(
        {
            "type": "connector",
            "connector": "http_file",
            "url": "https://example.com/orders.csv",
            "format": "csv",
            "read": {"schema": "id STRING, amount DOUBLE"},
        }
    )

    assert source["read"]["schema"] == "id STRING, amount DOUBLE"


def test_source_contract_rejects_options_schema_conflict() -> None:
    with pytest.raises(ValueError, match="source.options.schema conflicts with source.read.schema"):
        validate_source_contract(
            {
                "type": "connector",
                "connector": "http_file",
                "url": "https://example.com/orders.csv",
                "format": "csv",
                "read": {"schema": "id STRING"},
                "options": {"schema": "id BIGINT"},
            }
        )


def test_source_contract_rejects_jdbc_table_and_query_together() -> None:
    with pytest.raises(ValueError, match="JDBC connector accepts source.table or source.query"):
        validate_source_contract(
            {
                "type": "connector",
                "connector": "postgres",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "query": "select * from public.orders",
            }
        )


def test_generic_source_rejects_platform_specific_legacy_fields() -> None:
    with pytest.raises(ValueError, match="source.unknown"):
        validate_source_contract(
            {
                "type": "incremental_files",
                "path": "/mnt/raw/orders",
                "unknown": True,
            }
        )


def test_annotations_contract_rejects_unknown_nested_field() -> None:
    with pytest.raises(ValueError, match="annotations.columns.email.unknown"):
        validate_annotations_contract({"columns": {"email": {"unknown": True}}})


def test_annotations_contract_rejects_self_wrapper() -> None:
    with pytest.raises(ValueError, match="annotations.yaml must declare fields at the document root"):
        validate_annotations_contract(
            {
                "annotations": {
                    "table": {"description": "Orders"},
                    "columns": {"order_id": {"description": "Order id"}},
                }
            }
        )


def test_annotations_contract_rejects_invalid_pii_type() -> None:
    with pytest.raises(ValueError, match="annotations.columns.email.pii.type"):
        validate_annotations_contract({"columns": {"email": {"pii": {"type": "mail"}}}})


def test_annotations_contract_rejects_empty_governance_values() -> None:
    with pytest.raises(ValueError, match="aliases"):
        validate_annotations_contract({"table": {"aliases": ["orders", ""]}})

    with pytest.raises(ValueError, match="tags"):
        validate_annotations_contract({"table": {"tags": {"contains_pii": ""}}})

    with pytest.raises(ValueError, match="deprecated"):
        validate_annotations_contract({"table": {"deprecated": {"since": "", "replacement": "new_table"}}})


def test_operations_contract_rejects_invalid_frequency() -> None:
    with pytest.raises(ValueError, match="operations.expected_frequency"):
        validate_operations_contract({"expected_frequency": "sometimes"})


def test_operations_contract_rejects_self_wrapper() -> None:
    with pytest.raises(ValueError, match="operations.yaml must declare fields at the document root"):
        validate_operations_contract(
            {
                "operations": {
                    "criticality": "high",
                    "expected_frequency": "daily",
                    "owners": ["data-platform"],
                }
            }
        )


def test_contract_validation_errors_are_concise_and_actionable() -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_source_contract({"type": "connector", "connector": "postgres", "typo": True})

    message = str(exc_info.value)
    assert message == "source.typo: unexpected field 'typo'; remove it or move it to the canonical location"
    assert "ConnectorSourceContract" not in message
    assert "Extra inputs are not permitted" not in message


def test_environment_contract_accepts_execution_context_only() -> None:
    environment = validate_environment_contract(
        {
            "environment": {
                "name": "prod",
                "adapter": "databricks",
                "runtime": {"kind": "serverless"},
                "deployment": {"artifact": "bundle"},
                "evidence": {"schema": "contractforge_ops"},
                "secrets": {"strategy": "secret_scope"},
                "defaults": {"timezone": "UTC"},
                "capabilities": {"require": ["merge", "evidence_store"]},
                "parameters": {"databricks": {"job.max_concurrent_runs": 1}},
            }
        }
    )

    assert environment["name"] == "prod"
    assert environment["adapter"] == "databricks"
    assert environment["parameters"]["databricks"]["job.max_concurrent_runs"] == 1


def test_environment_contract_defaults_name_to_dev() -> None:
    environment = validate_environment_contract({"adapter": "aws"})

    assert environment["name"] == "dev"
    assert environment["adapter"] == "aws"


def test_environment_contract_rejects_semantic_fields() -> None:
    with pytest.raises(ValueError, match="semantic contract fields"):
        validate_environment_contract(
            {
                "name": "prod",
                "adapter": "databricks",
                "source": {"type": "table", "table": "main.raw.orders"},
            }
        )


def test_access_contract_accepts_column_masks_mapping() -> None:
    access = validate_access_contract(
        {
            "column_masks": {
                "email": {
                    "function": "main.security.mask_email",
                    "using_columns": ["email"],
                }
            }
        }
    )

    assert access["column_masks"][0]["column"] == "email"


def test_access_contract_rejects_unknown_grant_field() -> None:
    with pytest.raises(ValueError, match="access.grants.0.unknown"):
        validate_access_contract({"grants": [{"principal": "readers", "privileges": "SELECT", "unknown": True}]})


def test_access_contract_rejects_self_wrapper() -> None:
    with pytest.raises(ValueError, match="access.yaml must declare fields at the document root"):
        validate_access_contract(
            {"access": {"grants": [{"principal": "readers", "privileges": "SELECT"}]}}
        )


def test_access_contract_rejects_empty_governance_values() -> None:
    with pytest.raises(ValueError, match="principal"):
        validate_access_contract({"grants": [{"principal": "", "privileges": "SELECT"}]})

    with pytest.raises(ValueError, match="privileges"):
        validate_access_contract({"grants": [{"principal": "readers", "privileges": ["SELECT", ""]}]})

    with pytest.raises(ValueError, match="row_filters"):
        validate_access_contract({"row_filters": [{"name": "region_filter", "function": "", "columns": ["region"]}]})

    with pytest.raises(ValueError, match="using_columns"):
        validate_access_contract(
            {"column_masks": {"email": {"function": "main.security.mask_email", "using_columns": ["email", ""]}}}
        )


def test_shape_contract_rejects_unknown_parse_json_field() -> None:
    with pytest.raises(ValueError, match="shape.parse_json.0.unknown"):
        validate_shape_contract(
            {
                "parse_json": [
                    {
                        "column": "payload",
                        "schema": "STRUCT<id: STRING>",
                        "unknown": True,
                    }
                ]
            }
        )


def test_shape_contract_preserves_schema_alias() -> None:
    shape = validate_shape_contract({"parse_json": [{"column": "payload", "schema": "STRUCT<id: STRING>"}]})

    assert shape["parse_json"][0]["schema"] == "STRUCT<id: STRING>"


def test_shape_contract_preserves_semantic_guardrails() -> None:
    with pytest.raises(ValueError, match="requires schema or schema_ref"):
        validate_shape_contract({"parse_json": [{"column": "payload"}]})

    with pytest.raises(ValueError, match="schema or schema_ref, not both"):
        validate_shape_contract(
            {"parse_json": [{"column": "payload", "schema": "STRUCT<id: STRING>", "schema_ref": "payload"}]}
        )

    with pytest.raises(ValueError, match="duplicate output column"):
        validate_shape_contract(
            {
                "parse_json": [
                    {"column": "payload_a", "schema": "STRUCT<id: STRING>", "alias": "payload"},
                    {"column": "payload_b", "schema": "STRUCT<id: STRING>", "alias": "payload"},
                ]
            }
        )

    with pytest.raises(ValueError, match="at least two arrays"):
        validate_shape_contract({"zip_arrays": [{"alias": "hour", "columns": {"time": "time"}}]})

    with pytest.raises(ValueError, match="duplicate output field"):
        validate_shape_contract(
            {"zip_arrays": [{"alias": "hour", "columns": {"time": "value", "temperature": "value"}}]}
        )

    # When alias is omitted the column key is used as the default alias, even with expression.
    shape = validate_shape_contract({"columns": {"event_id": {"expression": "payload.id"}}})
    assert shape["columns"]["event_id"] == {"expression": "payload.id"}


def test_shape_contract_defaults_alias_to_key_when_expression_set() -> None:
    shape = validate_shape_contract(
        {
            "columns": {
                "price_band": {"expression": "CASE WHEN price < 50 THEN 'budget' ELSE 'premium' END"},
                "event_date": {"expression": "TO_DATE(event_ts)", "alias": "event_date"},
            }
        }
    )
    assert shape["columns"]["price_band"]["expression"].startswith("CASE")
    assert shape["columns"]["event_date"]["alias"] == "event_date"


def test_shape_contract_accepts_parse_json_cast_input_string() -> None:
    shape = validate_shape_contract(
        {
            "parse_json": [
                {
                    "column": "value",
                    "alias": "payload",
                    "schema": "STRUCT<id: STRING>",
                    "cast_input": "STRING",
                }
            ]
        }
    )

    assert shape["parse_json"][0]["cast_input"] == "STRING"
    # Lower-case normalises to upper.
    shape = validate_shape_contract(
        {"parse_json": [{"column": "value", "schema": "STRUCT<id: STRING>", "cast_input": "string"}]}
    )
    assert shape["parse_json"][0]["cast_input"] == "STRING"


def test_shape_contract_rejects_unsupported_parse_json_cast_input() -> None:
    with pytest.raises(ValueError, match="cast_input"):
        validate_shape_contract(
            {"parse_json": [{"column": "value", "schema": "STRUCT<id: STRING>", "cast_input": "BINARY"}]}
        )


def test_shape_contract_rejects_duplicate_aliases_with_expression() -> None:
    # Duplicate detection still runs after defaulting alias to the key.
    with pytest.raises(ValueError, match="duplicate alias"):
        validate_shape_contract(
            {
                "columns": {
                    "event_id": {"expression": "payload.id"},
                    "other": {"alias": "event_id", "expression": "payload.other_id"},
                }
            }
        )


def test_transform_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="transform.unknown"):
        validate_transform_contract({"unknown": True})


def test_transform_contract_rejects_non_list_arrays() -> None:
    with pytest.raises(ValueError, match="transform.shape.arrays"):
        validate_transform_contract({"shape": {"arrays": {"path": "items"}}})


def test_transform_contract_accepts_cast_derive_standardize_and_structured_deduplicate() -> None:
    transform = validate_transform_contract(
        {
            "cast": {"amount": "double"},
            "derive": {"order_date": "to_date(updated_at)"},
            "standardize": {"email": {"trim": True, "lower": True}},
            "deduplicate": {
                "keys": ["id"],
                "order_by": [{"column": "updated_at", "direction": "desc", "nulls": "last"}],
            },
        }
    )

    assert transform["cast"]["amount"] == "double"
    assert transform["derive"]["order_date"] == "to_date(updated_at)"
    assert transform["standardize"]["email"]["lower"] is True
    assert transform["deduplicate"]["order_by"][0]["column"] == "updated_at"


def test_quality_contract_rejects_empty_rule_identifiers() -> None:
    with pytest.raises(ValueError, match="quality_rules.required_columns"):
        validate_quality_rules_contract({"required_columns": ["id", ""]})

    with pytest.raises(ValueError, match="quality_rules.accepted_values"):
        validate_quality_rules_contract({"accepted_values": {"": ["active"]}})

    with pytest.raises(ValueError, match="quality_rules.custom"):
        validate_quality_rules_contract({"custom": {"": {"type": "business_check"}}})


def test_contract_model_schemas_are_generated_without_runtime_sdks() -> None:
    schemas = contract_model_schemas()

    assert "source.connector" in schemas
    assert "source.generic" in schemas
    assert "annotations" in schemas
    assert "environment" in schemas
    assert "naming" in schemas
    assert "transform" in schemas
    assert schemas["source.connector"]["properties"]["connector"]["type"] == "string"
    assert schemas["transform"]["properties"]["shape"]["anyOf"]


def test_yaml_schema_exposes_stable_root_contract_entry_point() -> None:
    schema = yaml_schema()
    props = schema["properties"]

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "https://github.com/marquesantero/contractforge-core/schema.json"
    assert "source" in schema["required"]
    assert "target" in schema["required"]
    assert "table" in props["target"]["required"]
    assert "source" in props
    assert "annotations" in props
    assert "operations" in props
    assert "access" in props
    assert "environment" not in props
    assert "schemas" in props
    assert "shape" in props
    assert "transform" in props
    assert props["mode"]["anyOf"][0]["enum"]
    assert props["mode"]["anyOf"][1]["pattern"] == r"^custom:[A-Za-z0-9_.-]+$"
