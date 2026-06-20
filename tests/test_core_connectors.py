import datetime as dt

import pytest

from contractforge_core.config import VALID_FILE_CONNECTOR_FORMATS, VALID_SOURCE_CONNECTORS
from contractforge_core.connectors import (
    catalog_source_query,
    catalog_source_table_or_path,
    delta_share_options,
    download_http_file,
    eventhubs_bounded_options,
    file_reader_options,
    file_source_format,
    generate_rds_iam_auth_token,
    http_file_format,
    http_file_headers,
    http_file_params,
    http_file_reader_options,
    http_file_url,
    infer_aws_region_from_rds_host,
    is_http_file_source,
    is_catalog_source,
    is_delta_share_source,
    is_file_source,
    is_native_passthrough_source,
    is_rest_api_connector,
    jdbc_common_options,
    list_source_connector_details,
    kafka_bounded_options,
    native_passthrough_descriptor,
    object_storage_provider,
    parse_jdbc_host_port,
    read_http_file_payload,
    rest_api_descriptor,
    source_capabilities,
    source_connector_details,
    source_metadata_from_contract,
    source_metadata_from_mapping,
    source_provider,
)
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.contracts.source_validation import validate_source_semantics
from contractforge_core.watermark import encode_watermark_values


def test_core_http_file_helpers_normalize_portable_contract() -> None:
    source = {
        "type": "http_csv",
        "request": {"params": {"region": "br"}, "headers": {"Accept": "text/csv"}},
        "auth": {"type": "api_key", "header": "X-Key", "value": "secret"},
        "options": {"header": True, "delimiter": ";"},
    }

    assert is_http_file_source(source)
    assert http_file_format(source) == "csv"
    assert http_file_params(source) == {"region": "br"}
    assert http_file_url({"type": "http_csv", "url": "https://example.com/orders.csv", **source}) == (
        "https://example.com/orders.csv?region=br"
    )
    assert http_file_headers(source)["X-Key"] == "secret"
    assert http_file_reader_options(source) == {"header": "true", "delimiter": ";"}


def test_core_http_file_reader_fetches_with_params_and_limits(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return b"id\n1\n"

    class FakeOpener:
        def open(self, request, timeout):
            calls.append((request.full_url, dict(request.header_items()), timeout))
            return FakeResponse()

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: FakeOpener())

    payload = read_http_file_payload(
        {
            "type": "http_csv",
            "request": {
                "url": "https://example.com/orders.csv",
                "params": {"region": "br"},
                "headers": {"Accept": "text/csv"},
            },
            "limits": {"timeout_seconds": 10, "max_bytes": 10},
        }
    )

    assert payload == b"id\n1\n"
    assert calls == [("https://example.com/orders.csv?region=br", {"Accept": "text/csv"}, 10)]


def test_core_http_file_download_returns_tracked_temp_file(monkeypatch) -> None:
    monkeypatch.setattr(
        "contractforge_core.connectors.http_files.http_file.reader.read_http_file_payload",
        lambda source: b"id\n1\n",
    )

    path = download_http_file({"type": "http_csv", "url": "https://example.com/orders.csv"})

    assert path.endswith(".csv")


def test_core_http_file_requires_bearer_token() -> None:
    with pytest.raises(ValueError, match="auth.token"):
        http_file_headers({"type": "http_json", "auth": {"type": "bearer_token"}})


def test_core_http_file_supports_basic_auth_header() -> None:
    headers = http_file_headers({"type": "http_json", "auth": {"type": "basic", "username": "u", "password": "p"}})

    assert headers["Authorization"] == "Basic dTpw"


def test_core_http_file_requires_canonical_api_key_value_and_rejects_unknown_auth() -> None:
    headers = http_file_headers({"type": "http_json", "auth": {"type": "api_key", "header": "X-Key", "value": "secret"}})

    assert headers["X-Key"] == "secret"
    with pytest.raises(ValueError, match="auth.value"):
        http_file_headers({"type": "http_json", "auth": {"type": "api_key", "header": "X-Key", "key": "secret"}})

    with pytest.raises(ValueError, match="auth.type='digest'"):
        http_file_headers({"type": "http_json", "auth": {"type": "digest"}})


