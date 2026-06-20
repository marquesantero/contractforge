from __future__ import annotations

import json

from contractforge_aws import (
    apply_aws_annotations_contract,
    apply_aws_annotations_plan,
    record_aws_operations_contract,
    render_aws_annotations_evidence_sql,
    render_aws_annotations_plan,
    render_aws_contract,
    render_aws_operations_evidence_sql,
    render_aws_operations_json,
)
from contractforge_aws.runtime.athena import AthenaQueryResult


class FakeGlueCatalogClient:
    def __init__(self, table: dict) -> None:
        self.table = table
        self.get_calls: list[dict] = []
        self.update_calls: list[dict] = []

    def get_table(self, **kwargs: dict) -> dict:
        self.get_calls.append(kwargs)
        return {"Table": self.table}

    def update_table(self, **kwargs: dict) -> None:
        self.update_calls.append(kwargs)


class RecordingRunner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)
        if self.fail:
            raise RuntimeError("athena unavailable password=raw-secret token=raw-token")


def _contract() -> dict:
    return {
        "source": {"type": "parquet", "path": "s3://landing/customers"},
        "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
        "mode": "scd0_append",
        "annotations": {
            "table": {
                "description": "Curated customers",
                "aliases": ["customer_master"],
                "tags": {"domain": "crm"},
                "deprecated": {"since": "2026-01", "replacement": "customers_v2"},
            },
            "columns": {
                "email": {
                    "description": "Customer email",
                    "pii": {"enabled": True, "type": "email", "sensitivity": "confidential"},
                    "tags": {"quality": "validated"},
                }
            },
        },
        "operations": {
            "criticality": "high",
            "expected_frequency": "daily",
            "freshness_sla_minutes": 60,
            "alert_on_failure": True,
            "runbook_url": "https://runbooks.example/customers",
            "owners": ["data-platform"],
            "groups": "support|governance",
            "tags": {"tier": "gold"},
            "ownership": {"business_owner": "sales", "technical_owner": "data-eng"},
        },
    }


def test_aws_annotation_plan_maps_core_annotations_to_glue_catalog_metadata() -> None:
    plan = json.loads(render_aws_annotations_plan(_contract()))

    assert plan["resource"] == {"DatabaseName": "lake_silver", "Name": "customers"}
    assert plan["apply_operation"] == "glue:UpdateTable"
    assert {"annotation_scope": "table", "annotation_type": "description", "value": "Curated customers", "glue_path": "Description", "status": "PLANNED", "column_name": None, "key": "description"} in plan["changes"]
    assert any(change["glue_path"] == "StorageDescriptor.Columns[].Comment" for change in plan["changes"])
    assert any(change["key"] == "pii_type" and change["value"] == "email" for change in plan["changes"])


def test_aws_annotation_evidence_uses_core_control_table_schema() -> None:
    sql = render_aws_annotations_evidence_sql(_contract(), run_id="run-1")

    assert "INSERT INTO glue_catalog.`lake_silver_ops`.`ctrl_ingestion_annotations`" in sql
    assert "`annotation_scope`" in sql
    assert "'glue:UpdateTable'" in sql
    assert "'contractforge-aws'" in sql
    assert "'Curated customers'" in sql


def test_aws_operations_metadata_renders_json_and_evidence() -> None:
    payload = json.loads(render_aws_operations_json(_contract()))
    sql = render_aws_operations_evidence_sql(_contract(), run_id="run-1")

    assert payload["criticality"] == "high"
    assert payload["owners"] == ["data-platform"]
    assert payload["groups"] == ["support", "governance"]
    assert payload["ownership"]["technical_owner"] == "data-eng"
    assert "INSERT INTO glue_catalog.`lake_silver_ops`.`ctrl_ingestion_operations`" in sql
    assert "`framework_version`" in sql
    assert "'contractforge-aws'" in sql
    assert "'https://runbooks.example/customers'" in sql


def test_aws_contract_publishes_annotations_and_operations_artifacts() -> None:
    artifacts = render_aws_contract(_contract()).artifacts

    assert "lake_silver_customers.annotations.json" in artifacts
    assert "lake_silver_customers.annotations_evidence.sql" in artifacts
    assert "lake_silver_customers.operations.json" in artifacts
    assert "lake_silver_customers.operations.sql" in artifacts


