from __future__ import annotations

import json
import os
from subprocess import CompletedProcess

from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.cli import main as gcp_cli
from contractforge_gcp.evidence import render_run_evidence_insert_sql
from contractforge_gcp.runtime import BqCliBigQueryClient, BigQueryJobEvidence, bigquery_job_evidence_from_resource, split_bigquery_script
from contractforge_gcp.smoke import run_gcp_contract_smoke, run_gcp_project_smoke
from contractforge_core.contracts import semantic_contract_from_mapping


class FakeBigQueryClient:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.loads: list[dict[str, object]] = []
        self.local_loads: list[tuple[str, dict[str, object]]] = []
        self._job = 0

    def query(self, sql: str) -> BigQueryJobEvidence:
        self._job += 1
        self.queries.append(sql)
        return BigQueryJobEvidence(
            job_id=f"query-{self._job}",
            job_type="QUERY",
            state="DONE",
            statement_type="SELECT",
            total_bytes_processed=10,
            total_bytes_billed=10,
            total_slot_ms=20,
        )

    def load_table_from_uri(self, load_job_config: dict[str, object]) -> BigQueryJobEvidence:
        self._job += 1
        self.loads.append(load_job_config)
        return BigQueryJobEvidence(
            job_id=f"load-{self._job}",
            job_type="LOAD",
            state="DONE",
            output_rows=3,
        )

    def load_table_from_file(self, path: str, load_job_config: dict[str, object]) -> BigQueryJobEvidence:
        self._job += 1
        self.local_loads.append((path, load_job_config))
        return BigQueryJobEvidence(
            job_id=f"load-file-{self._job}",
            job_type="LOAD",
            state="DONE",
            output_rows=3,
        )


def _environment() -> dict[str, object]:
    return {
        "parameters": {"gcp": {"project_id": "test-project", "location": "US", "dataset": "bronze"}},
        "evidence": {"dataset": "contractforge_ops"},
    }


def _table_contract() -> dict[str, object]:
    return {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
        "quality_rules": {"not_null": ["order_id"]},
    }