def test_core_jdbc_common_options_include_rds_iam_review_boundary() -> None:
    options = jdbc_common_options(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://orders.abc123.us-east-1.rds.amazonaws.com/app",
            "table": "public.orders",
            "auth": {"type": "rds_iam", "username": "app_user"},
        }
    )

    assert options["dbtable"] == "public.orders"
    assert options["password"] == "{{rds_iam_token}}"
    assert options["contractforge.rdsIamRegion"] == "us-east-1"


def test_core_jdbc_common_options_support_canonical_basic_auth() -> None:
    options = jdbc_common_options(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "auth": {"type": "basic", "username": "app", "password": "secret"},
        }
    )

    assert options["user"] == "app"
    assert options["password"] == "secret"


def test_core_jdbc_common_options_rejects_legacy_auth_aliases() -> None:
    with pytest.raises(ValueError, match="JDBC auth.type"):
        jdbc_common_options(
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "auth": {"type": "password", "username": "app", "password": "secret"},
            }
        )
    with pytest.raises(ValueError, match="auth.username"):
        jdbc_common_options(
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://orders.abc123.us-east-1.rds.amazonaws.com/app",
                "table": "public.orders",
                "auth": {"type": "rds_iam", "user": "app_user"},
            }
        )


def test_core_jdbc_common_options_applies_incremental_predicate_to_table() -> None:
    options = jdbc_common_options(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "incremental": {"watermark_column": "updated_at", "watermark_value": "2026-01-01"},
        }
    )

    assert options["dbtable"] == "(SELECT * FROM public.orders WHERE updated_at > '2026-01-01') cf_src"


def test_core_jdbc_common_options_rejects_unsafe_incremental_watermark_column() -> None:
    with pytest.raises(ValueError, match="watermark_column must be a simple identifier"):
        jdbc_common_options(
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "incremental": {"watermark_column": "updated_at); DROP TABLE x; --", "watermark_value": "2026-01-01"},
            }
        )


def test_core_jdbc_common_options_accepts_dotted_incremental_watermark_column() -> None:
    options = jdbc_common_options(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "incremental": {"watermark_column": "cf_src.updated_at", "watermark_value": "2026-01-01"},
        }
    )

    assert options["dbtable"] == "(SELECT * FROM public.orders WHERE cf_src.updated_at > '2026-01-01') cf_src"


def test_core_jdbc_common_options_applies_incremental_predicate_to_query() -> None:
    options = jdbc_common_options(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "query": "select * from public.orders where tenant_id = 10",
            "incremental": {
                "watermark_column": "updated_at",
                "watermark_value": "2026-01-01T00:00:00Z",
                "predicate": "updated_at >= '{watermark}'",
                "alias": "orders_src",
            },
        }
    )

    assert "query" not in options
    assert options["dbtable"] == (
        "(SELECT * FROM (select * from public.orders where tenant_id = 10) orders_src "
        "WHERE updated_at >= '2026-01-01T00:00:00Z') orders_src"
    )


def test_core_jdbc_common_options_extracts_typed_incremental_watermark() -> None:
    options = jdbc_common_options(
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "incremental": {
                "watermark_column": "updated_at",
                "watermark_value": encode_watermark_values({"updated_at": "2026-01-01", "id": 100}),
            },
        }
    )

    assert options["dbtable"] == "(SELECT * FROM public.orders WHERE updated_at > '2026-01-01') cf_src"


def test_core_jdbc_common_options_reject_partial_partitioning() -> None:
    with pytest.raises(ValueError, match="JDBC partitioning requires"):
        jdbc_common_options(
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "read": {"partition_column": "id", "num_partitions": 8},
            }
        )


def test_core_jdbc_common_options_reject_unknown_auth_type() -> None:
    with pytest.raises(ValueError, match="JDBC auth.type"):
        jdbc_common_options(
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "auth": {"type": "oauth"},
            }
        )


