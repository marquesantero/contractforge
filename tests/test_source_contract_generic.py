import pytest

from contractforge_core.contracts import validate_source_contract, validate_source_semantics


def test_incremental_files_source_contract_is_accepted() -> None:
    source = validate_source_contract(
        {
            "type": "incremental_files",
            "path": "s3://bucket/landing/events",
            "format": "json",
            "progress_location": "s3://bucket/_progress/events",
            "schema_tracking_location": "s3://bucket/_schemas/events",
            "options": {"infer_column_types": True},
        }
    )

    assert source["type"] == "incremental_files"
    assert source["path"] == "s3://bucket/landing/events"
    assert source["progress_location"] == "s3://bucket/_progress/events"
    assert source["schema_tracking_location"] == "s3://bucket/_schemas/events"


def test_source_contract_accepts_portable_intent_discovery_and_state() -> None:
    source = validate_source_contract(
        {
            "type": "s3",
            "intent": "file_stream",
            "path": "s3://landing/orders",
            "format": "json",
            "discovery": {"strategy": "file_listing", "tracking": "modification_time"},
            "state": {
                "storage": "external",
                "location": {"type": "object_storage", "path": "s3://state/orders"},
            },
        }
    )

    assert source["intent"] == "file_stream"
    assert source["discovery"]["strategy"] == "file_listing"
    assert source["state"]["location"]["type"] == "object_storage"


def test_source_external_state_requires_location() -> None:
    with pytest.raises(ValueError, match="source.state.storage='external'"):
        validate_source_contract(
            {
                "type": "s3",
                "intent": "file_stream",
                "path": "s3://landing/orders",
                "format": "json",
                "state": {"storage": "external"},
            }
        )


def test_incremental_files_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="source.format='xlsx' is not supported"):
        validate_source_semantics(
            {
                "type": "incremental_files",
                "path": "s3://bucket/landing/events",
                "format": "xlsx",
            }
        )


def test_native_passthrough_source_contract_is_accepted() -> None:
    source = validate_source_contract(
        {
            "type": "native_passthrough",
            "system": "salesforce",
            "object": "Account",
            "watermark": {"column": "SystemModstamp"},
            "auth": {"type": "oauth2_jwt", "secret_scope": "sf_prod"},
        }
    )

    assert source["system"] == "salesforce"
    assert source["object"] == "Account"


def test_custom_transform_source_contract_requires_named_inputs() -> None:
    source = validate_source_contract(
        {
            "type": "custom_transform",
            "intent": "custom_treatment",
            "inputs": [
                {"alias": "orders", "table_ref": {"layer": "silver", "table": "orders"}},
                {"alias": "customers", "table": "main.silver.customers"},
            ],
        }
    )

    assert source["type"] == "custom_transform"
    assert source["inputs"][0]["alias"] == "orders"
    validate_source_semantics(source)

    with pytest.raises(ValueError, match="source.inputs is required"):
        validate_source_contract({"type": "custom_transform"})

    with pytest.raises(ValueError, match="duplicated"):
        validate_source_contract(
            {
                "type": "custom_transform",
                "inputs": [
                    {"alias": "orders", "table": "main.silver.orders"},
                    {"alias": "orders", "table": "main.silver.orders_changes"},
                ],
            }
        )


def test_connection_source_contract_requires_external_path() -> None:
    source = validate_source_contract(
        {
            "type": "connection",
            "connection_path": "../connections/supabase.yaml",
            "table": "public.products",
        }
    )

    assert source["type"] == "connection"
    assert source["connection_path"] == "../connections/supabase.yaml"

    with pytest.raises(ValueError, match="source.connection_path"):
        validate_source_semantics({"type": "connection"})


def test_source_contract_preserves_connector_validation_rules() -> None:
    with pytest.raises(ValueError, match="JDBC partitioning requires"):
        validate_source_semantics(
            {
                "type": "connector",
                "connector": "postgres",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "read": {"partition_column": "id", "num_partitions": 8},
            }
        )

    with pytest.raises(ValueError, match="pagination.next_cursor_path"):
        validate_source_semantics(
            {
                "type": "rest_api",
                "url": "https://api.example.test/orders",
                "pagination": {"type": "cursor"},
            }
        )

    with pytest.raises(ValueError, match="source.system"):
        validate_source_semantics({"type": "native_passthrough", "object": "Account"})

    with pytest.raises(ValueError, match="auth.type='digest'"):
        validate_source_semantics(
            {
                "type": "rest_api",
                "url": "https://api.example.test/orders",
                "auth": {"type": "digest"},
            }
        )

    with pytest.raises(ValueError, match="raw_column must be a simple column name"):
        validate_source_semantics(
            {
                "type": "rest_api",
                "url": "https://api.example.test/orders",
                "response": {"mode": "raw", "raw_column": "raw.response"},
            }
        )

    with pytest.raises(ValueError, match="records_path must not be used"):
        validate_source_semantics(
            {
                "type": "rest_api",
                "url": "https://api.example.test/orders",
                "response": {"mode": "raw", "records_path": "$.items"},
            }
        )

    with pytest.raises(ValueError, match="auth.type='digest'"):
        validate_source_semantics(
            {
                "type": "http_json",
                "url": "https://example.test/orders.json",
                "auth": {"type": "digest"},
            }
        )


def test_direct_rest_api_source_contract_is_accepted() -> None:
    source = validate_source_contract(
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.test/orders", "method": "POST", "json": {}},
            "pagination": {"type": "page"},
            "response": {"mode": "records"},
            "incremental": {"watermark_body_field": "updated_after"},
        }
    )

    assert source["type"] == "rest_api"
    assert source["request"]["method"] == "POST"
    validate_source_semantics(source)