def _gcs_contract() -> dict[str, object]:
    return {
        "source": {"type": "gcs", "format": "csv", "path": "gs://bucket/orders.csv"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
    }


def _governed_gcs_contract() -> dict[str, object]:
    contract = _gcs_contract()
    contract["access"] = {
        "row_filters": [
            {
                "name": "paid_only",
                "function": "status = 'paid'",
                "columns": ["status"],
                "applies_to": {"principals": ["group:analysts@example.com"]},
            }
        ]
    }
    contract["annotations"] = {"table": {"description": "Orders table", "tags": {"domain": "sales"}}}
    return contract


def _rest_contract() -> dict[str, object]:
    return {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "response": {"records_path": "items"},
            "read": {
                "columns": [
                    {"name": "order_id", "type": "STRING"},
                    {"name": "amount", "type": "FLOAT64"},
                ]
            },
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "overwrite",
    }


def _authenticated_rest_contract() -> dict[str, object]:
    contract = _rest_contract()
    source = dict(contract["source"])  # type: ignore[index]
    source["auth"] = {"type": "bearer_token", "token": "{{ secret:gcp/api-token }}"}
    contract["source"] = source
    return contract


def _authenticated_variant_contract(source_type: str, auth: dict[str, object]) -> dict[str, object]:
    request_url = "https://postman-echo.com/headers"
    if source_type == "rest_api":
        return {
            "source": {
                "type": "rest_api",
                "request": {"url": request_url},
                "response": {"records_path": "headers"},
                "read": {"columns": [{"name": "header_value", "type": "STRING"}]},
                "auth": auth,
            },
            "target": {"catalog": "test-project", "schema": "bronze", "table": "auth_headers"},
            "mode": "overwrite",
        }
    return {
        "source": {
            "type": source_type,
            "request": {"url": request_url},
            "response": {"format": "text"} if source_type == "http_text" else {"format": "json"},
            "read": {"columns": [{"name": "header_value", "type": "STRING"}]},
            "auth": auth,
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "auth_headers"},
        "mode": "overwrite",
    }


def _http_text_contract() -> dict[str, object]:
    return {
        "source": {
            "type": "http_text",
            "request": {"url": "https://example.com/orders.txt"},
            "read": {"columns": [{"name": "line_text", "type": "STRING"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "text_orders"},
        "mode": "overwrite",
    }


def _http_file_text_contract() -> dict[str, object]:
    return {
        "source": {
            "type": "http_file",
            "format": "text",
            "request": {"url": "https://example.com/orders.txt"},
            "response": {"raw_column": "payload_line"},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_file_text_orders"},
        "mode": "overwrite",
    }


def _http_json_records_path_contract() -> dict[str, object]:
    return {
        "source": {
            "type": "http_json",
            "request": {"url": "https://example.com/headers.json"},
            "response": {"records_path": "headers.x-api-key"},
            "read": {"columns": [{"name": "value", "type": "STRING"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_json_header"},
        "mode": "overwrite",
    }


def _http_file_json_records_path_contract() -> dict[str, object]:
    return {
        "source": {
            "type": "http_file",
            "format": "json",
            "request": {"url": "https://example.com/items.json"},
            "response": {"records_path": "items"},
            "read": {
                "columns": [
                    {"name": "id", "type": "INT64"},
                    {"name": "name", "type": "STRING"},
                ]
            },
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_file_json_items"},
        "mode": "overwrite",
    }


def _http_file_parquet_contract() -> dict[str, object]:
    return {
        "source": {
            "type": "http_file",
            "format": "parquet",
            "request": {"url": "https://example.com/orders.parquet"},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "http_file_parquet_orders"},
        "mode": "overwrite",
    }


def _write_gcp_project(tmp_path) -> tuple[object, object]:
    project_path = tmp_path / "project.yaml"
    environment_path = tmp_path / "gcp.env.yaml"
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    environment_path.write_text(
        """
parameters:
  gcp:
    project_id: test-project
    location: US
    dataset: bronze
evidence:
  dataset: contractforge_ops
""".strip(),
        encoding="utf-8",
    )
    (contracts / "01_bronze.ingestion.yaml").write_text(
        """
source:
  type: gcs
  format: csv
  path: gs://bucket/orders.csv
target:
  catalog: test-project
  schema: bronze
  table: orders
mode: append
""".strip(),
        encoding="utf-8",
    )
    (contracts / "02_silver.ingestion.yaml").write_text(
        """
source:
  type: table
  table: test-project.bronze.orders
target:
  catalog: test-project
  schema: silver
  table: orders
mode: overwrite
quality_rules:
  not_null:
    - order_id
""".strip(),
        encoding="utf-8",
    )
    project_path.write_text(
        """
name: gcp-smoke-project
environments:
  gcp: gcp.env.yaml
execution_order:
  - name: bronze_orders
    layer: bronze
    contracts:
      gcp: contracts/01_bronze.ingestion.yaml
  - name: silver_orders
    layer: silver
    depends_on:
      - bronze_orders
    contracts:
      gcp: contracts/02_silver.ingestion.yaml
""".strip(),
        encoding="utf-8",
    )
    return project_path, environment_path


def test_gcp_smoke_dry_run_plans_load_without_execution() -> None:
    result = run_gcp_contract_smoke(_gcs_contract(), _environment())

    assert result.status == "DRY_RUN"
    assert result.ok is True
    assert result.executed is False
    assert [operation.name for operation in result.operations] == ["prepare_evidence", "load_source"]
    assert all(operation.executed is False for operation in result.operations)
    assert any(name.endswith(".gcp.load_job.json") for name in result.artifacts)


def test_gcp_smoke_execute_runs_evidence_load_and_reports_jobs() -> None:
    client = FakeBigQueryClient()
    result = run_gcp_contract_smoke(_gcs_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert result.executed is True
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "load_source",
        "persist_run_evidence",
        "persist_lineage_evidence",
    ]
    assert len(client.queries) == 10  # schema DDL plus seven evidence tables, run evidence and lineage evidence
    assert len(client.loads) == 1
    assert client.loads[0]["source_uris"] == ["gs://bucket/orders.csv"]
    assert [operation.job.job_id for operation in result.operations if operation.job] == [
        "query-8",
        "load-9",
        "query-10",
        "query-11",
    ]
    assert any("contractforge_annotation_evidence" in query for query in client.queries)
    assert any("contractforge_governance_evidence" in query for query in client.queries)
    assert any("INSERT INTO `test-project.contractforge_ops.contractforge_run_evidence`" in query for query in client.queries)
    assert "INSERT INTO `test-project.contractforge_ops.contractforge_lineage_evidence`" in client.queries[-1]
    assert "test-project.bronze.orders" in client.queries[-1]


def test_gcp_smoke_execute_persists_governance_evidence_for_governed_contract() -> None:
    client = FakeBigQueryClient()

    result = run_gcp_contract_smoke(
        _governed_gcs_contract(),
        _environment(),
        client=client,
        execute=True,
        allow_review_required=True,
    )

    assert result.status == "SUCCEEDED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "load_source",
        "persist_run_evidence",
        "persist_lineage_evidence",
        "persist_governance_evidence",
    ]
    governance_sql = next(
        query for query in client.queries if "contractforge_governance_evidence" in query and "INSERT INTO" in query
    )
    assert "'bigquery_row_access_policy'" in governance_sql
    assert "'knowledge_catalog_or_dataplex_aspect'" in governance_sql
    assert "group:REDACTED_EMAIL" in governance_sql
    assert "analysts@example.com" not in governance_sql


def test_gcp_smoke_execute_materializes_public_rest_source(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    monkeypatch.setattr(
        smoke_workflow,
        "read_rest_api_records",
        lambda source: [{"order_id": "1", "amount": 10.0}, {"order_id": "2", "amount": 20.0}],
    )
    client = FakeBigQueryClient()

    result = run_gcp_contract_smoke(_rest_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "materialize_source",
        "persist_run_evidence",
        "persist_lineage_evidence",
    ]
    assert client.loads == []
    assert len(client.local_loads) == 1
    local_path, load_config = client.local_loads[0]
    assert not os.path.exists(local_path)
    assert load_config["destination_table"] == "test-project.bronze.orders"
    assert load_config["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert load_config["write_disposition"] == "WRITE_TRUNCATE"
    assert load_config["schema_fields"] == [
        {"name": "order_id", "type": "STRING"},
        {"name": "amount", "type": "FLOAT64"},
    ]
    assert any("contractforge_run_evidence" in query for query in client.queries)
    assert any("contractforge_lineage_evidence" in query for query in client.queries)


def test_gcp_smoke_execute_materializes_authenticated_rest_source_with_secret_manager(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    commands: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        commands.append(command)
        return CompletedProcess(command, 0, stdout="resolved-token\n", stderr="")

    def fake_reader(source):
        assert source["auth"]["token"] == "resolved-token"
        return [{"order_id": "1", "amount": 10.0}]

    monkeypatch.setattr("contractforge_gcp.security.runtime.shutil.which", lambda name: "C:\\CloudSDK\\gcloud.cmd")
    monkeypatch.setattr("contractforge_gcp.security.runtime.subprocess.run", fake_run)
    monkeypatch.setattr(smoke_workflow, "read_rest_api_records", fake_reader)
    client = FakeBigQueryClient()

    result = run_gcp_contract_smoke(_authenticated_rest_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert result.planning_status == "SUPPORTED_WITH_WARNINGS"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "materialize_source",
        "persist_run_evidence",
        "persist_lineage_evidence",
    ]
    assert commands == [
        [
            "C:\\CloudSDK\\gcloud.cmd",
            "secrets",
            "versions",
            "access",
            "latest",
            "--secret=gcp-api-token",
            "--project=test-project",
        ]
    ]
    assert len(client.local_loads) == 1


def test_gcp_smoke_resolves_secret_manager_auth_variants_before_core_reader(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    commands: list[list[str]] = []
    seen_sources: list[dict[str, object]] = []

    variants = [
        (
            "rest_api",
            {"type": "api_key", "header": "X-Api-Key", "value": "{{ secret:gcp/rest-api-key }}"},
            "read_rest_api_records",
            "gcp-rest-api-key",
        ),
        (
            "http_json",
            {"type": "bearer_token", "token": "{{ secret:gcp/http-bearer-token }}"},
            "read_http_file_payload",
            "gcp-http-bearer-token",
        ),
        (
            "http_json",
            {"type": "api_key", "header": "X-Api-Key", "value": "{{ secret:gcp/http-api-key }}"},
            "read_http_file_payload",
            "gcp-http-api-key",
        ),
        (
            "http_text",
            {"type": "bearer_token", "token": "{{ secret:gcp/http-text-bearer-token }}"},
            "read_http_file_payload",
            "gcp-http-text-bearer-token",
        ),
        (
            "http_text",
            {"type": "api_key", "header": "X-Api-Key", "value": "{{ secret:gcp/http-text-api-key }}"},
            "read_http_file_payload",
            "gcp-http-text-api-key",
        ),
    ]

    def fake_run(command, check, capture_output, text):
        commands.append(command)
        return CompletedProcess(command, 0, stdout="resolved-secret\n", stderr="")

    def fake_rest_reader(source):
        seen_sources.append(source)
        assert source["auth"]["value"] == "resolved-secret"
        assert source["auth"]["header"] == "X-Api-Key"
        return [{"header_value": "resolved-secret"}]

    def fake_http_reader(source):
        seen_sources.append(source)
        auth = source["auth"]
        if auth["type"] == "bearer_token":
            assert auth["token"] == "resolved-secret"
        else:
            assert auth["value"] == "resolved-secret"
            assert auth["header"] == "X-Api-Key"
        if source["type"] == "http_text":
            return b"resolved-secret\n"
        return b'{"header_value":"resolved-secret"}'

    monkeypatch.setattr("contractforge_gcp.security.runtime.shutil.which", lambda name: "C:\\CloudSDK\\gcloud.cmd")
    monkeypatch.setattr("contractforge_gcp.security.runtime.subprocess.run", fake_run)
    monkeypatch.setattr(smoke_workflow, "read_rest_api_records", fake_rest_reader)
    monkeypatch.setattr(smoke_workflow, "read_http_file_payload", fake_http_reader)

    for source_type, auth, _reader, expected_secret in variants:
        client = FakeBigQueryClient()
        result = run_gcp_contract_smoke(
            _authenticated_variant_contract(source_type, auth),
            _environment(),
            client=client,
            execute=True,
        )

        assert result.status == "SUCCEEDED"
        assert result.planning_status == "SUPPORTED_WITH_WARNINGS"
        assert [operation.name for operation in result.operations] == [
            "prepare_evidence",
            "materialize_source",
            "persist_run_evidence",
            "persist_lineage_evidence",
        ]
        assert len(client.local_loads) == 1
        assert commands[-1] == [
            "C:\\CloudSDK\\gcloud.cmd",
            "secrets",
            "versions",
            "access",
            "latest",
            f"--secret={expected_secret}",
            "--project=test-project",
        ]

    assert [source["type"] for source in seen_sources] == [
        "rest_api",
        "http_json",
        "http_json",
        "http_text",
        "http_text",
    ]


def test_gcp_smoke_execute_materializes_http_text_source(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    seen_sources: list[dict[str, object]] = []
    materialized_payloads: list[list[dict[str, str]]] = []

    class InspectingBigQueryClient(FakeBigQueryClient):
        def load_table_from_file(self, path: str, load_job_config: dict[str, object]) -> BigQueryJobEvidence:
            with open(path, encoding="utf-8") as handle:
                materialized_payloads.append([json.loads(line) for line in handle if line.strip()])
            return super().load_table_from_file(path, load_job_config)

    def fake_http_reader(source):
        seen_sources.append(source)
        return b"first line\nsecond line\n"

    monkeypatch.setattr(smoke_workflow, "read_http_file_payload", fake_http_reader)
    client = InspectingBigQueryClient()

    result = run_gcp_contract_smoke(_http_text_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert result.planning_status == "SUPPORTED_WITH_WARNINGS"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "materialize_source",
        "persist_run_evidence",
        "persist_lineage_evidence",
    ]
    assert len(seen_sources) == 1
    assert seen_sources[0]["type"] == "http_text"
    assert seen_sources[0]["request"] == {"url": "https://example.com/orders.txt"}
    assert seen_sources[0]["read"] == {"columns": [{"name": "line_text", "type": "STRING"}]}
    assert client.loads == []
    assert len(client.local_loads) == 1
    local_path, load_config = client.local_loads[0]
    assert not os.path.exists(local_path)
    assert load_config["destination_table"] == "test-project.bronze.text_orders"
    assert load_config["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert load_config["schema_fields"] == [{"name": "line_text", "type": "STRING"}]
    assert "autodetect" not in load_config
    assert materialized_payloads == [[{"line_text": "first line"}, {"line_text": "second line"}]]


def test_gcp_smoke_execute_materializes_generic_http_file_text_source(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    materialized_payloads: list[list[dict[str, str]]] = []

    class InspectingBigQueryClient(FakeBigQueryClient):
        def load_table_from_file(self, path: str, load_job_config: dict[str, object]) -> BigQueryJobEvidence:
            with open(path, encoding="utf-8") as handle:
                materialized_payloads.append([json.loads(line) for line in handle if line.strip()])
            return super().load_table_from_file(path, load_job_config)

    monkeypatch.setattr(smoke_workflow, "read_http_file_payload", lambda source: b"alpha\nbeta\n")
    client = InspectingBigQueryClient()

    result = run_gcp_contract_smoke(_http_file_text_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert result.planning_status == "SUPPORTED_WITH_WARNINGS"
    assert len(client.local_loads) == 1
    _local_path, load_config = client.local_loads[0]
    assert load_config["destination_table"] == "test-project.bronze.http_file_text_orders"
    assert load_config["source_format"] == "NEWLINE_DELIMITED_JSON"
    assert load_config["schema_fields"] == [{"name": "payload_line", "type": "STRING"}]
    assert materialized_payloads == [[{"payload_line": "alpha"}, {"payload_line": "beta"}]]


def test_gcp_smoke_execute_materializes_http_json_records_path(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    materialized_payloads: list[list[dict[str, str]]] = []

    class InspectingBigQueryClient(FakeBigQueryClient):
        def load_table_from_file(self, path: str, load_job_config: dict[str, object]) -> BigQueryJobEvidence:
            with open(path, encoding="utf-8") as handle:
                materialized_payloads.append([json.loads(line) for line in handle if line.strip()])
            return super().load_table_from_file(path, load_job_config)

    monkeypatch.setattr(
        smoke_workflow,
        "read_http_file_payload",
        lambda source: b'{"headers":{"x-api-key":"resolved-secret","host":"example.com"}}',
    )
    client = InspectingBigQueryClient()

    result = run_gcp_contract_smoke(_http_json_records_path_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert len(client.local_loads) == 1
    _local_path, load_config = client.local_loads[0]
    assert load_config["destination_table"] == "test-project.bronze.http_json_header"
    assert load_config["schema_fields"] == [{"name": "value", "type": "STRING"}]
    assert materialized_payloads == [[{"value": "resolved-secret"}]]


def test_gcp_smoke_execute_materializes_generic_http_file_json_records_path(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    materialized_payloads: list[list[dict[str, object]]] = []

    class InspectingBigQueryClient(FakeBigQueryClient):
        def load_table_from_file(self, path: str, load_job_config: dict[str, object]) -> BigQueryJobEvidence:
            with open(path, encoding="utf-8") as handle:
                materialized_payloads.append([json.loads(line) for line in handle if line.strip()])
            return super().load_table_from_file(path, load_job_config)

    monkeypatch.setattr(
        smoke_workflow,
        "read_http_file_payload",
        lambda source: b'{"items":[{"id":1,"name":"alpha"},{"id":2,"name":"beta"}]}',
    )
    client = InspectingBigQueryClient()

    result = run_gcp_contract_smoke(
        _http_file_json_records_path_contract(),
        _environment(),
        client=client,
        execute=True,
    )

    assert result.status == "SUCCEEDED"
    assert len(client.local_loads) == 1
    _local_path, load_config = client.local_loads[0]
    assert load_config["destination_table"] == "test-project.bronze.http_file_json_items"
    assert load_config["schema_fields"] == [{"name": "id", "type": "INT64"}, {"name": "name", "type": "STRING"}]
    assert materialized_payloads == [[{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]]


def test_gcp_smoke_execute_materializes_generic_http_file_binary_source(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    observed_payloads: list[bytes] = []

    class InspectingBigQueryClient(FakeBigQueryClient):
        def load_table_from_file(self, path: str, load_job_config: dict[str, object]) -> BigQueryJobEvidence:
            with open(path, "rb") as handle:
                observed_payloads.append(handle.read())
            assert path.endswith(".parquet")
            return super().load_table_from_file(path, load_job_config)

    monkeypatch.setattr(smoke_workflow, "read_http_file_payload", lambda source: b"PAR1binary-parquet-fixture")
    client = InspectingBigQueryClient()

    result = run_gcp_contract_smoke(_http_file_parquet_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert result.planning_status == "SUPPORTED_WITH_WARNINGS"
    assert len(client.local_loads) == 1
    _local_path, load_config = client.local_loads[0]
    assert load_config["destination_table"] == "test-project.bronze.http_file_parquet_orders"
    assert load_config["source_format"] == "PARQUET"
    assert observed_payloads == [b"PAR1binary-parquet-fixture"]


def test_gcp_smoke_execute_runs_write_and_quality_for_table_source() -> None:
    client = FakeBigQueryClient()
    result = run_gcp_contract_smoke(_table_contract(), _environment(), client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "write_target",
        "persist_run_evidence",
        "persist_lineage_evidence",
        "quality",
        "persist_quality_evidence",
    ]
    assert len(client.loads) == 0
    assert any("CREATE OR REPLACE TABLE `test-project.bronze.orders` AS" in query for query in client.queries)
    assert any("WHERE `order_id` IS NULL" in query for query in client.queries)
    assert any("contractforge_lineage_evidence" in query for query in client.queries)
    assert any("INSERT INTO `test-project.contractforge_ops.contractforge_quality_evidence`" in query for query in client.queries)


def test_gcp_smoke_execute_can_enforce_additive_schema_policy() -> None:
    class SchemaPolicyClient(FakeBigQueryClient):
        def query(self, sql: str) -> BigQueryJobEvidence:
            evidence = super().query(sql)
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.raw.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "status", "data_type": "STRING"},
                        {"column_name": "amount", "data_type": "FLOAT64"},
                    ],
                )
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.bronze.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "status", "data_type": "STRING"},
                    ],
                )
            return evidence

    contract = {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "schema_policy": "additive_only",
    }
    client = SchemaPolicyClient()

    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, enforce_schema_policy=True)

    assert result.status == "SUCCEEDED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "schema_policy",
        "persist_schema_evidence",
        "write_target",
        "persist_run_evidence",
        "persist_lineage_evidence",
    ]
    assert any("ALTER TABLE `test-project.bronze.orders` ADD COLUMN `amount` FLOAT64" in query for query in client.queries)
    assert any("INSERT INTO `test-project.contractforge_ops.contractforge_schema_evidence`" in query for query in client.queries)
    schema_job = next(operation.job for operation in result.operations if operation.name == "schema_policy")
    schema_policy = schema_job.raw["schema_policy"]
    assert schema_policy["commands"] == ("ALTER TABLE `test-project.bronze.orders` ADD COLUMN `amount` FLOAT64",)
    assert schema_policy["schema_changes"]["added_columns"][0]["applied"] is True


def test_gcp_smoke_schema_policy_blocks_strict_schema_drift() -> None:
    class DriftClient(FakeBigQueryClient):
        def query(self, sql: str) -> BigQueryJobEvidence:
            evidence = super().query(sql)
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.raw.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "status", "data_type": "STRING"},
                    ],
                )
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.bronze.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[{"column_name": "order_id", "data_type": "STRING"}],
                )
            return evidence

    contract = {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "schema_policy": "strict",
    }

    client = DriftClient()
    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, enforce_schema_policy=True)

    assert result.status == "FAILED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "schema_policy",
        "persist_schema_evidence",
    ]
    assert any("INSERT INTO `test-project.contractforge_ops.contractforge_schema_evidence`" in query for query in client.queries)
    schema_job = next(operation.job for operation in result.operations if operation.name == "schema_policy")
    assert "Schema policy strict violation" in schema_job.error_message
    assert schema_job.raw["schema_policy"]["schema_changes"]["added_columns"][0]["column"] == "status"


def test_gcp_smoke_schema_policy_applies_nullable_additions_for_permissive_policy() -> None:
    class SchemaPolicyClient(FakeBigQueryClient):
        def query(self, sql: str) -> BigQueryJobEvidence:
            evidence = super().query(sql)
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.raw.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "status", "data_type": "STRING"},
                        {"column_name": "amount", "data_type": "FLOAT64"},
                    ],
                )
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.bronze.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "status", "data_type": "STRING"},
                    ],
                )
            return evidence

    contract = {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "schema_policy": "permissive",
    }
    client = SchemaPolicyClient()

    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, enforce_schema_policy=True)

    assert result.status == "SUCCEEDED"
    assert any("ALTER TABLE `test-project.bronze.orders` ADD COLUMN `amount` FLOAT64" in query for query in client.queries)


def test_gcp_smoke_schema_policy_records_permissive_type_change_violation() -> None:
    class TypeChangeClient(FakeBigQueryClient):
        def query(self, sql: str) -> BigQueryJobEvidence:
            evidence = super().query(sql)
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.raw.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "amount", "data_type": "STRING"},
                    ],
                )
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.bronze.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "amount", "data_type": "FLOAT64"},
                    ],
                )
            return evidence

    contract = {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "schema_policy": "permissive",
    }
    client = TypeChangeClient()

    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, enforce_schema_policy=True)

    assert result.status == "FAILED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "schema_policy",
        "persist_schema_evidence",
    ]
    assert any("INSERT INTO `test-project.contractforge_ops.contractforge_schema_evidence`" in query for query in client.queries)
    schema_job = next(operation.job for operation in result.operations if operation.name == "schema_policy")
    assert "permissive does not apply potentially destructive type changes" in schema_job.error_message
    type_change = schema_job.raw["schema_policy"]["schema_changes"]["type_changes"][0]
    assert type_change["column"] == "amount"
    assert type_change["source"] == "STRING"
    assert type_change["target"] == "FLOAT64"
    assert type_change["applied"] is False


