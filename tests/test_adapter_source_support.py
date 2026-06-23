from __future__ import annotations

from contractforge_core.connectors.registry import CONNECTOR_CATALOG
from contractforge_aws.sources import aws_source_support, list_aws_source_support
from contractforge_aws.sources.classification import classify_aws_source
from contractforge_databricks.sources import databricks_source_support, list_databricks_source_support
from contractforge_databricks.sources.classification import classify_databricks_source
from contractforge_fabric.sources import fabric_source_support, list_fabric_source_support
from contractforge_fabric.sources.classification import classify_fabric_source
from contractforge_gcp.sources import (
    classify_gcp_source,
    gcp_source_support,
    is_gcp_source_renderable,
    list_gcp_source_support,
)


def test_databricks_source_support_declares_portable_connector_mappings() -> None:
    assert databricks_source_support({"type": "incremental_files", "path": "s3://b/x", "format": "json"}) == {
        "adapter": "databricks",
        "source_type": "incremental_files",
        "status": "SUPPORTED",
        "note": "Uses core incremental_files/file_stream intent.",
        "native_mapping": "Auto Loader cloudFiles",
    }
    assert databricks_source_support("http_json")["native_mapping"] == "Core HTTP file fetch + Spark reader"
    assert databricks_source_support("rest_api")["native_mapping"] == "Core REST client + Spark JSON materialization"
    assert databricks_source_support("custom_transform")["native_mapping"] == "Databricks notebook task in Asset Bundle"
    assert databricks_source_support("native_passthrough")["status"] == "REVIEW_REQUIRED"


def test_aws_source_support_declares_portable_connector_mappings() -> None:
    assert aws_source_support({"type": "incremental_files", "path": "s3://b/x", "format": "json"}) == {
        "adapter": "aws",
        "source_type": "incremental_files",
        "status": "SUPPORTED",
        "note": "Requires S3 path and bookmark-eligible format.",
        "native_mapping": "AWS Glue job bookmarks",
    }
    assert aws_source_support({"type": "incremental_files", "path": "s3://b/x", "format": "text"})["status"] == "REVIEW_REQUIRED"
    assert (
        aws_source_support({"type": "incremental_files", "path": "s3://b/x", "format": "json", "options": {"multiLine": "true"}})[
            "status"
        ]
        == "SUPPORTED"
    )
    assert aws_source_support("http_json")["native_mapping"] == "Core HTTP file fetch + Glue Spark materialization"
    assert aws_source_support("rest_api")["native_mapping"] == "Core REST client + Glue Spark JSON materialization"
    assert aws_source_support("parquet")["status"] == "SUPPORTED"
    assert aws_source_support("delta")["status"] == "SUPPORTED_WITH_WARNINGS"
    assert aws_source_support("gcs")["status"] == "SUPPORTED_WITH_WARNINGS"
    assert aws_source_support("kafka_available_now")["status"] == "REVIEW_REQUIRED"
    assert (
        aws_source_support(
            {
                "type": "kafka_available_now",
                "bootstrap_servers": "broker:9092",
                "topic": "events",
                "checkpoint_location": "s3://state/events",
            }
        )["status"]
        == "SUPPORTED_WITH_WARNINGS"
    )


