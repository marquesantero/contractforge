from __future__ import annotations

import pytest

from contractforge_databricks.runtime import (
    list_source_resolvers,
    register_source_resolver,
    unregister_source_resolver,
)
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.runtime.sources import (
    prepare_contract_source_view,
    prepare_source_view,
    resolve_source_dataframe,
)


class FakeDataFrame:
    columns = ["id", "value"]

    def __init__(self) -> None:
        self.views = []
        self.filters = []
        self.schema = FakeSchema([FakeField("id", "BIGINT"), FakeField("value", "STRING")])

    def createOrReplaceTempView(self, name: str) -> None:
        self.views.append(name)

    def count(self) -> int:
        return 7

    def select(self, *columns: str) -> "FakeDataFrame":
        self.columns = list(columns)
        self.schema = FakeSchema([field for field in self.schema.fields if field.name in self.columns])
        return self

    def where(self, predicate: str) -> "FakeDataFrame":
        self.filters.append(predicate)
        return self

    def withColumnRenamed(self, source: str, target: str) -> "FakeDataFrame":
        self.columns = [target if column == source else column for column in self.columns]
        self.schema = FakeSchema(
            [FakeField(target if field.name == source else field.name, field.dataType.simpleString()) for field in self.schema.fields]
        )
        return self


class FakeReader:
    def __init__(self) -> None:
        self.calls = []
        self.df = FakeDataFrame()

    def format(self, value: str) -> "FakeReader":
        self.calls.append(("format", value))
        return self

    def option(self, key: str, value: str) -> "FakeReader":
        self.calls.append(("option", key, value))
        return self

    def schema(self, value: str) -> "FakeReader":
        self.calls.append(("schema", value))
        return self

    def load(self, path: str | None = None) -> FakeDataFrame:
        self.calls.append(("load", path))
        return self.df


class FakeConf:
    def __init__(self, error: Exception | None = None) -> None:
        self.values = {}
        self.error = error

    def set(self, key: str, value: str) -> None:
        if self.error is not None:
            raise self.error
        self.values[key] = value


class FakeSpark:
    def __init__(self, conf_error: Exception | None = None) -> None:
        self.conf = FakeConf(conf_error)
        self.read = FakeReader()
        self.readStream = FakeReader()
        self.table_calls = []
        self.sql_calls = []
        self.table_df = FakeDataFrame()
        self.sql_df = FakeDataFrame()
        self.created_dataframes = []

    def table(self, name: str) -> FakeDataFrame:
        self.table_calls.append(name)
        return self.table_df

    def sql(self, statement: str) -> FakeDataFrame:
        self.sql_calls.append(statement)
        return self.sql_df

    def createDataFrame(self, records):
        self.created_dataframes.append(records)
        return FakeDataFrame()


class FakeType:
    def __init__(self, name: str) -> None:
        self.name = name

    def simpleString(self) -> str:
        return self.name


class FakeField:
    def __init__(self, name: str, data_type: str) -> None:
        self.name = name
        self.dataType = FakeType(data_type)


class FakeSchema:
    def __init__(self, fields: list[FakeField]) -> None:
        self.fields = fields


class CustomResolver:
    def __init__(self) -> None:
        self.calls = []

    def resolve(self, spark, source):
        self.calls.append((spark, source))
        return spark.createDataFrame([{"custom": True}])


def test_resolve_catalog_table_and_sql_sources() -> None:
    spark = FakeSpark()

    assert resolve_source_dataframe(spark, {"type": "table", "table": "main.raw.orders"}) is spark.table_df
    assert resolve_source_dataframe(spark, {"type": "sql", "query": "select * from main.raw.orders"}) is spark.sql_df
    assert (
        resolve_source_dataframe(
            spark,
            {"type": "connector", "connector": "sql", "query": "select count(*) from main.raw.orders"},
        )
        is spark.sql_df
    )

    assert spark.table_calls == ["main.raw.orders"]
    assert spark.sql_calls == ["select * from main.raw.orders", "select count(*) from main.raw.orders"]