def test_core_jdbc_catalog_includes_extended_portable_family() -> None:
    assert source_connector_details("oracle")["runtime_notes"]
    assert source_connector_details("snowflake_jdbc")["family"] == "jdbc"
    assert source_connector_details("bigquery_jdbc")["auth_modes"] == ["none", "basic", "oauth"]
    assert source_connector_details("oracle")["auth_modes"] == ["none", "basic"]
    assert "snowflake_jdbc" in {item["name"] for item in list_source_connector_details()}
    assert source_connector_details("postgresql")["portability"] == "UNSUPPORTED"
    assert "postgresql" not in {item["name"] for item in list_source_connector_details()}


def test_core_rds_iam_token_generation_is_platform_neutral() -> None:
    host, port = parse_jdbc_host_port("jdbc:postgresql://orders.abc123.us-east-1.rds.amazonaws.com/app")
    token = generate_rds_iam_auth_token(
        host=host,
        port=port,
        region=infer_aws_region_from_rds_host(host) or "",
        username="app_user",
        access_key="AKIDEXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
        now=dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc),
    )

    assert "X-Amz-Date=20260102T030405Z" in token
    assert "X-Amz-Signature=" in token


def test_core_file_object_and_catalog_helpers_are_platform_neutral() -> None:
    file_source = {"type": "s3", "format": "jsonl", "path": "s3://bucket/events", "options": {"multiLine": False}}
    xml_source = {"type": "xml", "path": "s3://bucket/events", "options": {"rowTag": "event"}}
    catalog_source = {"type": "sql", "query": "select * from main.raw.events"}
    table_source = {"type": "table", "table": "main.raw.events"}

    assert is_file_source(file_source)
    assert file_source_format(file_source) == "json"
    assert file_reader_options(file_source) == {"multiLine": "false"}
    assert is_file_source(xml_source)
    assert file_source_format(xml_source) == "xml"
    assert file_reader_options(xml_source) == {"rowTag": "event"}
    assert object_storage_provider(file_source) == "s3"
    assert is_catalog_source(catalog_source)
    assert catalog_source_query(catalog_source) == "select * from main.raw.events"
    assert catalog_source_table_or_path(table_source) == "main.raw.events"


def test_core_catalog_helpers_resolve_logical_table_refs_with_adapter_callback() -> None:
    def resolve(ref):
        return f"native.{ref.layer}.{ref.table}"

    table_source = {"type": "table", "ref": "bronze.orders"}
    sql_source = {"type": "sql", "query": "select * from {{ table_ref:bronze.orders }} where active = true"}

    assert catalog_source_table_or_path(table_source, table_ref_resolver=resolve) == "native.bronze.orders"
    assert catalog_source_query(sql_source, table_ref_resolver=resolve) == (
        "select * from native.bronze.orders where active = true"
    )


def test_core_connector_catalog_exposes_metadata_shape() -> None:
    details = source_connector_details("incremental_files")
    azure_blob = source_connector_details("azure_blob")
    rest = source_connector_details("rest_api")

    assert details["family"] == "incremental_files"
    assert details["incremental"] is True
    assert "supported_formats" in details
    assert "xml" in details["supported_formats"]
    assert "recommended_usage" in details
    assert azure_blob["conditional_required"] == [
        {"when": "auth.sas_token with a relative path", "requires": ["account_url", "container"]}
    ]
    assert rest["family"] == "api"
    assert "oauth_client_credentials" in rest["auth_modes"]
    assert "rate_limit_per_minute" in rest["limits"]
    assert "runtime" in rest