def test_fabric_source_support_declares_notebook_first_source_mappings() -> None:
    rest = fabric_source_support({"type": "rest_api", "request": {"url": "https://api.example.com/orders"}})
    http_json = fabric_source_support({"type": "http_json", "request": {"url": "https://api.example.com/orders.json"}})
    rest_auth = fabric_source_support(
        {"type": "rest_api", "request": {"url": "https://api.example.com/orders"}, "auth": {"type": "bearer_token"}}
    )
    rest_secret_auth = fabric_source_support(
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "auth": {"type": "bearer_token", "token": "{{ secret:fabric/api-token }}"},
        }
    )
    sqlserver_secret_auth = fabric_source_support(
        {
            "type": "sqlserver",
            "url": "jdbc:sqlserver://cf-sql.database.windows.net:1433;database=contractforge",
            "table": "dbo.orders",
            "auth": {"type": "basic", "username": "cfreader", "password": "{{ secret:fabric/sql-password }}"},
        }
    )
    postgres_secret_auth = fabric_source_support(
        {
            "type": "postgres",
            "url": "jdbc:postgresql://db.example.com:5432/postgres?sslmode=require",
            "table": "public.orders",
            "auth": {"type": "basic", "username": "cfreader", "password": "{{ secret:fabric/pg-password }}"},
        }
    )
    kafka_bounded_secret_auth = fabric_source_support(
        {
            "type": "kafka_bounded",
            "bootstrap_servers": "broker:9093",
            "topic": "orders",
            "starting_offsets": "earliest",
            "ending_offsets": "latest",
            "options": {
                "kafka.security.protocol": "SASL_SSL",
                "kafka.sasl.mechanism": "PLAIN",
                "kafka.sasl.jaas.config": "{{ secret:fabric/eventhubs-jaas }}",
            },
        }
    )
    kafka_available_now_secret_auth = fabric_source_support(
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "broker:9093",
            "topic": "orders",
            "starting_offsets": "earliest",
            "checkpoint_location": "Files/checkpoints/orders",
            "options": {
                "kafka.security.protocol": "SASL_SSL",
                "kafka.sasl.mechanism": "PLAIN",
                "kafka.sasl.jaas.config": "{{ secret:fabric/eventhubs-jaas }}",
            },
        }
    )

    assert fabric_source_support("sql")["status"] == "SUPPORTED"
    assert fabric_source_support("parquet")["status"] == "SUPPORTED"
    assert fabric_source_support("delta")["status"] == "SUPPORTED"
    assert rest["status"] == "SUPPORTED_WITH_WARNINGS"
    assert rest["renderable"] is True
    assert rest["native_mapping"] == "Fabric notebook bounded REST fetch via ContractForge core"
    assert "USGS REST/GeoJSON bronze-to-gold E2E" in rest["note"]
    assert http_json["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_json["renderable"] is True
    assert rest_auth["status"] == "REVIEW_REQUIRED"
    assert rest_auth["renderable"] is False
    assert rest_secret_auth["status"] == "REVIEW_REQUIRED"
    assert rest_secret_auth["renderable"] is True
    assert "Key Vault" in rest_secret_auth["native_mapping"]
    assert fabric_source_support("jdbc")["status"] == "REVIEW_REQUIRED"
    assert sqlserver_secret_auth["status"] == "REVIEW_REQUIRED"
    assert sqlserver_secret_auth["renderable"] is True
    assert "SQL Server JDBC" in sqlserver_secret_auth["native_mapping"]
    assert postgres_secret_auth["status"] == "REVIEW_REQUIRED"
    assert postgres_secret_auth["renderable"] is True
    assert "PostgreSQL JDBC" in postgres_secret_auth["native_mapping"]
    assert fabric_source_support("kafka_available_now")["status"] == "REVIEW_REQUIRED"
    assert kafka_available_now_secret_auth["status"] == "REVIEW_REQUIRED"
    assert kafka_available_now_secret_auth["renderable"] is True
    assert "Kafka available-now" in kafka_available_now_secret_auth["native_mapping"]
    assert kafka_bounded_secret_auth["status"] == "REVIEW_REQUIRED"
    assert kafka_bounded_secret_auth["renderable"] is True
    assert "bounded Kafka replay" in kafka_bounded_secret_auth["native_mapping"]


def test_adapter_source_support_lists_are_adapter_owned() -> None:
    databricks = {item["source_type"]: item for item in list_databricks_source_support()}
    aws = {item["source_type"]: item for item in list_aws_source_support()}
    fabric = {item["source_type"]: item for item in list_fabric_source_support()}
    gcp = {item["source_type"]: item for item in list_gcp_source_support()}

    for name in ("jdbc", "http_json", "rest_api", "incremental_files", "native_passthrough"):
        assert name in databricks
        assert name in aws
        assert name in fabric
        assert name in gcp
        assert databricks[name]["adapter"] == "databricks"
        assert aws[name]["adapter"] == "aws"
        assert fabric[name]["adapter"] == "fabric"
        assert gcp[name]["adapter"] == "gcp"


def test_aws_source_support_lists_every_core_runtime_connector() -> None:
    aws = {item["source_type"]: item for item in list_aws_source_support()}
    expected = set(CONNECTOR_CATALOG) - {"connection"}

    assert expected <= set(aws)
    assert "connection" not in aws


def test_fabric_source_support_lists_every_core_runtime_connector() -> None:
    fabric = {item["source_type"]: item for item in list_fabric_source_support()}
    expected = set(CONNECTOR_CATALOG) - {"connection"}

    assert expected <= set(fabric)
    assert "connection" not in fabric


def test_gcp_source_support_lists_every_core_runtime_connector() -> None:
    gcp = {item["source_type"]: item for item in list_gcp_source_support()}
    expected = set(CONNECTOR_CATALOG) - {"connection"}

    assert expected <= set(gcp)
    assert "connection" not in gcp
    assert gcp["delta"]["status"] == "REVIEW_REQUIRED"
    assert gcp["delta_table"]["status"] == "REVIEW_REQUIRED"
    assert gcp["delta_share"]["status"] == "REVIEW_REQUIRED"
    assert gcp["rest_api"]["status"] == "SUPPORTED_WITH_WARNINGS"
    assert gcp["http_json"]["status"] == "SUPPORTED_WITH_WARNINGS"
    assert gcp["http_csv"]["status"] == "SUPPORTED_WITH_WARNINGS"
    assert gcp["http_text"]["status"] == "SUPPORTED_WITH_WARNINGS"
    assert gcp["http_file"]["status"] == "REVIEW_REQUIRED"
    assert gcp["native_passthrough"]["status"] == "REVIEW_REQUIRED"
    assert gcp["oracle"]["status"] == "REVIEW_REQUIRED"
    assert gcp["bigquery_jdbc"]["status"] == "REVIEW_REQUIRED"


def test_aws_source_support_uses_same_classification_as_renderability() -> None:
    cases = (
        ({"type": "jdbc", "url": "jdbc:postgresql://h/db", "table": "public.t"}, True),
        ({"type": "incremental_files", "path": "s3://b/x", "format": "json"}, True),
        ({"type": "incremental_files", "path": "s3://b/x", "format": "text"}, False),
        ({"type": "rest_api", "request": {"url": "https://api.example.com/x"}}, True),
        ({"type": "kafka_available_now", "bootstrap_servers": "b:9092", "topic": "t"}, False),
        (
            {
                "type": "eventhubs_available_now",
                "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
                "event_hub_name": "events",
                "checkpoint_location": "s3://state/events",
            },
            True,
        ),
        ({"type": "native_passthrough", "system": "salesforce"}, False),
    )

    for source, renderable in cases:
        classification = classify_aws_source(source)
        support = aws_source_support(source)
        assert classification.renderable is renderable
        assert support["status"] == classification.status
        assert support["note"] == classification.note


def test_databricks_source_support_uses_adapter_classification() -> None:
    cases = (
        {"type": "jdbc", "url": "jdbc:postgresql://h/db", "table": "public.t"},
        {"type": "incremental_files", "path": "s3://b/x", "format": "json"},
        {"type": "rest_api", "request": {"url": "https://api.example.com/x"}},
        {"type": "native_passthrough", "system": "salesforce"},
        {"type": "unknown_vendor_source"},
    )

    for source in cases:
        classification = classify_databricks_source(source)
        support = databricks_source_support(source)
        assert support["status"] == classification.status
        assert support["note"] == classification.note


def test_fabric_source_support_uses_adapter_classification() -> None:
    cases = (
        {"type": "sql", "query": "select 1 as id"},
        {"type": "parquet", "path": "Files/orders"},
        {"type": "rest_api", "request": {"url": "https://api.example.com/x"}},
        {"type": "rest_api", "request": {"url": "https://api.example.com/x"}, "auth": {"type": "bearer_token"}},
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/x"},
            "auth": {"type": "bearer_token", "token": "{{ secret:fabric/api-token }}"},
        },
        {
            "type": "sqlserver",
            "url": "jdbc:sqlserver://cf-sql.database.windows.net:1433;database=contractforge",
            "table": "dbo.orders",
            "auth": {"type": "basic", "username": "cfreader", "password": "{{ secret:fabric/sql-password }}"},
        },
        {"type": "native_passthrough", "system": "salesforce"},
        {"type": "unknown_vendor_source"},
    )

    for source in cases:
        classification = classify_fabric_source(source)
        support = fabric_source_support(source)
        assert support["status"] == classification.status
        assert support["note"] == classification.note
        assert support["renderable"] == classification.renderable