def test_gcp_smoke_schema_policy_inspects_sql_source_schema() -> None:
    class SQLSchemaClient(FakeBigQueryClient):
        def query(self, sql: str) -> BigQueryJobEvidence:
            evidence = super().query(sql)
            if sql.startswith("CREATE OR REPLACE TABLE") and "contractforge_schema_source" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                )
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.contractforge_ops.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "status", "data_type": "STRING"},
                    ],
                )
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.bronze.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[{"column_name": "order_id", "data_type": "STRING"}],
                )
            return evidence

    contract = {
        "source": {"type": "sql", "query": "SELECT '1' AS order_id, 'paid' AS status"},
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "schema_policy": "permissive",
    }
    client = SQLSchemaClient()

    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, enforce_schema_policy=True)

    assert result.status == "SUCCEEDED"
    assert any("AS contractforge_schema_source" in query for query in client.queries)
    assert any("DROP TABLE IF EXISTS `test-project.contractforge_ops.cf_schema_probe_" in query for query in client.queries)
    assert any("ALTER TABLE `test-project.bronze.orders` ADD COLUMN `status` STRING" in query for query in client.queries)
    schema_job = next(operation.job for operation in result.operations if operation.name == "schema_policy")
    schema_changes = schema_job.raw["schema_policy"]["schema_changes"]
    assert schema_changes["added_columns"][0]["column"] == "status"
    assert schema_changes["added_columns"][0]["applied"] is True