def test_core_source_validation_ports_connector_limit_guardrails() -> None:
    with pytest.raises(ValueError, match="retry_backoff_seconds"):
        validate_source_semantics(
            {
                "type": "rest_api",
                "url": "https://api.example.com/orders",
                "limits": {"retry_backoff_seconds": -0.1},
            }
        )

    with pytest.raises(ValueError, match="file_regex_max_listed"):
        validate_source_semantics(
            {
                "type": "s3",
                "format": "parquet",
                "path": "s3://bucket/orders",
                "read": {"file_regex_max_listed": 0},
            }
        )

    with pytest.raises(ValueError, match="does not support source.limits"):
        validate_source_semantics(
            {
                "type": "s3",
                "format": "parquet",
                "path": "s3://bucket/orders",
                "limits": {"max_pages": 10},
            }
        )

    with pytest.raises(ValueError, match="max_page_bytes"):
        validate_source_semantics(
            {
                "type": "http_json",
                "url": "https://example.com/data.json",
                "limits": {"max_page_bytes": 1024},
            }
        )

    with pytest.raises(ValueError, match="max_pages must be a positive integer"):
        validate_source_semantics(
            {
                "type": "rest_api",
                "url": "https://api.example.com/orders",
                "limits": {"max_pages": "many"},
            }
        )

    with pytest.raises(ValueError, match="rate_limit_per_minute must be a non-negative integer"):
        validate_source_semantics(
            {
                "type": "rest_api",
                "url": "https://api.example.com/orders",
                "limits": {"rate_limit_per_minute": "fast"},
            }
        )


def test_core_config_exports_portable_source_vocabulary() -> None:
    assert {
        "incremental_files",
        "delta_share",
        "snowflake_jdbc",
        "bigquery_jdbc",
        "xml",
        "kafka_available_now",
        "eventhubs_available_now",
    } <= VALID_SOURCE_CONNECTORS
    assert "autoloader" not in VALID_SOURCE_CONNECTORS
    assert "postgresql" not in VALID_SOURCE_CONNECTORS
    assert {"avro", "jsonl", "ndjson", "xml"} <= VALID_FILE_CONNECTOR_FORMATS


def test_core_kafka_bounded_options_are_platform_neutral() -> None:
    options = kafka_bounded_options(
        {
            "type": "kafka_bounded",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "starting_offsets": "earliest",
            "ending_offsets": "latest",
            "max_offsets_per_trigger": 1000,
        }
    )

    assert options["kafka.bootstrap.servers"] == "broker:9092"
    assert options["subscribe"] == "orders"
    assert options["startingOffsets"] == "earliest"
    assert options["endingOffsets"] == "latest"
    assert options["maxOffsetsPerTrigger"] == "1000"

    with pytest.raises(ValueError, match="topic"):
        kafka_bounded_options({"type": "kafka_bounded", "bootstrap_servers": "broker:9092"})


def test_kafka_bounded_source_round_trips_through_semantic_contract() -> None:
    """semantic_contract_from_mapping must preserve every kafka_bounded field
    on source.raw so the Databricks runtime can dispatch to spark.read.format('kafka')
    without options-dict workarounds."""

    from contractforge_core.contracts import semantic_contract_from_mapping

    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "kafka_bounded",
                "bootstrap_servers": "broker:9092",
                "topic": "orders",
                "starting_offsets": "earliest",
                "ending_offsets": "latest",
                "max_offsets_per_trigger": 1000,
                "options": {"kafka.security.protocol": "SASL_SSL"},
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
            "mode": "scd0_append",
        }
    )

    raw = contract.source.raw
    assert raw is not None
    assert raw["type"] == "kafka_bounded"
    assert raw["bootstrap_servers"] == "broker:9092"
    assert raw["topic"] == "orders"
    assert raw["starting_offsets"] == "earliest"
    assert raw["ending_offsets"] == "latest"
    assert raw["max_offsets_per_trigger"] == 1000
    assert raw["options"]["kafka.security.protocol"] == "SASL_SSL"

    options = kafka_bounded_options(raw)
    assert options["kafka.bootstrap.servers"] == "broker:9092"
    assert options["subscribe"] == "orders"
    assert options["kafka.security.protocol"] == "SASL_SSL"
    assert options["maxOffsetsPerTrigger"] == "1000"