def test_resolve_file_source_uses_spark_reader_options() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {"type": "csv", "path": "s3://bucket/orders", "options": {"header": True}},
    )

    assert ("format", "csv") in spark.read.calls
    assert ("option", "header", "true") in spark.read.calls
    assert ("load", "s3://bucket/orders") in spark.read.calls


def test_resolve_file_source_applies_declared_schema() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "csv",
            "path": "s3://bucket/orders",
            "read": {"schema": "id BIGINT, value STRING"},
            "options": {"header": True},
        },
    )

    assert ("schema", "id BIGINT, value STRING") in spark.read.calls
    assert ("option", "schema", "id BIGINT, value STRING") not in spark.read.calls


def test_resolve_file_source_rejects_conflicting_declared_schema() -> None:
    with pytest.raises(ValueError, match="source.read.schema conflicts"):
        resolve_source_dataframe(
            FakeSpark(),
            {
                "type": "csv",
                "path": "s3://bucket/orders",
                "read": {"schema": "id BIGINT"},
                "options": {"schema": "id STRING"},
            },
        )


def test_resolve_file_source_rejects_top_level_schema_alias() -> None:
    with pytest.raises(ValueError, match="source.schema is not supported"):
        resolve_source_dataframe(
            FakeSpark(),
            {"type": "csv", "path": "s3://bucket/orders", "schema": "id BIGINT"},
        )


def test_resolve_file_source_applies_file_regex_selection() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "parquet",
            "path": "s3://bucket/orders",
            "read": {
                "file_regex": r"orders_\d+\.parquet$",
                "file_regex_scope": "filename",
                "files": [
                    "s3://bucket/orders/_SUCCESS",
                    "s3://bucket/orders/year=2026/orders_01.parquet",
                    "s3://bucket/orders/year=2026/ignore.txt",
                ],
            },
        },
    )

    assert ("load", ["s3://bucket/orders/year=2026/orders_01.parquet"]) in spark.read.calls


def test_resolve_s3_source_configures_spark_auth_and_splits_hadoop_options() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "s3",
            "format": "parquet",
            "path": "s3://bucket/orders",
            "auth": {
                "access_key_id": "access",
                "secret_access_key": "secret",
                "session_token": "session",
            },
            "options": {"fs.s3a.endpoint": "https://s3.local", "mergeSchema": True},
        },
    )

    assert spark.conf.values["fs.s3a.access.key"] == "access"
    assert spark.conf.values["fs.s3a.secret.key"] == "secret"
    assert spark.conf.values["fs.s3a.session.token"] == "session"
    assert spark.conf.values["fs.s3a.endpoint"] == "https://s3.local"
    assert ("option", "mergeSchema", "true") in spark.read.calls
    assert ("option", "fs.s3a.endpoint", "https://s3.local") not in spark.read.calls


def test_resolve_s3_source_rejects_partial_credentials() -> None:
    with pytest.raises(ValueError, match="access_key_id and secret_access_key together"):
        resolve_source_dataframe(
            FakeSpark(),
            {"type": "s3", "format": "parquet", "path": "s3://bucket/orders", "auth": {"access_key_id": "access"}},
        )


def test_resolve_s3_source_explains_serverless_config_block() -> None:
    with pytest.raises(RuntimeError, match="blocked Spark S3 credential configuration"):
        resolve_source_dataframe(
            FakeSpark(conf_error=RuntimeError("CONFIG_NOT_AVAILABLE")),
            {
                "type": "s3",
                "format": "parquet",
                "path": "s3://bucket/orders",
                "auth": {"access_key_id": "access", "secret_access_key": "secret"},
            },
        )


def test_resolve_azure_blob_source_configures_sas_and_normalizes_relative_path() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "azure_blob",
            "format": "csv",
            "path": "landing/orders.csv",
            "account_url": "https://acct.blob.core.windows.net",
            "container": "raw",
            "auth": {"sas_token": "?sig=abc"},
        },
    )

    assert spark.conf.values["fs.azure.sas.raw.acct.blob.core.windows.net"] == "sig=abc"
    assert ("load", "wasbs://raw@acct.blob.core.windows.net/landing/orders.csv") in spark.read.calls