def test_gcp_smoke_schema_policy_inspects_gcs_load_source_schema() -> None:
    class GCSProbeClient(FakeBigQueryClient):
        def query(self, sql: str) -> BigQueryJobEvidence:
            evidence = super().query(sql)
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.contractforge_ops.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[
                        {"column_name": "order_id", "data_type": "STRING"},
                        {"column_name": "status", "data_type": "STRING"},
                    ],
                )
            if "INFORMATION_SCHEMA.COLUMNS" in sql and "`test-project.bronze.INFORMATION_SCHEMA.COLUMNS`" in sql:
                return BigQueryJobEvidence(
                    job_id=evidence.job_id,
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[{"column_name": "order_id", "data_type": "STRING"}],
                )
            return evidence

    contract = {
        "source": {
            "type": "gcs",
            "format": "csv",
            "path": "gs://bucket/orders.csv",
            "read": {"columns": [{"name": "order_id", "type": "STRING"}, {"name": "status", "type": "STRING"}]},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "mode": "append",
        "schema_policy": "permissive",
    }
    client = GCSProbeClient()

    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, enforce_schema_policy=True)

    assert result.status == "SUCCEEDED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "schema_policy",
        "persist_schema_evidence",
        "load_source",
        "persist_run_evidence",
        "persist_lineage_evidence",
    ]
    assert len(client.loads) == 2
    assert client.loads[0]["destination_table"].startswith("test-project.contractforge_ops.cf_schema_probe_")
    assert "autodetect" not in client.loads[0]
    assert client.loads[1]["destination_table"] == "test-project.bronze.orders"
    assert any(
        query.startswith("CREATE OR REPLACE TABLE `test-project.contractforge_ops.cf_schema_probe_")
        and "(`order_id` STRING, `status` STRING)" in query
        for query in client.queries
    )
    assert any("DROP TABLE IF EXISTS `test-project.contractforge_ops.cf_schema_probe_" in query for query in client.queries)
    assert any("ALTER TABLE `test-project.bronze.orders` ADD COLUMN `status` STRING" in query for query in client.queries)
    schema_job = next(operation.job for operation in result.operations if operation.name == "schema_policy")
    schema_changes = schema_job.raw["schema_policy"]["schema_changes"]
    assert schema_changes["added_columns"][0]["column"] == "status"
    assert schema_changes["added_columns"][0]["applied"] is True