def test_eventhubs_bounded_source_round_trips_through_semantic_contract() -> None:
    from contractforge_core.contracts import semantic_contract_from_mapping

    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "eventhubs_bounded",
                "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
                "event_hub_name": "orders",
                "starting_position": '{"offset":"0"}',
                "ending_position": '{"offset":"@latest"}',
                "max_events_per_trigger": 100,
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
            "mode": "scd0_append",
        }
    )

    raw = contract.source.raw
    assert raw["type"] == "eventhubs_bounded"
    assert raw["connection_string"].startswith("Endpoint=sb://")
    assert raw["event_hub_name"] == "orders"
    assert raw["starting_position"] == '{"offset":"0"}'
    assert raw["ending_position"] == '{"offset":"@latest"}'
    assert raw["max_events_per_trigger"] == 100

    options = eventhubs_bounded_options(raw)
    assert options["eventhubs.connectionString"].startswith("Endpoint=sb://")
    assert options["eventhubs.name"] == "orders"
    assert options["maxEventsPerTrigger"] == "100"

    limit_options = eventhubs_bounded_options(
        {
            "type": "eventhubs_bounded",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
            "event_hub_name": "orders",
            "limits": {"max_events_per_trigger": 250},
        }
    )

    assert limit_options["maxEventsPerTrigger"] == "250"


def test_core_eventhubs_bounded_options_are_platform_neutral() -> None:
    options = eventhubs_bounded_options(
        {
            "type": "eventhubs_bounded",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
            "event_hub_name": "orders",
            "starting_position": '{"offset":"0"}',
            "ending_position": '{"offset":"100"}',
        }
    )

    assert options["eventhubs.connectionString"].startswith("Endpoint=sb://")
    assert options["eventhubs.name"] == "orders"
    assert options["eventhubs.startingPosition"] == '{"offset":"0"}'
    assert options["eventhubs.endingPosition"] == '{"offset":"100"}'


def test_core_source_validation_requires_available_now_checkpoint() -> None:
    with pytest.raises(ValueError, match="checkpoint_location"):
        validate_source_semantics(
            {
                "type": "kafka_available_now",
                "bootstrap_servers": "broker:9092",
                "topic": "orders",
            }
        )

    validate_source_semantics(
        {
            "type": "eventhubs_available_now",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
            "event_hub_name": "orders",
            "checkpoint_location": "s3://state/orders",
            "limits": {"max_events_per_trigger": 1000},
        }
    )

    with pytest.raises(ValueError, match="source.limits.max_offsets_per_trigger"):
        validate_source_semantics(
            {
                "type": "kafka_available_now",
                "bootstrap_servers": "broker:9092",
                "topic": "orders",
                "checkpoint_location": "s3://state/orders",
                "limits": {"max_offsets_per_trigger": 0},
            }
        )


def test_core_delta_share_options_are_platform_neutral() -> None:
    source = {
        "type": "delta_share",
        "profile_file": "/Volumes/sec/profile.share",
        "table": "share.schema.table",
    }

    assert is_delta_share_source(source)
    assert delta_share_options(source) == {
        "profileFile": "/Volumes/sec/profile.share",
        "table": "share.schema.table",
    }

    with pytest.raises(ValueError, match="profile_file"):
        delta_share_options({"type": "delta_share", "table": "share.schema.table"})


def test_core_native_passthrough_descriptor_is_platform_neutral() -> None:
    source = {
        "type": "native_passthrough",
        "system": "salesforce",
        "object": "Account",
        "watermark": {"column": "SystemModstamp"},
        "auth": {"token": "raw", "client_id": "abc"},
    }

    assert is_native_passthrough_source(source)
    descriptor = native_passthrough_descriptor(source)
    assert descriptor["system"] == "salesforce"
    assert descriptor["object"] == "Account"
    assert descriptor["watermark"] == {"column": "SystemModstamp"}
    assert descriptor["auth"] == {"token": "<redacted>", "client_id": "abc"}


def test_core_rest_api_descriptor_is_platform_neutral() -> None:
    source = {
        "type": "connector",
        "connector": "rest_api",
        "name": "orders_api",
        "request": {"url": "https://api.example.test/orders", "method": "POST"},
        "pagination": {"type": "cursor"},
        "auth": {"password": "raw"},
    }

    assert is_rest_api_connector(source)
    descriptor = rest_api_descriptor(source)
    assert descriptor["source_name"] == "orders_api"
    assert descriptor["url"] == "https://api.example.test/orders"
    assert descriptor["method"] == "POST"
    assert descriptor["pagination"] == {"type": "cursor"}
    assert descriptor["auth"] == {"password": "<redacted>"}

    direct = rest_api_descriptor({"type": "rest_api", "url": "https://api.example.test/orders"})
    assert direct["url"] == "https://api.example.test/orders"


