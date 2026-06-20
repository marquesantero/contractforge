from __future__ import annotations

import base64
import json

from contractforge_fabric import (
    FABRIC_RESOURCE,
    FABRIC_SUBTARGET_LAKEHOUSE,
    AzureCliFabricTokenProvider,
    FabricAdapter,
    fabric_lakehouse_capabilities,
    fabric_source_review_payload,
    fabric_source_support,
    list_fabric_source_support,
    plan_fabric_contract,
    render_fabric_contract,
)
from contractforge_fabric.cli import main as fabric_cli
from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.security import render_secret_aware_literal, render_secret_resolver_helper


def _contract(mode: str = "overwrite") -> dict[str, object]:
    return {
        "source": {"type": "parquet", "path": "Files/orders"},
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "layer": "bronze",
        "mode": mode,
    }


def _environment() -> dict[str, object]:
    return {
        "parameters": {
            "fabric": {
                "tenant_id": "3fb3492c-48be-4ac6-ae3a-fec6a63cf4d1",
                "tenant_domain": "ticomcafe.com.br",
                "workspace_name": "cf-dev",
                "lakehouse_name": "contractforge_lh",
                "warehouse_name": "contractforge_wh",
            }
        },
        "evidence": {"lakehouse": "contractforge_lh", "schema": "contractforge"},
        "artifacts": {"uri": "abfss://workspace@onelake.dfs.fabric.microsoft.com/artifacts"},
        "runtime": {"kind": "notebook"},
    }


def _environment_with_key_vault() -> dict[str, object]:
    environment = _environment()
    environment["secrets"] = {
        "vault_url": "https://contractforge-default.vault.azure.net/",
        "scopes": {"fabric": "https://contractforge-fabric.vault.azure.net/"},
    }
    return environment


def test_fabric_capabilities_are_conservative_until_runtime_is_validated() -> None:
    capabilities = fabric_lakehouse_capabilities()

    assert capabilities.platform == FABRIC_SUBTARGET_LAKEHOUSE
    assert capabilities.supports_append is True
    assert capabilities.supports_overwrite is True
    assert capabilities.supports_merge is True
    assert capabilities.supports_hash_diff is True
    assert capabilities.supports_scd2 is True
    assert capabilities.supports_snapshot_soft_delete is True
    assert capabilities.evidence_stores == ("fabric_lakehouse_delta_tables",)
    assert "source.rest_api.authenticated" in capabilities.review_required_semantics
    assert "source.http_file.authenticated" in capabilities.review_required_semantics
    assert "hash_diff_upsert" not in capabilities.review_required_semantics
    assert "snapshot_soft_delete" not in capabilities.review_required_semantics
    assert "scd2_historical" not in capabilities.review_required_semantics