def test_gcp_smoke_schema_policy_skips_local_rest_materialization_source(monkeypatch) -> None:
    from contractforge_gcp.smoke import workflow as smoke_workflow

    contract = {
        "source": {
            "type": "rest_api",
            "request": {"url": "https://api.example.test/orders"},
            "response": {"mode": "raw", "raw_column": "raw_response"},
        },
        "target": {"catalog": "test-project", "schema": "bronze", "table": "orders"},
        "layer": "bronze",
        "mode": "overwrite",
        "schema_policy": "permissive",
        "quality_rules": {"not_null": ["raw_response"]},
    }
    client = FakeBigQueryClient()

    def fake_reader(_source: dict[str, object]) -> list[dict[str, object]]:
        return [{"raw_response": "{\"ok\": true}", "response_page_number": 1}]

    monkeypatch.setattr(smoke_workflow, "read_rest_api_records", fake_reader)
    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, enforce_schema_policy=True)

    assert result.status == "SUCCEEDED"
    assert "schema_policy" not in [operation.name for operation in result.operations]
    assert any(operation.name == "materialize_source" for operation in result.operations)


def test_gcp_smoke_blocks_review_required_contract_by_default() -> None:
    contract = _table_contract()
    contract["mode"] = "hash_diff_upsert"
    contract["hash_keys"] = ["amount"]

    result = run_gcp_contract_smoke(contract, _environment())

    assert result.status == "BLOCKED"
    assert result.ok is False
    assert result.planning_status == "REVIEW_REQUIRED"
    assert any(warning["code"] == "REVIEW_REQUIRED" for warning in result.warnings)