def test_core_source_metadata_helpers_are_platform_neutral() -> None:
    assert source_provider("s3", source={"path": "s3://bucket/orders"}) == "aws"
    assert source_provider("eventhubs_bounded") == "azure"
    assert source_provider("gcs", source={"path": "gs://bucket/orders"}) == "gcp"
    assert source_provider("snowflake_jdbc") == "snowflake"

    assert source_capabilities("incremental_files") == {
        "bounded": False,
        "incremental": True,
        "native_passthrough": False,
    }
    assert source_capabilities("native_passthrough")["native_passthrough"]


def test_core_source_metadata_from_contract_redacts_and_normalizes() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "connector",
                "connector": "postgres",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "auth": {"password": "raw-secret"},
            },
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    metadata = source_metadata_from_contract(contract, target_table="main.bronze.orders")

    assert metadata["target_table"] == "main.bronze.orders"
    assert metadata["source_type"] == "connector"
    assert metadata["source_connector"] == "postgres"
    assert metadata["source_table"] == "public.orders"
    assert metadata["source_query"] is False
    assert metadata["source_read"] == {"table": "public.orders"}
    assert metadata["source_auth"] == {"password": "***REDACTED***"}
    assert metadata["source_capabilities"]["incremental"] is True
    assert metadata["source_capabilities"]["source_complete"] is False

    rich_metadata = source_metadata_from_mapping(
        {
            "type": "connector",
            "connector": "rest_api",
            "name": "orders_api",
            "mode": "incremental",
            "connection": "prod_rest",
            "host": "api.example.test",
            "port": 443,
            "url": "https://api.example.test/orders",
            "environment_url": "https://api.example.test",
            "entity": "orders",
            "index": "orders_v1",
            "query": "status=active",
            "mailbox": "inbox",
            "auth": {"token": "raw-secret"},
        },
        target_table="main.bronze.orders",
    )

    assert rich_metadata["source_mode"] == "incremental"
    assert rich_metadata["source_connection"] == "prod_rest"
    assert rich_metadata["source_host"] == "api.example.test"
    assert rich_metadata["source_port"] == 443
    assert rich_metadata["source_url"] == "https://api.example.test/orders"
    assert rich_metadata["source_environment_url"] == "https://api.example.test"
    assert rich_metadata["source_entity"] == "orders"
    assert rich_metadata["source_index"] == "orders_v1"
    assert rich_metadata["source_mailbox"] == "inbox"
    assert rich_metadata["source_query"] is True
    assert rich_metadata["source_auth"]["token"] == "***REDACTED***"

    intent_metadata = source_metadata_from_mapping(
        {
            "type": "s3",
            "intent": "file_stream",
            "path": "s3://landing/orders",
            "format": "json",
            "discovery": {"strategy": "file_listing", "tracking": "modification_time"},
            "state": {"storage": "external", "location": {"type": "object_storage", "path": "s3://state/orders"}},
        },
        target_table="main.bronze.orders",
    )

    assert intent_metadata["source_type"] == "s3"
    assert intent_metadata["source_intent"] == "file_stream"
    assert intent_metadata["source_discovery"]["tracking"] == "modification_time"
    assert intent_metadata["source_state"]["storage"] == "external"

    table_contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    table_metadata = source_metadata_from_contract(table_contract)

    assert table_metadata["source_capabilities"]["source_complete"] is True

    declared_incomplete = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders", "read": {"source_complete": "false"}},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    declared_metadata = source_metadata_from_contract(declared_incomplete)

    assert declared_metadata["source_capabilities"]["source_complete"] is False

    stream_metadata = source_metadata_from_mapping(
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "checkpoint_location": "s3://state/orders",
            "max_offsets_per_trigger": 5000,
        },
        target_table="main.bronze.orders",
    )

    assert stream_metadata["source_incremental"]["checkpoint_location"] == "s3://state/orders"
    assert stream_metadata["source_limits"]["max_offsets_per_trigger"] == 5000