def test_gcp_source_support_uses_adapter_classification() -> None:
    cases = (
        {"type": "table", "table": "raw.orders"},
        {"type": "gcs", "format": "csv", "path": "gs://bucket/orders.csv"},
        {"type": "gcs", "format": "csv", "path": "s3://bucket/orders.csv"},
        {"type": "iceberg_table", "table": "project.dataset.orders_iceberg"},
        {"type": "iceberg_table", "path": "gs://bucket/iceberg/orders"},
        {"type": "rest_api", "request": {"url": "https://api.example.com/x"}},
        {"type": "rest_api", "request": {"url": "https://api.example.com/x"}, "auth": {"type": "bearer_token"}},
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/x"},
            "auth": {"type": "bearer_token", "token": "{{ secret:gcp/api-token }}"},
        },
        {"type": "http_json", "request": {"url": "https://api.example.com/x.json"}},
        {
            "type": "http_json",
            "request": {"url": "https://api.example.com/x.json"},
            "auth": {"type": "bearer_token", "token": "{{ secret:gcp/http-token }}"},
        },
        {"type": "http_csv", "request": {"url": "https://api.example.com/x.csv"}},
        {"type": "delta_share", "profile_file": "profile.json", "table": "share.schema.table"},
        {"type": "http_text", "request": {"url": "https://api.example.com/x.txt"}},
        {"type": "oracle", "url": "jdbc:oracle:thin:@//h:1521/db", "table": "T"},
        {"type": "native_passthrough", "system": "salesforce"},
        {"type": "unknown_vendor_source"},
    )

    for source in cases:
        classification = classify_gcp_source(source)
        support = gcp_source_support(source)
        assert support["status"] == classification.status
        assert support["note"] == classification.note
        assert support["renderable"] == classification.renderable
        assert is_gcp_source_renderable(source) == classification.renderable