def test_gcp_smoke_executes_review_required_hash_diff_when_explicitly_allowed() -> None:
    contract = _table_contract()
    contract["mode"] = "hash_diff_upsert"
    contract["merge_keys"] = ["order_id"]
    contract["hash_keys"] = ["amount"]
    contract["source"] = {
        "type": "table",
        "table": "raw.orders",
        "read": {"columns": ["order_id", "amount", "status"]},
    }
    client = FakeBigQueryClient()

    result = run_gcp_contract_smoke(contract, _environment(), client=client, execute=True, allow_review_required=True)

    assert result.status == "SUCCEEDED"
    assert result.planning_status == "REVIEW_REQUIRED"
    assert [operation.name for operation in result.operations] == [
        "prepare_evidence",
        "write_target",
        "persist_run_evidence",
        "persist_lineage_evidence",
        "quality",
        "persist_quality_evidence",
    ]
    assert any("MERGE `test-project.bronze.orders` AS T" in query for query in client.queries)
    assert any("TO_HEX(SHA256" in query for query in client.queries)
    write_index = next(index for index, query in enumerate(client.queries) if "MERGE `test-project.bronze.orders` AS T" in query)
    assert "CONTRACTFORGE_NULL_MERGE_KEY" in client.queries[write_index - 2]
    assert "CONTRACTFORGE_DUPLICATE_MERGE_KEYS" in client.queries[write_index - 1]
    assert not any("CREATE TEMP TABLE" in query for query in client.queries)


def test_gcp_smoke_sql_splitter_keeps_statements_after_comments() -> None:
    sql = "-- rule\nSELECT COUNT(*) FROM `table` WHERE `id` IS NULL;\n-- trailing\n"

    assert split_bigquery_script(sql) == ("SELECT COUNT(*) FROM `table` WHERE `id` IS NULL",)