def test_fabric_source_support_declares_native_and_review_required_mappings() -> None:
    parquet = fabric_source_support({"type": "parquet", "path": "Files/orders"})
    text = fabric_source_support({"type": "text", "path": "Files/orders.txt"})
    orc = fabric_source_support({"type": "orc", "path": "Files/orders.orc"})
    avro = fabric_source_support({"type": "avro", "path": "Files/orders.avro"})
    xml_file = fabric_source_support({"type": "xml", "path": "Files/orders.xml", "options": {"rowTag": "order"}})
    s3 = fabric_source_support({"type": "s3", "format": "parquet", "path": "s3://bucket/orders"})
    iceberg = fabric_source_support("iceberg_table")
    iceberg_shortcut = fabric_source_support({"type": "iceberg_table", "table": "cf_fabric_iceberg_orders"})
    delta_share = fabric_source_support("delta_share")
    jdbc = fabric_source_support("jdbc")
    rest_api = fabric_source_support({"type": "rest_api", "request": {"url": "https://api.example.com/orders"}})
    azure_blob_bound = fabric_source_support(
        {
            "type": "azure_blob",
            "format": "csv",
            "path": "wasbs://raw@storage.example.com/orders.csv",
        }
    )
    rest_api_auth = fabric_source_support(
        {"type": "rest_api", "request": {"url": "https://api.example.com/orders"}, "auth": {"type": "bearer_token"}}
    )
    rest_api_secret_auth = fabric_source_support(
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "auth": {"type": "bearer_token", "token": "{{ secret:fabric/api-token }}"},
        }
    )
    http_json = fabric_source_support({"type": "http_json", "request": {"url": "https://api.example.com/orders"}})
    unknown = fabric_source_support("made_up")
    catalog = {entry["source_type"]: entry for entry in list_fabric_source_support()}

    assert parquet["status"] == "SUPPORTED"
    assert parquet["renderable"] is True
    assert "OneLake" in parquet["native_mapping"]
    assert text["status"] == "SUPPORTED"
    assert text["renderable"] is True
    assert orc["status"] == "SUPPORTED"
    assert orc["renderable"] is True
    assert avro["status"] == "SUPPORTED"
    assert avro["renderable"] is True
    assert xml_file["status"] == "SUPPORTED"
    assert xml_file["renderable"] is True
    assert s3["status"] == "REVIEW_REQUIRED"
    assert s3["renderable"] is False
    assert iceberg["status"] == "REVIEW_REQUIRED"
    assert iceberg["renderable"] is False
    assert iceberg_shortcut["status"] == "REVIEW_REQUIRED"
    assert iceberg_shortcut["renderable"] is True
    assert "table shortcut" in iceberg_shortcut["native_mapping"]
    assert delta_share["status"] == "REVIEW_REQUIRED"
    assert jdbc["status"] == "REVIEW_REQUIRED"
    assert rest_api["status"] == "SUPPORTED_WITH_WARNINGS"
    assert rest_api["renderable"] is True
    assert azure_blob_bound["status"] == "REVIEW_REQUIRED"
    assert azure_blob_bound["renderable"] is True
    assert "Lakehouse Files" in azure_blob_bound["native_mapping"]
    assert rest_api_auth["status"] == "REVIEW_REQUIRED"
    assert rest_api_auth["renderable"] is False
    assert rest_api_secret_auth["status"] == "REVIEW_REQUIRED"
    assert rest_api_secret_auth["renderable"] is True
    assert "Key Vault" in rest_api_secret_auth["native_mapping"]
    assert http_json["status"] == "SUPPORTED_WITH_WARNINGS"
    assert http_json["renderable"] is True
    assert unknown["status"] == "UNSUPPORTED"
    assert "connection" not in catalog


def test_fabric_plan_contract_returns_runtime_parity_warning() -> None:
    result = plan_fabric_contract(_contract(), environment=_environment())

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert result.plan is not None
    assert result.plan.platform == FABRIC_SUBTARGET_LAKEHOUSE
    assert any(warning.code == "FABRIC_RUNTIME_PARITY_PENDING" for warning in result.warnings)