def test_resolve_azure_blob_source_explains_serverless_config_block() -> None:
    with pytest.raises(RuntimeError, match="blocked Spark SAS configuration"):
        resolve_source_dataframe(
            FakeSpark(conf_error=RuntimeError("CONFIG_NOT_AVAILABLE")),
            {
                "type": "azure_blob",
                "format": "csv",
                "path": "landing/orders.csv",
                "account_url": "https://acct.blob.core.windows.net",
                "container": "raw",
                "auth": {"sas_token": "?sig=abc"},
            },
        )


def test_resolve_file_source_rejects_file_regex_without_listing_access() -> None:
    with pytest.raises(RuntimeError, match="file_regex requires Hadoop FileSystem access"):
        resolve_source_dataframe(
            FakeSpark(),
            {
                "type": "parquet",
                "path": "s3://bucket/orders",
                "read": {"file_regex": r"orders_\d+\.parquet$"},
            },
        )


def test_resolve_jdbc_source_loads_with_common_options() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {"type": "jdbc", "url": "jdbc:postgresql://host/db", "table": "public.orders"},
    )

    assert ("format", "jdbc") in spark.read.calls
    assert ("option", "url", "jdbc:postgresql://host/db") in spark.read.calls
    assert ("option", "dbtable", "public.orders") in spark.read.calls
    assert ("load", None) in spark.read.calls


def test_resolve_jdbc_source_loads_with_incremental_pushdown() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "incremental": {"watermark_column": "updated_at", "watermark_value": "2026-01-01"},
        },
    )

    assert ("format", "jdbc") in spark.read.calls
    assert ("option", "dbtable", "(SELECT * FROM public.orders WHERE updated_at > '2026-01-01') cf_src") in spark.read.calls


def test_resolve_source_dataframe_resolves_databricks_secret_placeholders(monkeypatch) -> None:
    spark = FakeSpark()
    monkeypatch.setenv("CONTRACTFORGE_ALLOW_SECRET_ENV_OVERRIDE", "1")
    monkeypatch.setenv("CONTRACTFORGE_SECRET_JDBC_PROD_PASSWORD", "resolved-password")

    resolve_source_dataframe(
        spark,
        {
            "type": "jdbc",
            "url": "jdbc:postgresql://host/db",
            "table": "public.orders",
            "options": {"password": "{{ secret:jdbc-prod/password }}"},
        },
    )

    assert ("option", "password", "resolved-password") in spark.read.calls


def test_resolve_jdbc_source_rejects_inline_password() -> None:
    with pytest.raises(ValueError, match="JDBC 'password' must be provided via"):
        resolve_source_dataframe(
            FakeSpark(),
            {
                "type": "jdbc",
                "url": "jdbc:postgresql://host/db",
                "table": "public.orders",
                "auth": {"type": "basic", "username": "app", "password": "raw-password"},
            },
        )


def test_resolve_jdbc_source_rejects_inline_url_credentials() -> None:
    with pytest.raises(ValueError, match="JDBC url embeds inline credentials"):
        resolve_source_dataframe(
            FakeSpark(),
            {"type": "jdbc", "url": "jdbc:postgresql://user:password@host/db", "table": "public.orders"},
        )


def test_resolve_http_file_downloads_and_loads_with_spark(monkeypatch, tmp_path) -> None:
    spark = FakeSpark()
    downloaded = tmp_path / "orders.json"
    downloaded.write_text('{"id": 1}\n', encoding="utf-8")

    monkeypatch.setattr(
        "contractforge_databricks.runtime.http_file.download_http_file",
        lambda source: str(downloaded),
    )

    resolve_source_dataframe(
        spark,
        {"type": "http_json", "url": "https://example.com/orders.json", "options": {"multiLine": False}},
    )

    assert ("format", "json") in spark.read.calls
    assert ("option", "multiLine", "false") in spark.read.calls
    assert ("load", str(downloaded)) in spark.read.calls