def test_apply_aws_annotations_plan_preserves_glue_table_input() -> None:
    plan = render_aws_annotations_plan(_contract())
    client = FakeGlueCatalogClient(
        {
            "Name": "customers",
            "DatabaseName": "lake_silver",
            "CreateTime": "read-only",
            "Description": "Old",
            "Parameters": {"existing": "keep"},
            "StorageDescriptor": {
                "Location": "s3://warehouse/customers",
                "Columns": [
                    {"Name": "id", "Type": "string"},
                    {"Name": "email", "Type": "string", "Parameters": {"existing_col": "keep"}},
                ],
            },
            "TableType": "EXTERNAL_TABLE",
        }
    )

    result = apply_aws_annotations_plan(plan, glue_client=client, catalog_id="123456789012", skip_archive=False)

    assert result.status == "SUCCESS"
    assert result.applied == 11
    assert client.get_calls == [{"DatabaseName": "lake_silver", "Name": "customers", "CatalogId": "123456789012"}]
    update = client.update_calls[0]
    assert update["CatalogId"] == "123456789012"
    assert update["SkipArchive"] is False
    assert update["TableInput"]["Description"] == "Curated customers"
    assert update["TableInput"]["Parameters"]["existing"] == "keep"
    assert update["TableInput"]["Parameters"]["domain"] == "crm"
    assert "CreateTime" not in update["TableInput"]
    email = update["TableInput"]["StorageDescriptor"]["Columns"][1]
    assert email["Comment"] == "Customer email"
    assert email["Parameters"]["existing_col"] == "keep"
    assert email["Parameters"]["pii_type"] == "email"


def test_apply_aws_annotations_contract_renders_and_applies_plan() -> None:
    client = FakeGlueCatalogClient(
        {
            "Name": "customers",
            "StorageDescriptor": {"Columns": [{"Name": "email", "Type": "string"}]},
            "TableType": "EXTERNAL_TABLE",
        }
    )

    result = apply_aws_annotations_contract(_contract(), glue_client=client)

    assert result.database == "lake_silver"
    assert result.table == "customers"
    assert result.status == "SUCCESS"
    assert client.update_calls[0]["DatabaseName"] == "lake_silver"


def test_apply_aws_annotations_plan_fails_on_missing_column() -> None:
    plan = render_aws_annotations_plan(_contract())
    client = FakeGlueCatalogClient(
        {"Name": "customers", "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "string"}]}}
    )

    try:
        apply_aws_annotations_plan(plan, glue_client=client)
    except ValueError as exc:
        assert "does not contain column 'email'" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected missing-column validation error")


def test_record_aws_operations_contract_executes_operations_evidence_sql() -> None:
    runner = RecordingRunner()

    result = record_aws_operations_contract(runner=runner, contract=_contract(), run_id="run-42")

    assert result.status == "RECORDED"
    assert len(runner.statements) == 1
    assert "INSERT INTO glue_catalog.`lake_silver_ops`.`ctrl_ingestion_operations`" in runner.statements[0]
    assert "'run-42'" in runner.statements[0]
    assert "'RECORDED'" in runner.statements[0]


def test_record_aws_operations_contract_reports_runner_failure() -> None:
    result = record_aws_operations_contract(runner=RecordingRunner(fail=True), contract=_contract())

    assert result.status == "FAILED"
    assert result.error is not None
    assert result.error.startswith("athena unavailable")
    assert "raw-secret" not in result.error
    assert "raw-token" not in result.error
    assert "***REDACTED***" in result.error
    assert result.sql is not None


def test_record_aws_operations_contract_reports_async_submission() -> None:
    class AsyncRunner:
        def sql(self, statement: str) -> AthenaQueryResult:
            return AthenaQueryResult(query_execution_id="q-1", state="SUBMITTED", statement=statement)

    result = record_aws_operations_contract(runner=AsyncRunner(), contract=_contract(), run_id="run-42")

    assert result.status == "SUBMITTED"
    assert result.sql is not None


def test_record_aws_operations_contract_ignores_contract_without_operations() -> None:
    runner = RecordingRunner()
    contract = {
        "source": {"type": "parquet", "path": "s3://landing/customers"},
        "target": {"catalog": "lake", "schema": "silver", "table": "customers"},
        "mode": "scd0_append",
    }

    result = record_aws_operations_contract(runner=runner, contract=contract)

    assert result.status == "NOT_CONFIGURED"
    assert runner.statements == []