def test_gcp_bq_resource_evidence_extracts_query_metrics() -> None:
    evidence = bigquery_job_evidence_from_resource(
        {
            "jobReference": {"jobId": "job-1"},
            "status": {"state": "DONE"},
            "statistics": {
                "query": {
                    "statementType": "MERGE",
                    "totalBytesProcessed": "10",
                    "totalBytesBilled": "20",
                    "totalSlotMs": "30",
                    "dmlStats": {
                        "insertedRowCount": "1",
                        "updatedRowCount": "2",
                        "deletedRowCount": "3",
                    },
                }
            },
        },
        job_type="QUERY",
    )

    assert evidence.job_id == "job-1"
    assert evidence.statement_type == "MERGE"
    assert evidence.total_slot_ms == 30
    assert evidence.inserted_rows == 1
    assert evidence.updated_rows == 2
    assert evidence.deleted_rows == 3


def test_gcp_bq_cli_client_assigns_job_id_and_reads_job_resource(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_which(name: str) -> str:
        assert name == "bq"
        return "C:\\CloudSDK\\bq.cmd"

    def fake_run(command, check, capture_output, text):
        commands.append(command)
        if command[-2:] == ["show", "-j"]:
            raise AssertionError("unexpected split show command")
        if "show" in command:
            job_id = command[-1]
            return CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "jobReference": {"jobId": job_id},
                        "status": {"state": "DONE"},
                        "user_email": "person@example.com",
                    }
                ),
                stderr="",
            )
        return CompletedProcess(command, 0, stdout="[]", stderr="")

    monkeypatch.setattr("contractforge_gcp.runtime.shutil.which", fake_which)
    monkeypatch.setattr("contractforge_gcp.runtime.subprocess.run", fake_run)

    client = BqCliBigQueryClient(GCPEnvironment(project_id="test-project", location="US"))
    evidence = client.query("SELECT 1")

    assert evidence.state == "DONE"
    assert evidence.raw["user_email"] == "REDACTED"
    assert commands[0][0] == "C:\\CloudSDK\\bq.cmd"
    assert "--project_id=test-project" in commands[0]
    assert "--location=US" in commands[0]
    assert "query" in commands[0]
    assert any(item.startswith("--job_id=cf_gcp_smoke_query_") for item in commands[0])
    assert commands[1][-2:] == ["-j", evidence.job_id]


def test_gcp_bq_cli_client_captures_query_result_rows(monkeypatch) -> None:
    monkeypatch.setattr("contractforge_gcp.runtime.shutil.which", lambda name: "C:\\CloudSDK\\bq.cmd")

    def fake_run(command, check, capture_output, text):
        if "show" in command:
            return CompletedProcess(
                command,
                0,
                stdout=json.dumps({"jobReference": {"jobId": command[-1]}, "status": {"state": "DONE"}}),
                stderr="",
            )
        return CompletedProcess(command, 0, stdout=json.dumps([{"failed_rows": "0"}]), stderr="")

    monkeypatch.setattr("contractforge_gcp.runtime.subprocess.run", fake_run)

    client = BqCliBigQueryClient(GCPEnvironment(project_id="test-project", location="US"))
    evidence = client.query("SELECT 0 AS failed_rows")

    assert evidence.result_rows == [{"failed_rows": "0"}]


def test_gcp_smoke_marks_quality_failure_from_failed_rows() -> None:
    class FailingQualityClient(FakeBigQueryClient):
        def query(self, sql: str) -> BigQueryJobEvidence:
            evidence = super().query(sql)
            if sql.lstrip().upper().startswith("SELECT") and "failed_rows" in sql:
                return BigQueryJobEvidence(
                    job_id="quality-failure",
                    job_type="QUERY",
                    state="DONE",
                    result_rows=[{"failed_rows": "2"}],
                )
            return evidence

    result = run_gcp_contract_smoke(_table_contract(), _environment(), client=FailingQualityClient(), execute=True)

    assert result.status == "FAILED"
    quality_operation = next(operation for operation in result.operations if operation.name == "quality")
    assert quality_operation.job.error_message == "Quality query returned failed_rows=2."
    assert any(operation.name == "persist_quality_evidence" for operation in result.operations)


def test_gcp_run_evidence_escapes_multiline_bigquery_errors() -> None:
    contract = semantic_contract_from_mapping(_table_contract())
    job = BigQueryJobEvidence(
        job_id="failed-job",
        job_type="QUERY",
        state="FAILED",
        error_message="BigQuery error: job 'failed-job'\nmissing table in location us-east1",
    )

    sql = render_run_evidence_insert_sql(
        environment=GCPEnvironment(project_id="test-project", location="US", evidence_dataset="contractforge_ops"),
        contract=contract,
        job=job,
    )

    assert "job \\'failed-job\\'\\nmissing table" in sql
    assert "job 'failed-job'\nmissing table" not in sql