def test_fabric_render_contract_emits_review_bundle_with_public_aliases() -> None:
    rendered = render_fabric_contract(_contract(), environment=_environment())
    artifacts = rendered.artifacts

    prefix = "workspace_bronze_orders"
    assert f"{prefix}.fabric.review.md" in artifacts
    assert f"{prefix}.fabric.capabilities.json" in artifacts
    assert f"{prefix}.fabric.source_support.json" in artifacts
    assert f"{prefix}.fabric.source_review.json" in artifacts
    assert f"{prefix}.fabric.source_review.md" in artifacts
    assert f"{prefix}.fabric.runtime.todo.md" in artifacts
    assert f"{prefix}.fabric.evidence_ddl.sql" in artifacts
    assert f"{prefix}.fabric.state_ddl.sql" in artifacts
    assert f"{prefix}.fabric.contract.json" in artifacts
    assert f"{prefix}.fabric.notebook.py" in artifacts
    assert f"{prefix}.fabric.notebook.definition.json" in artifacts
    assert f"{prefix}.fabric.manifest.json" in artifacts

    review = artifacts[f"{prefix}.fabric.review.md"]
    assert "Fabric Lakehouse Planning Review" in review
    assert "full bronze-to-gold runtime parity" in review
    assert "`cf-dev`" in review
    assert "`ticomcafe.com.br`" in review
    assert "`contractforge_lh`" in review

    capabilities = json.loads(artifacts[f"{prefix}.fabric.capabilities.json"])
    assert capabilities["runtime"]["tenant_id"] == "3fb3492c-48be-4ac6-ae3a-fec6a63cf4d1"
    assert capabilities["runtime"]["tenant_domain"] == "ticomcafe.com.br"
    assert capabilities["supports"]["historical"] is True
    assert "historical" not in capabilities["review_required_semantics"]
    assert capabilities["supports"]["snapshot_reconcile_soft_delete"] is True
    assert "snapshot_reconcile_soft_delete" not in capabilities["review_required_semantics"]
    assert "scd2_historical" not in capabilities["review_required_semantics"]

    manifest = json.loads(artifacts[f"{prefix}.fabric.manifest.json"])
    assert manifest["artifact_summary"]["deployable"] is False
    assert manifest["artifact_summary"]["execution_model"] == "render_only"
    assert f"{prefix}.fabric.manifest.json" in manifest["artifacts"]
    assert f"{prefix}.fabric.notebook.py" in manifest["artifacts"]
    assert f"{prefix}.fabric.notebook.definition.json" in manifest["artifacts"]

    notebook = artifacts[f"{prefix}.fabric.notebook.py"]
    assert "ContractForge Fabric Lakehouse notebook draft" in notebook
    assert 'spark.read.format("parquet").load("Files/orders")' in notebook
    assert 'df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)' in notebook

    definition = json.loads(artifacts[f"{prefix}.fabric.notebook.definition.json"])
    assert definition["runtime_status"] == "render_only"
    assert definition["deployable"] is False
    request = definition["create_notebook_request"]
    assert request["displayName"] == "cf_workspace_bronze_orders"
    assert request["definition"]["format"] == "fabricGitSource"
    parts = {part["path"]: part for part in request["definition"]["parts"]}
    assert set(parts) == {"notebook-content.py", ".platform"}
    assert parts["notebook-content.py"]["payloadType"] == "InlineBase64"
    decoded_notebook = base64.b64decode(parts["notebook-content.py"]["payload"]).decode("utf-8")
    decoded_platform = base64.b64decode(parts[".platform"]["payload"]).decode("utf-8")
    assert decoded_notebook.startswith("# Fabric notebook source\r\n")
    assert notebook.rstrip() in decoded_notebook
    assert '"type":"Notebook"' in decoded_platform

    source_review = json.loads(artifacts[f"{prefix}.fabric.source_review.json"])
    assert source_review["source_type"] == "parquet"
    assert source_review["status"] == "SUPPORTED"
    assert source_review["renderable"] is True
    assert "graduation_gates" in source_review


def test_fabric_render_contract_emits_notebook_for_public_rest_api_source() -> None:
    contract = {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://example.com/orders"},
            "response": {"records_path": "items"},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]

    assert "workspace_bronze_orders.fabric.notebook.definition.json" in artifacts
    assert "def _cf_rest_dataframe(spark, source):" in notebook
    assert "from contractforge_core.connectors import read_rest_api_records" in notebook
    assert "df = _cf_rest_dataframe(spark, _cf_rest_source)" in notebook
    assert "'records_path': 'items'" in notebook


def test_fabric_render_contract_emits_notebook_for_public_http_json_source() -> None:
    contract = {
        "source": {"type": "http_json", "request": {"url": "https://example.com/orders.json"}},
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]

    assert "def _cf_http_file_dataframe(spark, source):" in notebook
    assert "from contractforge_core.connectors import http_file_format, http_file_reader_options, read_http_file_payload" in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook


def test_fabric_render_contract_emits_notebook_for_authenticated_rest_with_key_vault_placeholder() -> None:
    contract = {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://example.com/orders"},
            "auth": {"type": "bearer_token", "token": "{{ secret:fabric/api-token }}"},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_fabric_contract(contract, environment=_environment_with_key_vault()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]

    assert "workspace_bronze_orders.fabric.notebook.definition.json" in artifacts
    assert "_CF_DEFAULT_KEY_VAULT_URL = \"https://contractforge-default.vault.azure.net/\"" in notebook
    assert '_CF_SECRET_SCOPES = {"fabric": "https://contractforge-fabric.vault.azure.net/"}' in notebook
    assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
    assert "_cf_resolve_secret('fabric', 'api-token')" in notebook
    assert "{{ secret:fabric/api-token }}" not in notebook
    assert "df = _cf_rest_dataframe(spark, _cf_rest_source)" in notebook
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    assert review["source_redacted"]["auth"]["token"] == "***REDACTED***"
    assert "{{ secret:fabric/api-token }}" not in artifacts["workspace_bronze_orders.fabric.source_review.md"]


def test_fabric_render_contract_does_not_emit_notebook_for_raw_authenticated_rest_source() -> None:
    contract = {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://example.com/orders"},
            "auth": {"type": "bearer_token", "token": "raw-token"},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts

    assert "workspace_bronze_orders.fabric.notebook.py" not in artifacts
    assert "workspace_bronze_orders.fabric.notebook.definition.json" not in artifacts
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is False
    assert review["source_redacted"]["auth"]["token"] == "***REDACTED***"
    assert "raw-token" not in artifacts["workspace_bronze_orders.fabric.source_review.md"]


def test_fabric_render_contract_emits_notebook_for_sqlserver_jdbc_with_key_vault_placeholder() -> None:
    contract = {
        "source": {
            "type": "sqlserver",
            "url": "jdbc:sqlserver://cf-sql.database.windows.net:1433;database=contractforge",
            "table": "dbo.orders",
            "auth": {"type": "basic", "username": "cfreader", "password": "{{ secret:fabric/sql-password }}"},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    support = fabric_source_support(contract["source"])
    artifacts = render_fabric_contract(contract, environment=_environment_with_key_vault()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "spark.read.format('jdbc').options(**_cf_jdbc_options).load()" in notebook
    assert "'driver': 'com.microsoft.sqlserver.jdbc.SQLServerDriver'" in notebook
    assert "'password': _cf_resolve_secret('fabric', 'sql-password')" in notebook
    assert "{{ secret:fabric/sql-password }}" not in notebook
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    assert review["source_redacted"]["auth"]["password"] == "***REDACTED***"


def test_fabric_render_contract_blocks_raw_sqlserver_jdbc_password() -> None:
    contract = {
        "source": {
            "type": "sqlserver",
            "url": "jdbc:sqlserver://cf-sql.database.windows.net:1433;database=contractforge",
            "table": "dbo.orders",
            "auth": {"type": "basic", "username": "cfreader", "password": "raw-password"},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts

    assert "workspace_bronze_orders.fabric.notebook.py" not in artifacts
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is False
    assert review["source_redacted"]["auth"]["password"] == "***REDACTED***"


def test_fabric_render_contract_emits_notebook_for_postgres_jdbc_with_key_vault_placeholder() -> None:
    contract = {
        "source": {
            "type": "postgres",
            "url": "{{ secret:fabric/fabric-postgres-jdbc-url }}",
            "table": "contractforge_fabric_f11.orders",
            "auth": {
                "type": "basic",
                "username": "{{ secret:fabric/fabric-postgres-user }}",
                "password": "{{ secret:fabric/fabric-postgres-password }}",
            },
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    support = fabric_source_support(contract["source"])
    artifacts = render_fabric_contract(contract, environment=_environment_with_key_vault()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "spark.read.format('jdbc').options(**_cf_jdbc_options).load()" in notebook
    assert "'driver': 'org.postgresql.Driver'" in notebook
    assert "'url': _cf_resolve_secret('fabric', 'fabric-postgres-jdbc-url')" in notebook
    assert "'user': _cf_resolve_secret('fabric', 'fabric-postgres-user')" in notebook
    assert "'password': _cf_resolve_secret('fabric', 'fabric-postgres-password')" in notebook
    assert "{{ secret:fabric/" not in notebook
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    assert review["source_redacted"]["auth"]["password"] == "***REDACTED***"


def test_fabric_render_contract_emits_notebook_for_bounded_kafka_with_key_vault_placeholder() -> None:
    contract = {
        "source": {
            "type": "kafka_bounded",
            "system": "azure_eventhubs",
            "bootstrap_servers": "cfstream.servicebus.windows.net:9093",
            "topic": "cf-orders",
            "starting_offsets": "earliest",
            "ending_offsets": "latest",
            "options": {
                "kafka.security.protocol": "SASL_SSL",
                "kafka.sasl.mechanism": "PLAIN",
                "kafka.sasl.jaas.config": "{{ secret:fabric/eventhubs-jaas }}",
                "failOnDataLoss": "false",
            },
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    support = fabric_source_support(contract["source"])
    artifacts = render_fabric_contract(contract, environment=_environment_with_key_vault()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "Event Hubs Kafka-compatible bounded replay" in support["native_mapping"]
    assert "spark.read" in notebook
    assert ".format('kafka')" in notebook
    assert ".option('kafka.bootstrap.servers', 'cfstream.servicebus.windows.net:9093')" in notebook
    assert ".option('subscribe', 'cf-orders')" in notebook
    assert ".option('startingOffsets', 'earliest')" in notebook
    assert ".option('endingOffsets', 'latest')" in notebook
    assert "_cf_resolve_secret('fabric', 'eventhubs-jaas')" in notebook
    assert "{{ secret:fabric/eventhubs-jaas }}" not in notebook
    assert review["source_redacted"]["options"]["kafka.sasl.jaas.config"] == "***REDACTED***"


def test_fabric_render_contract_emits_notebook_for_available_now_kafka_with_key_vault_placeholder() -> None:
    contract = {
        "source": {
            "type": "kafka_available_now",
            "system": "confluent_cloud",
            "bootstrap_servers": "pkc.example.confluent.cloud:9092",
            "topic": "cf-orders",
            "starting_offsets": "earliest",
            "checkpoint_location": "Files/checkpoints/cf-orders-available-now",
            "options": {
                "kafka.security.protocol": "SASL_SSL",
                "kafka.sasl.mechanism": "PLAIN",
                "kafka.sasl.jaas.config": "{{ secret:fabric/confluent-jaas }}",
                "failOnDataLoss": "false",
            },
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    support = fabric_source_support(contract["source"])
    artifacts = render_fabric_contract(contract, environment=_environment_with_key_vault()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "Kafka available-now" in support["native_mapping"]
    assert "spark.readStream" in notebook
    assert ".format('kafka')" in notebook
    assert ".option('checkpointLocation', _cf_available_now_checkpoint)" in notebook
    assert ".option('path', _cf_available_now_materialized_path)" in notebook
    assert ".trigger(availableNow=True)" in notebook
    assert ".awaitTermination()" in notebook
    assert "spark.read.format('delta').load(_cf_available_now_materialized_path)" in notebook
    assert "_cf_resolve_secret('fabric', 'confluent-jaas')" in notebook
    assert "{{ secret:fabric/confluent-jaas }}" not in notebook
    assert review["source_redacted"]["options"]["kafka.sasl.jaas.config"] == "***REDACTED***"


def test_fabric_render_contract_blocks_unbounded_kafka() -> None:
    contract = {
        "source": {
            "type": "kafka_bounded",
            "bootstrap_servers": "broker:9092",
            "topic": "orders",
            "starting_offsets": "earliest",
            "options": {
                "kafka.security.protocol": "SASL_SSL",
                "kafka.sasl.mechanism": "PLAIN",
                "kafka.sasl.jaas.config": "{{ secret:fabric/eventhubs-jaas }}",
            },
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_fabric_contract(contract, environment=_environment_with_key_vault()).artifacts
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])

    assert "workspace_bronze_orders.fabric.notebook.py" not in artifacts
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is False


def test_fabric_render_contract_emits_notebook_for_object_storage_with_fabric_runtime_path() -> None:
    contract = {
        "source": {
            "type": "azure_blob",
            "format": "csv",
            "path": "https://cffabricf11storage.blob.core.windows.net/raw/orders.csv",
            "options": {"header": True, "inferSchema": True},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "extensions": {"fabric": {"source_runtime_path": "Files/shortcuts/blob/orders.csv"}},
    }

    support = fabric_source_support({**contract["source"], "path": contract["extensions"]["fabric"]["source_runtime_path"]})
    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert 'spark.read.format("csv").option("header", "True").option("inferSchema", "True").load("Files/shortcuts/blob/orders.csv")' in notebook
    assert '.load("https://cffabricf11storage.blob.core.windows.net/raw/orders.csv")' not in notebook
    assert review["renderable"] is True
    assert review["runtime_path"] == "Fabric notebook read from `Files/shortcuts/blob/orders.csv`"


def test_fabric_render_contract_emits_notebook_for_iceberg_table_shortcut() -> None:
    contract = {
        "source": {"type": "iceberg_table", "table": "cf_fabric_iceberg_orders"},
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    support = fabric_source_support(contract["source"])
    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "Fabric Lakehouse table shortcut virtualized from Iceberg" in support["native_mapping"]
    assert 'df = spark.table("cf_fabric_iceberg_orders")' in notebook
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True


def test_fabric_render_contract_emits_private_azure_blob_key_vault_setup() -> None:
    contract = {
        "source": {
            "type": "azure_blob",
            "format": "csv",
            "path": "https://privateblob.blob.core.windows.net/raw/orders.csv",
            "options": {"header": True, "inferSchema": True},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "extensions": {
            "fabric": {
                "source_runtime_path": "wasbs://raw@privateblob.blob.core.windows.net/orders.csv",
                "storage_account_key_secret": "{{ secret:fabric/private-blob-storage-key }}",
            }
        },
    }

    artifacts = render_fabric_contract(contract, environment=_environment_with_key_vault()).artifacts
    notebook = artifacts["workspace_bronze_orders.fabric.notebook.py"]
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])

    assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
    assert "_cf_resolve_secret('fabric', 'private-blob-storage-key')" in notebook
    assert "spark.conf.set('fs.azure.account.key.privateblob.blob.core.windows.net'" in notebook
    assert "{{ secret:fabric/private-blob-storage-key }}" not in notebook
    assert 'load("wasbs://raw@privateblob.blob.core.windows.net/orders.csv")' in notebook
    assert review["source_redacted"]["extensions"]["fabric"]["storage_account_key_secret"] == "***REDACTED***"


def test_fabric_environment_parses_key_vault_secret_bindings() -> None:
    environment = FabricEnvironment.from_contract(_environment_with_key_vault())

    assert environment.secret_vault_url == "https://contractforge-default.vault.azure.net/"
    assert environment.secret_scopes == {"fabric": "https://contractforge-fabric.vault.azure.net/"}


def test_fabric_secret_placeholder_renders_runtime_lookup() -> None:
    expression = render_secret_aware_literal("Bearer {{ secret:fabric/api-token }}")
    helper = render_secret_resolver_helper(FabricEnvironment.from_contract(_environment_with_key_vault()))

    assert expression == "'Bearer ' + _cf_resolve_secret('fabric', 'api-token')"
    assert "{{ secret:fabric/api-token }}" not in expression
    assert "notebookutils.credentials.getSecret(vault_url, key)" in helper


def test_fabric_source_review_captures_review_only_object_storage_prerequisites() -> None:
    contract = {
        "source": {
            "type": "s3",
            "format": "parquet",
            "path": "s3://example-private/orders",
            "auth": {"access_key_id": "AKIA_TEST", "secret_access_key": "{{ secret:aws/orders-secret }}"},
        },
        "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts
    review = json.loads(artifacts["workspace_bronze_orders.fabric.source_review.json"])

    assert "workspace_bronze_orders.fabric.notebook.py" not in artifacts
    assert review["source_type"] == "s3"
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is False
    assert review["source_redacted"]["auth"]["secret_access_key"] == "***REDACTED***"
    assert "OneLake shortcut" in review["runtime_path"]
    assert any("shortcut" in item for item in review["review_prerequisites"])
    assert any("real Fabric smoke or parity test fixture" in item for item in review["graduation_gates"])

    payload = fabric_source_review_payload(contract["source"])
    assert payload["source_redacted"]["auth"]["secret_access_key"] == "***REDACTED***"


def test_fabric_render_contract_emits_upsert_notebook_merge() -> None:
    contract = {
        "source": {"type": "sql", "query": "SELECT 1 AS id, 'alpha' AS name"},
        "target": {"catalog": "workspace", "schema": "silver", "table": "orders"},
        "mode": "upsert",
        "merge_keys": ["id"],
    }

    artifacts = render_fabric_contract(contract, environment=_environment()).artifacts
    notebook = artifacts["workspace_silver_orders.fabric.notebook.py"]

    assert "df = spark.sql(\"SELECT 1 AS id, 'alpha' AS name\")" in notebook
    assert 'MERGE_KEYS = ["id"]' in notebook
    assert "missing_merge_keys = [key for key in MERGE_KEYS if key not in df.columns]" in notebook
    assert "duplicate_merge_keys = (" in notebook
    assert "MERGE INTO {TARGET_TABLE} AS target" in notebook
    assert "WHEN MATCHED THEN UPDATE SET {assignments}" in notebook
    assert "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})" in notebook
    assert "NotImplementedError" not in notebook


def test_fabric_render_contract_emits_evidence_ddl_from_environment() -> None:
    artifacts = render_fabric_contract(_contract(), environment=_environment()).artifacts

    evidence_sql = artifacts["workspace_bronze_orders.fabric.evidence_ddl.sql"]
    state_sql = artifacts["workspace_bronze_orders.fabric.state_ddl.sql"]
    assert "CREATE SCHEMA IF NOT EXISTS `contractforge`;" in evidence_sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_runs`" in evidence_sql
    assert "USING DELTA PARTITIONED BY (`run_date`);" in evidence_sql
    assert "CREATE TABLE IF NOT EXISTS `contractforge`.`ctrl_ingestion_state`" in state_sql


def test_fabric_adapter_rejects_unsupported_source() -> None:
    contract = {
        "source": {"type": "made_up"},
        "target": {"schema": "bronze", "table": "orders"},
        "mode": "append",
    }

    result = plan_fabric_contract(contract)

    assert result.status == "UNSUPPORTED"
    assert result.plan is None
    assert [blocker.code for blocker in result.blockers] == ["FABRIC_UNSUPPORTED_SOURCE"]


def test_fabric_public_api_and_cli_are_importable(capsys) -> None:
    adapter = FabricAdapter.lakehouse()

    assert adapter.name == FABRIC_SUBTARGET_LAKEHOUSE
    assert FABRIC_RESOURCE == "https://api.fabric.microsoft.com"
    assert AzureCliFabricTokenProvider(tenant_id="tenant-1").tenant_id == "tenant-1"
    assert fabric_cli(["sources"]) == 0
    assert "parquet" in capsys.readouterr().out