def test_resolve_http_file_applies_declared_schema(monkeypatch, tmp_path) -> None:
    spark = FakeSpark()
    downloaded = tmp_path / "orders.json"
    downloaded.write_text('{"id": 1}\n', encoding="utf-8")
    monkeypatch.setattr(
        "contractforge_databricks.runtime.http_file.download_http_file",
        lambda source: str(downloaded),
    )

    resolve_source_dataframe(
        spark,
        {"type": "http_json", "url": "https://example.com/orders.json", "read": {"schema": "id BIGINT"}},
    )

    assert ("schema", "id BIGINT") in spark.read.calls


def test_resolve_rest_api_source_creates_dataframe(monkeypatch) -> None:
    spark = FakeSpark()

    monkeypatch.setattr(
        "contractforge_databricks.runtime.rest_api.read_rest_api_records",
        lambda source: [{"id": 1}, {"id": 2}],
    )

    resolve_source_dataframe(spark, {"type": "connector", "connector": "rest_api", "request": {"url": "https://api"}})

    assert spark.created_dataframes == [[{"id": 1}, {"id": 2}]]


def test_resolve_incremental_files_uses_read_stream_cloudfiles() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "incremental_files",
            "path": "s3://bucket/landing/orders",
            "format": "json",
            "schema_tracking_location": "s3://bucket/_schemas/orders",
        },
    )

    assert ("format", "cloudFiles") in spark.readStream.calls
    assert ("option", "cloudFiles.format", "json") in spark.readStream.calls
    assert ("option", "cloudFiles.schemaLocation", "s3://bucket/_schemas/orders") in spark.readStream.calls
    assert ("load", "s3://bucket/landing/orders") in spark.readStream.calls


def test_resolve_file_stream_intent_uses_read_stream_cloudfiles() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "s3",
            "intent": "file_stream",
            "path": "s3://bucket/landing/orders",
            "format": "json",
            "state": {
                "storage": "external",
                "location": {"type": "object_storage", "path": "s3://bucket/_checkpoints/orders"},
            },
        },
    )

    assert ("format", "cloudFiles") in spark.readStream.calls
    assert ("option", "cloudFiles.format", "json") in spark.readStream.calls
    assert ("load", "s3://bucket/landing/orders") in spark.readStream.calls
    assert not spark.read.calls


def test_resolve_kafka_bounded_uses_spark_read() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "kafka_bounded",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "starting_offsets": "earliest",
        },
    )

    assert ("format", "kafka") in spark.read.calls
    assert ("option", "kafka.bootstrap.servers", "broker:9092") in spark.read.calls
    assert ("option", "subscribe", "orders") in spark.read.calls
    # readStream must not be touched for the bounded variant.
    assert spark.readStream.calls == []


def test_resolve_kafka_available_now_uses_spark_read_stream() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "starting_offsets": "earliest",
            "checkpoint_location": "dbfs:/checkpoints/orders",
        },
    )

    assert ("format", "kafka") in spark.readStream.calls
    assert ("option", "kafka.bootstrap.servers", "broker:9092") in spark.readStream.calls
    assert ("option", "subscribe", "orders") in spark.readStream.calls
    assert spark.read.calls == []


def test_resolve_kafka_available_now_shades_plain_login_module_for_databricks() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "kafka_available_now",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "checkpoint_location": "dbfs:/checkpoints/orders",
            "options": {
                "kafka.security.protocol": "SASL_SSL",
                "kafka.sasl.mechanism": "PLAIN",
                "kafka.sasl.jaas.config": (
                    "org.apache.kafka.common.security.plain.PlainLoginModule required "
                    'username="contract-user" password="contract-password";'
                ),
            },
        },
    )

    assert (
        "option",
        "kafka.sasl.jaas.config",
        "kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required "
        'username="contract-user" password="contract-password";',
    ) in spark.readStream.calls