def test_gcp_bq_cli_client_uses_cli_destination_table_syntax(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr("contractforge_gcp.runtime.shutil.which", lambda name: "C:\\CloudSDK\\bq.cmd")

    def fake_run(command, check, capture_output, text):
        commands.append(command)
        if "show" in command:
            return CompletedProcess(
                command,
                0,
                stdout=json.dumps({"jobReference": {"jobId": command[-1]}, "status": {"state": "DONE"}}),
                stderr="",
            )
        return CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr("contractforge_gcp.runtime.subprocess.run", fake_run)

    client = BqCliBigQueryClient(GCPEnvironment(project_id="test-project", location="US"))
    evidence = client.load_table_from_uri(
        {
            "source_uris": ["gs://bucket/orders.csv"],
            "destination_table": "test-project.bronze.orders",
            "source_format": "CSV",
            "write_disposition": "WRITE_APPEND",
        }
    )

    assert evidence.state == "DONE"
    assert "test-project:bronze.orders" in commands[0]
    assert "test-project.bronze.orders" not in commands[0]


def test_gcp_cli_smoke_dry_run_prints_payload(tmp_path, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    environment_path = tmp_path / "environment.yaml"
    contract_path.write_text(
        """
source:
  type: gcs
  format: csv
  path: gs://bucket/orders.csv
target:
  catalog: test-project
  schema: bronze
  table: orders
mode: append
""".strip(),
        encoding="utf-8",
    )
    environment_path.write_text(
        """
parameters:
  gcp:
    project_id: test-project
    location: US
    dataset: bronze
evidence:
  dataset: contractforge_ops
""".strip(),
        encoding="utf-8",
    )

    rc = gcp_cli(["smoke", str(contract_path), "--environment", str(environment_path)])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["status"] == "DRY_RUN"
    assert [operation["name"] for operation in payload["operations"]] == ["prepare_evidence", "load_source"]


def test_gcp_cli_smoke_writes_report(tmp_path, capsys) -> None:
    contract_path = tmp_path / "contract.yaml"
    environment_path = tmp_path / "environment.yaml"
    report_path = tmp_path / "reports" / "gcp-smoke.json"
    contract_path.write_text(
        """
source:
  type: table
  table: raw.orders
target:
  catalog: test-project
  schema: bronze
  table: orders
mode: overwrite
""".strip(),
        encoding="utf-8",
    )
    environment_path.write_text(
        """
parameters:
  gcp:
    project_id: test-project
    location: US
    dataset: bronze
""".strip(),
        encoding="utf-8",
    )

    rc = gcp_cli(["smoke", str(contract_path), "--environment", str(environment_path), "--report", str(report_path)])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert stdout_payload["status"] == "DRY_RUN"
    assert file_payload == stdout_payload


def test_gcp_project_smoke_dry_run_runs_execution_order(tmp_path) -> None:
    project_path, _environment_path = _write_gcp_project(tmp_path)

    result = run_gcp_project_smoke(project_path)

    assert result.status == "SUCCEEDED"
    assert result.executed is False
    assert [step.name for step in result.steps] == ["bronze_orders", "silver_orders"]
    assert [step.status for step in result.steps] == ["DRY_RUN", "DRY_RUN"]
    assert result.steps[1].depends_on == ("bronze_orders",)


def test_gcp_project_smoke_execute_reuses_runtime_client_for_all_steps(tmp_path) -> None:
    project_path, _environment_path = _write_gcp_project(tmp_path)
    client = FakeBigQueryClient()

    result = run_gcp_project_smoke(project_path, client=client, execute=True)

    assert result.status == "SUCCEEDED"
    assert result.executed is True
    assert len(client.loads) == 1
    assert any("CREATE OR REPLACE TABLE `test-project.silver.orders` AS" in query for query in client.queries)
    assert [step.status for step in result.steps] == ["SUCCEEDED", "SUCCEEDED"]


def test_gcp_project_smoke_stops_on_blocked_step_by_default(tmp_path) -> None:
    project_path, _environment_path = _write_gcp_project(tmp_path)
    blocked = tmp_path / "contracts" / "02_silver.ingestion.yaml"
    blocked.write_text(
        """
source:
  type: table
  table: test-project.bronze.orders
target:
  catalog: test-project
  schema: silver
  table: orders
mode: hash_diff_upsert
hash_keys:
  - amount
""".strip(),
        encoding="utf-8",
    )

    result = run_gcp_project_smoke(project_path, execute=True, client=FakeBigQueryClient())

    assert result.status == "BLOCKED"
    assert [step.name for step in result.steps] == ["bronze_orders", "silver_orders"]
    assert result.steps[1].status == "BLOCKED"


def test_gcp_project_smoke_can_start_at_step(tmp_path) -> None:
    project_path, _environment_path = _write_gcp_project(tmp_path)

    result = run_gcp_project_smoke(project_path, start_at="silver_orders")

    assert result.status == "SUCCEEDED"
    assert [step.name for step in result.steps] == ["silver_orders"]


def test_gcp_cli_run_project_writes_report(tmp_path, capsys) -> None:
    project_path, _environment_path = _write_gcp_project(tmp_path)
    report_path = tmp_path / "reports" / "project-smoke.json"

    rc = gcp_cli(["run-project", str(project_path), "--report", str(report_path)])
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert stdout_payload["status"] == "SUCCEEDED"
    assert [step["name"] for step in stdout_payload["steps"]] == ["bronze_orders", "silver_orders"]
    assert file_payload == stdout_payload


def test_gcp_cli_source_promotion_dry_run_writes_report(tmp_path, capsys) -> None:
    contract_path = tmp_path / "raw_iceberg.yaml"
    environment_path = tmp_path / "environment.yaml"
    report_path = tmp_path / "source-promotion.json"
    contract_path.write_text(
        """
source:
  type: iceberg_table
  path: gs://bucket/lake/orders
target:
  catalog: test-project
  schema: bronze
  table: orders
mode: overwrite
""".strip(),
        encoding="utf-8",
    )
    environment_path.write_text(
        """
parameters:
  gcp:
    project_id: test-project
    location: us-east1
    dataset: contractforge
""".strip(),
        encoding="utf-8",
    )

    rc = gcp_cli(
        [
            "source-promotion",
            str(contract_path),
            "--environment",
            str(environment_path),
            "--report",
            str(report_path),
        ]
    )
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert rc == 0
    assert stdout_payload["status"] == "PLANNED_NOT_EXECUTED"
    assert stdout_payload["source_type"] == "iceberg_table"
    assert stdout_payload["plan"]["biglake_iceberg_registration"]["source_storage_uri"] == "gs://bucket/lake/orders/"
    assert file_payload == stdout_payload