def test_resolve_eventhubs_available_now_uses_spark_read_stream() -> None:
    spark = FakeSpark()

    resolve_source_dataframe(
        spark,
        {
            "type": "eventhubs_available_now",
            "connection_string": "Endpoint=sb://ns/;SharedAccessKey=secret",
            "event_hub_name": "orders",
            "starting_position": '{"offset":"0"}',
            "checkpoint_location": "dbfs:/checkpoints/orders",
        },
    )

    assert ("format", "eventhubs") in spark.readStream.calls
    found_event_hub_name = any(call == ("option", "eventhubs.name", "orders") for call in spark.readStream.calls)
    assert found_event_hub_name
    assert spark.read.calls == []


def test_prepare_source_view_returns_core_prepared_input() -> None:
    spark = FakeSpark()

    prepared = prepare_source_view(
        spark,
        {"type": "parquet", "path": "s3://bucket/orders"},
        view_name="cf_source_orders",
        collect_metrics=True,
    )

    assert prepared.source_view == "cf_source_orders"
    assert prepared.source_columns == ("id", "value")
    assert prepared.source_schema == {"id": "BIGINT", "value": "STRING"}
    assert prepared.rows_read == 7
    assert prepared.source_name == "s3://bucket/orders"
    assert prepared.source_metadata["source_provider"] == "aws"
    assert prepared.source_metadata["source_capabilities"]["source_complete"] is False
    assert spark.read.df.views == ["cf_source_orders"]


def test_prepare_contract_source_view_applies_core_preparation() -> None:
    spark = FakeSpark()
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"table": "orders"},
            "select_columns": ["id", "value"],
            "column_mapping": {"id": "order_id"},
        }
    )

    prepared = prepare_contract_source_view(spark, contract, view_name="cf_orders", collect_metrics=True)

    assert prepared.source_view == "cf_orders"
    assert prepared.source_columns == ("order_id", "value")
    assert prepared.source_schema == {"order_id": "BIGINT", "value": "STRING"}
    assert prepared.rows_read == 7
    assert prepared.source_name == "main.raw.orders"
    assert spark.table_calls == ["main.raw.orders"]
    assert spark.table_df.views == ["cf_orders"]


def test_prepare_contract_source_view_applies_previous_state_watermark_filter() -> None:
    spark = FakeSpark()
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["id"],
            "watermark_columns": ["id"],
        }
    )
    queries = []

    def query_one(statement: str):
        queries.append(statement)
        return {"watermark_value": '{"id":{"type":"BIGINT","value":"10"}}'}

    prepared = prepare_contract_source_view(
        spark,
        contract,
        view_name="cf_orders",
        query_one=query_one,
        evidence_catalog="ops",
        evidence_schema="audit",
    )

    assert "FROM `ops`.`audit`.`ctrl_ingestion_state`" in queries[0]
    assert spark.table_df.filters == ["`id` > CAST('10' AS BIGINT)"]
    assert prepared.source_metadata["watermark_previous"] == '{"id":{"type":"BIGINT","value":"10"}}'


def test_resolve_rejects_review_only_sources() -> None:
    with pytest.raises(ValueError, match="cannot be resolved"):
        resolve_source_dataframe(FakeSpark(), {"type": "native_passthrough", "system": "salesforce"})


def test_runtime_source_resolver_registry_supports_custom_sources() -> None:
    spark = FakeSpark()
    resolver = CustomResolver()

    unregister_source_resolver("custom_api")
    register_source_resolver("custom_api", resolver)
    try:
        result = resolve_source_dataframe(spark, {"type": "custom_api", "url": "https://example.test"})

        assert isinstance(result, FakeDataFrame)
        assert spark.created_dataframes == [[{"custom": True}]]
        assert "custom_api" in list_source_resolvers()
        assert resolver.calls[0][1]["type"] == "custom_api"
    finally:
        unregister_source_resolver("custom_api")


def test_runtime_source_resolver_registry_rejects_duplicates_and_bad_names() -> None:
    resolver = CustomResolver()
    unregister_source_resolver("custom_api")
    register_source_resolver("custom_api", resolver)
    try:
        with pytest.raises(ValueError, match="already registered"):
            register_source_resolver("custom_api", resolver)
        with pytest.raises(ValueError, match="source_type"):
            register_source_resolver("1_bad", resolver)
    finally:
        unregister_source_resolver("custom_api")
