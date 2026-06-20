from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gcp_capability_parity_doc_records_supported_surface_and_gates() -> None:
    doc = (ROOT / "docs" / "specs" / "gcp-capability-parity.md").read_text(encoding="utf-8")

    assert "Status: `STABLE_SUPPORTED_SURFACE`" in doc
    assert "`gcp_bigquery`" in doc
    assert "GCS files: CSV, JSON/JSONL/NDJSON, Parquet, Avro, ORC" in doc
    assert "BigQuery `MERGE`" in doc
    assert "`GCP-BQ-03`" in doc
    assert "`GCP-BQ-05`" in doc
    assert "`GCP-BQ-08`" in doc
    assert "`GCP-BQ-12A`" in doc
    assert "`GCP-BQ-12C`" in doc
    assert "`GCP-BQ-12B`" in doc
    assert "`GCP-BQ-12C4`" in doc
    assert "`GCP-BQ-12C5`" in doc
    assert "`GCP-BQ-12D`" in doc
    assert "`GCP-BQ-13A`" in doc
    assert "`GCP-BQ-13A0`" in doc
    assert "`GCP-BQ-15B`" in doc
    assert "`GCP-BQ-15C`" in doc
    assert "`GCP-BQ-15C3`" in doc
    assert "`GCP-BQ-15C4`" in doc
    assert "`GCP-BQ-15C5`" in doc
    assert "`GCP-BQ-15C6`" in doc
    assert "`GCP-BQ-15C7`" in doc
    assert "`GCP-BQ-15C8`" in doc
    assert "`GCP-BQ-15C9`" in doc
    assert "`GCP-BQ-15C10`" in doc
    assert "`GCP-BQ-16A1`" in doc
    assert "`GCP-BQ-16B3`" in doc
    assert "`GCP-BQ-17B1`" in doc
    assert "`GCP-BQ-17B2`" in doc
    assert "`GCP-BQ-17B`" in doc
    assert "`GCP-BQ-20`" in doc
    assert "`GCP-BQ-20A`" in doc
    assert "`GCP-BQ-20B`" in doc
    assert "`GCP-BQ-20D`" in doc
    assert "`GCP-BQ-20C`" in doc
    assert "`GCP-BQ-20E`" in doc
    assert "authenticated REST/HTTP Secret Manager review/runtime resolution" in doc
    assert "redacted source-review JSON/Markdown" in doc
    assert "source-family promotion-plan JSON" in doc
    assert "non-JDBC source-family promotion paths" in doc
    assert "row access policy apply/readback/enforcement" in doc
    assert "docs/reports/gcp-bigquery-data-masking-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-policy-tags-smoke.json" in doc
    assert "docs/reports/gcp-biglake-iceberg-smoke.json" in doc
    assert "docs/reports/gcp-raw-iceberg-registration-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-schema-policy-strict-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-schema-policy-permissive-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-schema-policy-type-change-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-schema-policy-sql-source-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-schema-policy-gcs-source-smoke.json" in doc
    assert "docs/reports/gcp-schema-policy-type-mutation-decision.json" in doc
    assert "BigQuery table/view/SQL and declared-schema GCS-source runtime hook" in doc
    assert "BigQuery table-source/target `INFORMATION_SCHEMA.COLUMNS`" not in doc
    assert "docs/reports/gcp-streaming-scope-decision.json" in doc
    assert "docs/reports/gcp-write-mode-scope-decision.json" in doc
    assert "docs/reports/gcp-hashdiff-cross-adapter-production-parity.json" in doc
    assert "docs/reports/gcp-auth-rest-http-secret-manager-variants-smoke.json" in doc
    assert "docs/reports/gcp-auth-rest-http-secret-manager-variants-blocker.json" in doc
    assert "docs/reports/gcp-http-text-materialization-local-smoke.json" in doc
    assert "docs/reports/gcp-http-sources-bigquery-smoke.json" in doc
    assert "docs/reports/gcp-http-file-binary-bigquery-smoke.json" in doc
    assert "docs/reports/gcp-http-text-bigquery-smoke-blocker.json" in doc
    assert "docs/reports/gcp-http-file-materialization-local-smoke.json" in doc
    assert "docs/reports/gcp-deployment-orchestration-scope-decision.json" in doc
    assert "docs/reports/gcp-workflows-command-readback-smoke.json" in doc
    assert "docs/reports/gcp-workflows-runner-evidence-smoke.json" in doc
    assert "docs/reports/gcp-workflows-quality-semantics-smoke.json" in doc
    assert "docs/reports/gcp-workflows-execution-runid-smoke.json" in doc
    assert "docs/reports/gcp-workflows-schema-evidence-smoke.json" in doc
    assert "docs/reports/gcp-workflows-cleanup-command-smoke.json" in doc
    assert "docs/reports/gcp-workflows-write-failure-evidence-smoke.json" in doc
    assert "docs/reports/gcp-workflows-target-evidence-cleanup-smoke.json" in doc
    assert "bounded BigQuery job polling" in doc
    assert "docs/reports/gcp-dataplex-lineage-dq-scope-decision.json" in doc
    assert "docs/reports/gcp-dataplex-lineage-aspect-runtime-decision.json" in doc
    assert "docs/reports/gcp-governance-stable-scope-decision.json" in doc
    assert "docs/reports/gcp-governance-ledger-evidence-smoke.json" in doc
    assert "docs/reports/gcp-governance-ledger-reconciliation-plan.json" in doc
    assert "docs/reports/gcp-governance-ledger-reconciliation-smoke.json" in doc
    assert "docs/reports/gcp-stable-surface-evidence.json" in doc
    assert "docs/reports/gcp-bigquery-annotations-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-error-evidence-smoke.json" in doc
    assert "docs/reports/gcp-bigquery-hashdiff-production-benchmark.json" in doc
    assert "docs/reports/gcp-bigquery-advanced-write-production-benchmark.json" in doc
    assert "docs/reports/gcp-bigquery-data-masking-blocker.json" in doc
    assert "Databricks-level full runtime parity beyond the scoped BigQuery batch and Workflows runner surface" in doc


def test_gcp_capability_parity_doc_links_official_google_sources() -> None:
    doc = (ROOT / "docs" / "specs" / "gcp-capability-parity.md").read_text(encoding="utf-8")

    assert "https://docs.cloud.google.com/bigquery/docs/batch-loading-data" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/dml-syntax" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/hash_functions" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/access-historical-data" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/information-schema-jobs" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/information-schema-column-field-paths" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/row-level-security-intro" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/column-level-security-intro" in doc
    assert "https://docs.cloud.google.com/bigquery/docs/access-control" in doc
    assert "https://docs.cloud.google.com/secret-manager/docs/access-control" in doc
    assert "https://docs.cloud.google.com/secret-manager/docs/access-secret-version" in doc
    assert "https://docs.cloud.google.com/sdk/gcloud/reference/secrets/versions/access" in doc
    assert "https://docs.cloud.google.com/dataflow/docs/guides/read-from-kafka" in doc
    assert "https://docs.cloud.google.com/pubsub/docs/bigquery" in doc
    assert "https://cloud.google.com/workflows/docs" in doc
    assert "https://docs.cloud.google.com/workflows/docs/reference/environment-variables" in doc
    assert "https://cloud.google.com/workflows/docs/reference/googleapis/bigquery/Overview" in doc
    assert "https://docs.cloud.google.com/dataplex/docs/reference/rest" in doc
    assert "https://docs.cloud.google.com/data-catalog/docs/data-lineage" in doc
    assert "https://docs.cloud.google.com/dataplex/docs/check-data-quality" in doc


def test_gcp_docs_index_links_capability_parity_doc() -> None:
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    adapter = (ROOT / "docs" / "adapters" / "gcp.md").read_text(encoding="utf-8")

    assert "specs/gcp-capability-parity.md" in readme
    assert "reports/gcp-stable-surface-evidence.json" in readme
    assert "reports/gcp-auth-rest-http-secret-manager-variants-smoke.json" in readme
    assert "reports/gcp-auth-rest-http-secret-manager-variants-blocker.json" in readme
    assert "reports/gcp-http-text-materialization-local-smoke.json" in readme
    assert "reports/gcp-http-sources-bigquery-smoke.json" in readme
    assert "reports/gcp-http-file-binary-bigquery-smoke.json" in readme
    assert "reports/gcp-http-text-bigquery-smoke-blocker.json" in readme
    assert "reports/gcp-http-file-materialization-local-smoke.json" in readme
    assert "../specs/gcp-capability-parity.md" in adapter
    assert "../reports/gcp-stable-surface-evidence.json" in adapter
    assert "redacted source-review JSON and Markdown artifacts" in adapter
    assert "non-JDBC source-family promotion paths" in adapter
    assert "source-family promotion-plan JSON" in adapter
    assert "authenticated REST/HTTP Secret Manager review artifacts and resolve placeholders at runtime" in adapter
    assert "execution_ready: true" in adapter


def test_gcp_smoke_report_records_redacted_successful_live_run() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-csv-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["executed"] is True
    load_operation = next(item for item in payload["operations"] if item["name"] == "load_source")
    quality_operation = next(item for item in payload["operations"] if item["name"] == "quality")
    assert load_operation["job"]["output_rows"] == 3
    assert quality_operation["job"]["result_rows"] == [{"failed_rows": "0"}]
    assert "antero" not in report.lower()
    assert "gmail.com" not in report.lower()


def test_gcp_file_format_smoke_report_records_all_supported_gcs_formats() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-file-formats-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-02"
    assert set(payload["formats"]) == {"avro", "csv", "ndjson", "orc", "parquet"}
    for result in payload["formats"].values():
        assert result["status"] == "SUCCEEDED"
        assert result["ok"] is True
        load_operation = next(item for item in result["operations"] if item["name"] == "load_source")
        quality_operation = next(item for item in result["operations"] if item["name"] == "quality")
        assert load_operation["job"]["output_rows"] == 3
        assert quality_operation["job"]["result_rows"] == [{"failed_rows": "0"}]
        assert any(item["name"] == "persist_run_evidence" for item in result["operations"])
        assert any(item["name"] == "persist_quality_evidence" for item in result["operations"])


def test_gcp_upsert_smoke_report_records_merge_dml_stats_and_verification() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-upsert-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-04"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    write_operation = next(item for item in payload["operations"] if item["name"] == "write_target")
    assert write_operation["job"]["statement_type"] == "MERGE"
    assert write_operation["job"]["inserted_rows"] == 1
    assert write_operation["job"]["updated_rows"] == 1
    assert payload["verification"] == [
        {"failed_rows": "0", "inserted_rows": "1", "row_count": "3", "updated_rows": "1"}
    ]


def test_gcp_bronze_to_gold_smoke_report_records_medallion_e2e() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-bronze-to-gold-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-03"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert [item["name"] for item in payload["contracts"]] == [
        "bronze_orders_csv",
        "silver_orders_curated",
        "gold_orders_by_status",
    ]
    assert payload["verification"] == [
        {"failed_rows": "0", "layer": "bronze", "row_count": "3"},
        {"failed_rows": "0", "layer": "gold", "row_count": "2"},
        {"failed_rows": "0", "layer": "silver", "row_count": "3"},
    ]
    assert payload["gold_rows"] == [
        {"amount_total": "10.5", "order_count": "1", "status": "new"},
        {"amount_total": "27.25", "order_count": "2", "status": "paid"},
    ]
    assert {item["contract_name"] for item in payload["run_evidence_rows"]} == {
        "b2g_bronze_orders",
        "b2g_silver_orders",
        "b2g_gold_orders_by_status",
    }


def test_gcp_schema_policy_smoke_report_records_additive_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-schema-policy-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_bigquery_schema_policy_smoke"
    assert payload["status"] == "PASS"
    assert payload["maturity_gate"] == "GCP-BQ-07C"
    assert payload["contract"]["schema_policy"] == "additive_only"
    assert payload["decision"]["additive_nullable_column_e2e"] == "VALIDATED"
    assert payload["decision"]["schema_evidence_readback"] == "VALIDATED"
    assert payload["readback"]["target_row_count"] == 2
    assert payload["readback"]["schema_evidence"]["added_columns"] == ["amount"]
    assert payload["readback"]["schema_evidence"]["added_applied"] is True
    assert any(
        "ADD COLUMN `amount` FLOAT64" in command
        for operation in payload["operations"]
        for command in operation.get("commands", [])
    )
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_schema_policy_strict_smoke_report_records_failed_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-schema-policy-strict-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_bigquery_schema_policy_strict_smoke"
    assert payload["status"] == "PASS_NEGATIVE"
    assert payload["maturity_gate"] == "GCP-BQ-07D"
    assert payload["contract"]["schema_policy"] == "strict"
    assert payload["decision"]["strict_schema_drift_e2e"] == "VALIDATED"
    assert payload["decision"]["failure_schema_evidence"] == "VALIDATED"
    assert payload["decision"]["target_write_after_drift"] == "BLOCKED_AS_EXPECTED"
    schema_policy = next(item for item in payload["operations"] if item["name"] == "schema_policy")
    persisted = next(item for item in payload["operations"] if item["name"] == "persist_schema_evidence")
    assert schema_policy["status"] == "FAILED_EXPECTED"
    assert "Schema policy strict violation" in schema_policy["error_message"]
    assert schema_policy["schema_changes"]["added_columns"][0]["column"] == "status"
    assert persisted["inserted_rows"] == 1
    assert payload["readback"]["schema_evidence"]["status"] == "FAILED"
    assert payload["readback"]["schema_evidence"]["added_columns"] == ["status"]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_schema_policy_permissive_smoke_report_records_successful_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-schema-policy-permissive-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_bigquery_schema_policy_permissive_smoke"
    assert payload["status"] == "PASS"
    assert payload["maturity_gate"] == "GCP-BQ-07E"
    assert payload["contract"]["schema_policy"] == "permissive"
    assert payload["decision"]["permissive_nullable_column_e2e"] == "VALIDATED"
    assert payload["decision"]["schema_evidence_readback"] == "VALIDATED"
    assert payload["decision"]["write_after_schema_sync"] == "VALIDATED"
    assert payload["readback"]["target_row_count"] == 2
    assert payload["readback"]["target_amount_not_null"] == 2
    assert payload["readback"]["schema_evidence"]["status"] == "SUCCEEDED"
    assert payload["readback"]["schema_evidence"]["added_columns"] == ["amount"]
    assert payload["readback"]["schema_evidence"]["added_applied"] is True
    assert any(
        "ADD COLUMN `amount` FLOAT64" in command
        for operation in payload["operations"]
        for command in operation.get("commands", [])
    )
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_schema_policy_type_change_smoke_report_records_failed_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-schema-policy-type-change-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_bigquery_schema_policy_type_change_smoke"
    assert payload["status"] == "PASS_NEGATIVE"
    assert payload["maturity_gate"] == "GCP-BQ-07F"
    assert payload["contract"]["schema_policy"] == "permissive"
    assert payload["decision"]["destructive_type_change_block_e2e"] == "VALIDATED"
    assert payload["decision"]["failure_schema_evidence"] == "VALIDATED"
    assert payload["decision"]["target_write_after_drift"] == "BLOCKED_AS_EXPECTED"
    assert payload["decision"]["automatic_type_widening_or_mutation"] == "REVIEW_REQUIRED"
    assert payload["decision"]["full_schema_policy_promotion"] == "VALIDATED_WITH_REVIEW_BOUNDARY"
    schema_policy = next(item for item in payload["operations"] if item["name"] == "schema_policy")
    persisted = next(item for item in payload["operations"] if item["name"] == "persist_schema_evidence")
    assert schema_policy["status"] == "FAILED_EXPECTED"
    assert "permissive does not apply potentially destructive type changes" in schema_policy["error_message"]
    assert schema_policy["schema_changes"]["type_changes"][0]["column"] == "amount"
    assert schema_policy["schema_changes"]["type_changes"][0]["source"] == "STRING"
    assert schema_policy["schema_changes"]["type_changes"][0]["target"] == "FLOAT64"
    assert schema_policy["schema_changes"]["type_changes"][0]["applied"] is False
    assert persisted["inserted_rows"] == 1
    assert payload["readback"]["target_row_count"] == 0
    assert payload["readback"]["schema_evidence"]["status"] == "FAILED"
    assert payload["readback"]["schema_evidence"]["type_change_column"] == "amount"
    assert payload["readback"]["schema_evidence"]["allowed"] is False
    assert payload["readback"]["schema_evidence"]["applied"] is False
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_schema_policy_type_mutation_decision_records_review_boundary() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-schema-policy-type-mutation-decision.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_schema_policy_type_mutation_decision"
    assert payload["status"] == "DECIDED"
    assert payload["maturity_gate"] == "GCP-BQ-07I"
    assert payload["decision"]["automatic_type_widening_or_mutation"] == "REVIEW_REQUIRED"
    assert payload["decision"]["runtime_behavior"].startswith("Block type changes")
    assert "docs/reports/gcp-bigquery-schema-policy-type-change-smoke.json" in payload["evidence"]
    assert "automatic BigQuery type widening or type mutation".lower() in " ".join(payload["rationale"]).lower()
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_schema_policy_sql_source_smoke_report_records_successful_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-schema-policy-sql-source-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_bigquery_schema_policy_sql_source_smoke"
    assert payload["status"] == "PASS"
    assert payload["maturity_gate"] == "GCP-BQ-07G"
    assert payload["contract"]["source"] == "inline_sql"
    assert payload["decision"]["sql_source_schema_policy_e2e"] == "VALIDATED"
    assert payload["decision"]["schema_probe_cleanup"] == "VALIDATED"
    assert payload["decision"]["schema_evidence_readback"] == "VALIDATED"
    assert payload["decision"]["write_after_schema_sync"] == "VALIDATED"
    assert payload["readback"]["target_row_count"] == 2
    assert payload["readback"]["target_status_not_null"] == 2
    assert payload["readback"]["schema_probe_tables_remaining"] == []
    assert payload["readback"]["schema_evidence"]["status"] == "SUCCEEDED"
    assert payload["readback"]["schema_evidence"]["added_columns"] == ["status"]
    assert payload["readback"]["schema_evidence"]["added_applied"] is True
    schema_policy = next(item for item in payload["operations"] if item["name"] == "schema_policy")
    assert schema_policy["source_inspection"] == "zero-row SQL schema probe in evidence dataset"
    assert schema_policy["probe_cleanup"] == "VALIDATED"
    assert any("ADD COLUMN `status` STRING" in command for command in schema_policy["commands"])
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_schema_policy_gcs_source_smoke_report_records_successful_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-schema-policy-gcs-source-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_bigquery_schema_policy_gcs_source_smoke"
    assert payload["status"] == "PASS"
    assert payload["maturity_gate"] == "GCP-BQ-07H"
    assert payload["contract"]["source_type"] == "gcs"
    assert payload["decision"]["gcs_load_source_schema_policy_e2e"] == "VALIDATED"
    assert payload["decision"]["declared_source_schema_probe"] == "VALIDATED"
    assert payload["decision"]["schema_probe_cleanup"] == "VALIDATED"
    assert payload["decision"]["schema_evidence_readback"] == "VALIDATED"
    assert payload["decision"]["write_after_schema_sync"] == "VALIDATED"
    assert payload["readback"]["target_row_count"] == 2
    assert payload["readback"]["target_status_not_null"] == 2
    assert payload["readback"]["schema_probe_tables_remaining"] == []
    assert payload["readback"]["schema_evidence"]["status"] == "SUCCEEDED"
    assert payload["readback"]["schema_evidence"]["added_columns"] == ["status"]
    assert payload["readback"]["schema_evidence"]["added_applied"] is True
    schema_policy = next(item for item in payload["operations"] if item["name"] == "schema_policy")
    assert schema_policy["source_inspection"] == "declared-schema GCS load probe in evidence dataset"
    assert schema_policy["probe_cleanup"] == "VALIDATED"
    assert any("ADD COLUMN `status` STRING" in command for command in schema_policy["commands"])
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_row_access_policy_smoke_report_records_restricted_principal_enforcement() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-row-access-policy-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-08"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["policy"]["filter_predicate"] == "status = 'paid'"
    assert payload["contract_basis"]["unfiltered_source_row_count"] == 3
    assert payload["contract_basis"]["expected_filtered_row_count"] == 2
    readback = next(item for item in payload["operations"] if item["name"] == "readback_row_access_policy")
    enforcement = next(item for item in payload["operations"] if item["name"] == "impersonated_reader_enforcement_query")
    assert readback["readback"]["filter_predicate"] == "status = 'paid'"
    assert enforcement["result_rows"] == [{"paid_count": "2", "row_count": "2"}]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_error_evidence_smoke_report_records_failed_run_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-error-evidence-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-05"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    failed = next(item for item in payload["operations"] if item["name"] == "write_target")
    persisted = next(item for item in payload["operations"] if item["name"] == "persist_run_evidence")
    assert failed["status"] == "FAILED"
    assert persisted["inserted_rows"] == 1
    assert payload["readback"]["status"] == "FAILED"
    assert payload["readback"]["has_error_message"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_data_masking_blocker_report_records_account_prerequisite() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-data-masking-blocker.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-08"
    assert payload["status"] == "BLOCKED"
    assert payload["ok"] is False
    assert payload["blocker"]["classification"] == "ACCOUNT_PREREQUISITE"
    assert payload["superseded_by"] == "docs/reports/gcp-bigquery-data-masking-smoke.json"
    assert "organization" in payload["blocker"]["message"]
    assert "https://docs.cloud.google.com/bigquery/docs/column-data-masking" in payload["sources"]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_data_masking_smoke_report_records_masked_reader_enforcement() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-data-masking-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-08"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["organization_backed"] is True
    assert payload["policy"]["data_policy_type"] == "DATA_MASKING_POLICY"
    assert payload["policy"]["version"] == "V2"
    assert payload["policy"]["masking_expression"] == "ALWAYS_NULL"
    enforcement = next(item for item in payload["operations"] if item["name"] == "masked_reader_enforcement_query")
    assert enforcement["result_rows"] == [
        {"amount": None, "order_id": "1", "status": "new"},
        {"amount": None, "order_id": "2", "status": "paid"},
    ]
    assert payload["readback"]["schema_column"]["data_policies"][0]["name"].endswith(
        "/dataPolicies/cf_mask_amount_null"
    )
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_annotations_smoke_report_records_description_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-annotations-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-09"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    table_readback = next(item for item in payload["operations"] if item["name"] == "readback_table_description")
    column_readback = next(item for item in payload["operations"] if item["name"] == "readback_column_description")
    evidence_readback = next(item for item in payload["operations"] if item["name"] == "readback_annotation_evidence")
    assert table_readback["source"] == "INFORMATION_SCHEMA.TABLE_OPTIONS"
    assert table_readback["result_rows"] == [
        {
            "option_name": "description",
            "option_value": "\"ContractForge GCP annotation smoke table\"",
            "table_name": "annotation_orders",
        }
    ]
    assert column_readback["source"] == "INFORMATION_SCHEMA.COLUMN_FIELD_PATHS"
    assert column_readback["result_rows"] == [
        {
            "column_name": "customer_email",
            "description": "Customer email from annotation contract",
            "field_path": "customer_email",
        }
    ]
    assert evidence_readback["source"] == "contractforge_annotation_evidence"
    assert evidence_readback["result_rows"] == [
        {
            "annotation_scope": "table",
            "annotation_type": "description",
            "column_name": None,
            "framework_version": "contractforge-gcp",
            "status": "APPLIED",
            "value": "ContractForge GCP annotation smoke table",
        },
        {
            "annotation_scope": "column",
            "annotation_type": "description",
            "column_name": "customer_email",
            "framework_version": "contractforge-gcp",
            "status": "APPLIED",
            "value": "Customer email from annotation contract",
        },
    ]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_policy_tags_smoke_report_records_deny_then_allow_enforcement() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-bigquery-policy-tags-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-08"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["taxonomy"]["activated_policy_types"] == ["FINE_GRAINED_ACCESS_CONTROL"]
    assert payload["decision"]["column_level_access_policy_tags"] == "VALIDATED"
    assert payload["decision"]["tag_based_masking"] == "REVIEW_REQUIRED"
    readback = next(item for item in payload["operations"] if item["name"] == "readback_policy_tag")
    denied = next(item for item in payload["operations"] if item["name"] == "restricted_reader_protected_column_before_grant")
    allowed = next(item for item in payload["operations"] if item["name"] == "restricted_reader_protected_column_after_grant")
    region_mismatch = next(item for item in payload["operations"] if item["name"] == "attach_wrong_region_policy_tag")
    assert readback["source"] == "INFORMATION_SCHEMA.COLUMN_FIELD_PATHS"
    assert readback["result_rows"][0]["column_name"] == "customer_email"
    assert denied["status"] == "FAILED_EXPECTED"
    assert denied["error_classification"] == "FINE_GRAINED_ACCESS_DENIED"
    assert allowed["status"] == "SUCCEEDED"
    assert allowed["result_rows"] == [
        {"customer_email": "alpha@example.com", "order_id": "1"},
        {"customer_email": "beta@example.com", "order_id": "2"},
    ]
    assert region_mismatch["error_classification"] == "REGION_MISMATCH"
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_biglake_iceberg_smoke_report_records_registered_table_surface() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-biglake-iceberg-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-14"
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["table"]["managed_table_type"] == "BIGLAKE"
    assert payload["table"]["table_format"] == "ICEBERG"
    assert payload["decision"]["registered_bigquery_biglake_iceberg_table_sources"] == "VALIDATED"
    assert payload["decision"]["raw_iceberg_path_sources"] == "REVIEW_REQUIRED"
    append = next(item for item in payload["operations"] if item["name"] == "query_after_append")
    merge = next(item for item in payload["operations"] if item["name"] == "query_after_merge")
    config = next(item for item in payload["operations"] if item["name"] == "readback_biglake_configuration")
    layout = next(item for item in payload["operations"] if item["name"] == "readback_storage_layout")
    assert append["result_rows"] == [{"amount_total": "30.5", "row_count": "2"}]
    assert merge["result_rows"] == [
        {"amount": "10.5", "order_id": "1", "status": "paid"},
        {"amount": "25", "order_id": "2", "status": "paid"},
        {"amount": "5", "order_id": "3", "status": "new"},
    ]
    assert config["biglake_configuration"]["tableFormat"] == "ICEBERG"
    assert config["num_rows"] == "3"
    assert any(item.endswith("metadata/v0.metadata.json") for item in layout["objects_observed"])
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_raw_iceberg_registration_smoke_report_records_command_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-raw-iceberg-registration-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_raw_iceberg_registration_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-20E"
    assert payload["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert payload["result"]["status"] == "SUCCEEDED"
    assert [operation["name"] for operation in payload["result"]["operations"]] == [
        "register_biglake_iceberg_table",
        "readback_biglake_iceberg_table",
        "query_registered_table",
    ]
    readback = payload["result"]["operations"][1]
    assert readback["biglake_configuration"]["tableFormat"] == "ICEBERG"
    assert readback["schema_fields"] == ["order_id", "status", "amount"]
    assert all(assertion["passed"] for assertion in payload["result"]["readback_assertions"])
    assert "BigLake table creation fails without an explicit schema." in payload["provider_findings"]
    assert payload["no_workaround_code_used"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_streaming_scope_decision_excludes_first_stable_surface() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-streaming-scope-decision.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["gate"] == "GCP-BQ-13"
    assert payload["status"] == "DECIDED"
    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["decision"]["stable_final_scope"] == "EXCLUDED_FROM_FIRST_STABLE_SURFACE"
    assert payload["decision"]["kafka_available_now"] == "PROVIDER_PARITY_VALIDATED_FOR_CONFLUENT_DATAFLOW"
    assert payload["decision"]["dataflow_kafka_runtime"] == "CONFLUENT_PROVIDER_PARITY_VALIDATED_BROADER_STREAMING_REVIEW_SCOPED"
    assert payload["decision"]["pubsub_bigquery_subscription"] == "NATIVE_BUT_NOT_EQUIVALENT_TO_KAFKA_AVAILABLE_NOW"
    assert payload["latest_live_validation"]["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert payload["latest_live_validation"]["evidence"] == "docs/reports/gcp-confluent-kafka-dataflow-source-promotion-smoke.json"
    assert payload["adapter_behavior"]["supports_available_now_streaming"] is True
    assert payload["adapter_behavior"]["streaming_e2e"] is True
    assert "production streaming operations coverage" in " ".join(payload["required_before_promotion"])
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_write_mode_scope_decision_excludes_advanced_modes_from_first_stable_surface() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-write-mode-scope-decision.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_write_mode_scope_decision"
    assert payload["maturity_gate"] == "GCP-BQ-12"
    assert payload["status"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert payload["decision"]["stable_final_scope"] == "EXCLUDED"
    assert set(payload["decision"]["excluded_modes"]) == {
        "hash_diff_upsert",
        "historical",
        "snapshot_reconcile_soft_delete",
    }
    assert "Do not silently fall back" in payload["decision"]["planner_behavior"]
    assert "hash_diff_upsert production parity" in payload["decision"]["reason"]
    assert payload["adapter_behavior"]["stable_write_modes"] == ["append", "overwrite", "upsert"]
    assert payload["adapter_behavior"]["advanced_write_mode_review_artifact_planning"] is True
    assert payload["adapter_behavior"]["supports_hash_diff"] is False
    assert payload["adapter_behavior"]["supports_historical"] is False
    assert payload["adapter_behavior"]["supports_snapshot_reconcile_soft_delete"] is False
    assert "https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/hash_functions" in payload["sources"]
    assert payload["validated_evidence"]["gcp_bq_12c"] == (
        "docs/reports/gcp-hashdiff-cross-adapter-production-parity.json"
    )
    assert "Hash_diff_upsert production parity is accepted" in payload["acceptance"]
    assert payload["required_before_promotion"]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_deployment_orchestration_scope_decision_promotes_workflows_runner() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-deployment-orchestration-scope-decision.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_deployment_orchestration_scope_decision"
    assert payload["maturity_gate"] == "GCP-BQ-15"
    assert payload["status"] == "PASS_WITH_NON_WORKFLOWS_EXCLUSIONS"
    assert payload["decision"]["stable_final_scope"] == "WORKFLOWS_INCLUDED"
    assert set(payload["decision"]["included_surfaces"]) == {"workflows_project_runner"}
    assert set(payload["decision"]["excluded_surfaces"]) == {
        "cloud_run_jobs_runner",
        "composer_dag_runner",
        "bigquery_scheduled_queries",
    }
    assert payload["adapter_behavior"]["rendered_bundle_deployable"] is True
    assert payload["adapter_behavior"]["workflows_runner_artifact_planning"] is True
    assert payload["adapter_behavior"]["workflows_evidence_readback_artifact"] is True
    assert payload["adapter_behavior"]["workflows_evidence_readback_command"] is True
    assert payload["adapter_behavior"]["workflows_live_command_readback_smoke"] is True
    assert payload["adapter_behavior"]["workflows_runner_evidence_persistence"] is True
    assert payload["adapter_behavior"]["workflows_quality_failed_row_semantics"] is True
    assert payload["adapter_behavior"]["workflows_bigquery_job_polling_planning"] is True
    assert payload["adapter_behavior"]["workflows_certified_runner_smoke"] is True
    assert payload["adapter_behavior"]["single_contract_smoke"] is True
    assert payload["adapter_behavior"]["project_deployment_runner"] is True
    assert payload["adapter_behavior"]["stable_orchestration_surface"] == "google_workflows"
    assert "polls submitted BigQuery jobs until DONE" in payload["decision"]["reason"]
    assert "promoted GCP deployment orchestration path" in payload["decision"]["planner_behavior"]
    assert "https://cloud.google.com/workflows/docs" in payload["sources"]
    assert payload["required_before_promotion"]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_certified_runner_smoke_report_closes_15c() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-certified-runner-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_certified_runner_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C"
    assert payload["status"] == "PASS"
    assert payload["validated"]["adapter_owned_cli_path"] is True
    assert payload["validated"]["pre_run_reset_data"] is True
    assert payload["validated"]["deploy_run_wait"] is True
    assert payload["validated"]["execution_scoped_readback"] is True
    assert payload["validated"]["repeated_full_project_rerun"] is True
    assert payload["validated"]["run_evidence_scoped_per_execution"] is True
    assert payload["validated"]["quality_evidence_scoped_per_execution"] is True
    assert payload["validated"]["schema_evidence_scoped_per_execution"] is True
    assert payload["validated"]["workflow_resource_cleanup"] is True
    assert payload["promotion_decision"]["decision"] == "PROMOTE_GCP_BQ_15C"
    assert len(payload["runs"]) == 2
    assert payload["runs"][0]["execution_id"] != payload["runs"][1]["execution_id"]
    for run in payload["runs"]:
        assert run["status"] == "SUCCEEDED"
        assert run["wait_state"] == "SUCCEEDED"
        assert run["readback_execution_scoped"] is True
        assert run["readback_execution_id"] == run["execution_id"]
        assert run["target_row_counts"] == [
            {
                "row_count": "3",
                "step_name": "bronze_orders",
                "target_table": "midyear-system-499521-p3.contractforge_gcp_smoke.workflow_bronze_orders",
            },
            {
                "row_count": "2",
                "step_name": "gold_orders_by_status",
                "target_table": "midyear-system-499521-p3.contractforge_gcp_smoke.workflow_gold_orders_by_status",
            },
        ]
        assert len(run["run_evidence"]) == 2
        assert len(run["quality_evidence"]) == 2
        assert len(run["schema_evidence"]) == 2
    assert payload["cleanup"]["status"] == "SUCCEEDED"
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_runner_smoke_report_records_live_generated_runner() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-runner-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_runner_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15B"
    assert payload["status"] == "PASS"
    assert payload["workflow"]["execution_state"] == "SUCCEEDED"
    assert payload["workflow"]["result"]["operation_count"] == 6
    assert payload["workflow"]["result"]["wait_polling_included"] is True
    assert payload["contract_basis"]["manual_workflow_edits"] is False
    assert payload["validated"]["workflow_deployed_from_generated_artifact"] is True
    assert payload["validated"]["bigquery_jobs_polled_with_location"] is True
    assert payload["validated"]["multiline_sql_preserved_as_yaml_literal_blocks"] is True
    assert payload["readback"]["target_counts"] == [
        {"layer": "bronze", "row_count": 3},
        {"layer": "gold", "row_count": 2},
    ]
    assert payload["readback"]["gold_rows"] == [
        {"amount_total": 7.25, "order_count": 1, "status": "new"},
        {"amount_total": 27.25, "order_count": 2, "status": "paid"},
    ]
    assert "GCP-BQ-15C is now closed" in payload["remaining_review_boundary"]
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_command_readback_smoke_report_records_live_readback_command() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-command-readback-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_command_readback_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C3"
    assert payload["status"] == "PASS"
    assert payload["workflow"]["execution_state"] == "SUCCEEDED"
    assert payload["command_path"]["readback_location"] == "us-east1"
    assert payload["fixes_validated"]["platform_executable_resolution"] is True
    assert payload["fixes_validated"]["bq_multiline_sql_flattening"] is True
    assert payload["readback"]["target_row_counts"] == [
        {
            "step_name": "bronze_orders",
            "target_table": "midyear-system-499521-p3.contractforge_gcp_smoke.workflow_bronze_orders",
            "row_count": 3,
        },
        {
            "step_name": "gold_orders_by_status",
            "target_table": "midyear-system-499521-p3.contractforge_gcp_smoke.workflow_gold_orders_by_status",
            "row_count": 2,
        },
    ]
    assert len(payload["readback"]["evidence_tables_present"]) == 6
    assert payload["readback"]["run_evidence_rows"] == 0
    assert payload["review_boundary"]["superseded_by_certified_runner_smoke"] == (
        "docs/reports/gcp-workflows-certified-runner-smoke.json"
    )
    assert payload["review_boundary"]["remaining_before_runner_promotion"] == []
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_runner_evidence_smoke_report_records_run_quality_evidence() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-runner-evidence-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_runner_evidence_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C4"
    assert payload["status"] == "PASS"
    assert payload["workflow"]["execution_state"] == "SUCCEEDED"
    assert payload["validated"]["runner_side_run_evidence"] is True
    assert payload["validated"]["runner_side_quality_evidence"] is True
    assert payload["validated"]["quality_failed_row_semantics"] is True
    assert payload["validated"]["schema_evidence_for_schema_policy_contracts"] is False
    assert payload["readback"]["run_evidence_by_target"] == [
        {
            "target_table": "midyear-system-499521-p3.contractforge_gcp_smoke.workflow_bronze_orders",
            "run_rows": 1,
            "succeeded_rows": 1,
            "failed_rows": 0,
        },
        {
            "target_table": "midyear-system-499521-p3.contractforge_gcp_smoke.workflow_gold_orders_by_status",
            "run_rows": 1,
            "succeeded_rows": 1,
            "failed_rows": 0,
        },
    ]
    assert payload["readback"]["quality_evidence_by_contract"] == [
        {"contract_name": "workflow_bronze_orders", "quality_rows": 1, "passed_rows": 1, "failed_rows": 0},
        {
            "contract_name": "workflow_gold_orders_by_status",
            "quality_rows": 1,
            "passed_rows": 1,
            "failed_rows": 0,
        },
    ]
    assert payload["review_boundary"]["superseded_by_certified_runner_smoke"] == (
        "docs/reports/gcp-workflows-certified-runner-smoke.json"
    )
    assert payload["review_boundary"]["remaining_before_runner_promotion"] == []
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_schema_evidence_smoke_report_records_schema_evidence() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-schema-evidence-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_schema_evidence_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C7"
    assert payload["status"] == "PASS"
    assert payload["workflow"]["execution_state"] == "SUCCEEDED"
    assert payload["workflow"]["readback_status"] == "SUCCEEDED"
    assert payload["validated"]["workflow_schema_evidence_operation"] is True
    assert payload["validated"]["schema_evidence_run_id_is_execution_scoped"] is True
    assert payload["validated"]["schema_evidence_rows_for_schema_policy_contracts"] is True
    assert payload["validated"]["full_in_workflow_schema_drift_enforcement"] is False

    rows = payload["readback"]["schema_evidence_by_target"]
    assert len(rows) == 2
    assert {row["contract_name"] for row in rows} == {
        "workflow_bronze_orders",
        "workflow_gold_orders_by_status",
    }
    assert {row["schema_policy"] for row in rows} == {"permissive"}
    assert {row["status"] for row in rows} == {"SUCCEEDED"}
    assert all(":schema_evidence" in row["run_id"] for row in rows)
    assert all(row["run_id"].startswith("workflows:4557a249-509f-416c-a032-23694e99466b:") for row in rows)
    assert all(row["type_changes_json"] == "[]" for row in rows)
    assert all("planned_no_runtime_drift" in row["schema_changes_json"] for row in rows)
    assert payload["review_boundary"]["superseded_by_certified_runner_smoke"] == (
        "docs/reports/gcp-workflows-certified-runner-smoke.json"
    )
    assert payload["review_boundary"]["remaining_before_runner_promotion"] == []
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_cleanup_command_smoke_report_records_cleanup_surface() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-cleanup-command-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_cleanup_command_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C8"
    assert payload["status"] == "PASS"
    assert payload["validated"]["adapter_owned_cleanup_flag"] is True
    assert payload["validated"]["generated_execution_plan_cleanup_command"] is True
    assert payload["validated"]["workflow_delete_command_executed"] is True
    assert payload["validated"]["missing_workflow_cleanup_is_idempotent"] is True
    assert payload["validated"]["cli_output_redacts_active_account_email"] is True
    assert payload["validated"]["target_table_cleanup"] is False
    assert payload["validated"]["evidence_table_cleanup"] is False
    assert payload["commands"]["cleanup"] == [
        "gcloud",
        "workflows",
        "delete",
        "cf-gcp-workflows-smoke-runner",
        "--project=midyear-system-499521-p3",
        "--location=us-central1",
        "--quiet",
    ]
    assert payload["results"]["first_cleanup"]["status"] == "SUCCEEDED"
    assert payload["results"]["second_cleanup"]["status"] == "SKIPPED"
    assert payload["results"]["second_cleanup"]["reason"] == "workflow_not_found"
    assert payload["results"]["second_cleanup"]["raw_contains_redacted_email"] is True
    assert payload["review_boundary"]["superseded_by_certified_runner_smoke"] == (
        "docs/reports/gcp-workflows-certified-runner-smoke.json"
    )
    assert payload["review_boundary"]["remaining_before_runner_promotion"] == []
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_write_failure_evidence_smoke_report_records_failed_run_evidence() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-write-failure-evidence-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_write_failure_evidence_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C9"
    assert payload["status"] == "PASS"
    assert payload["workflow"]["execution_state"] == "FAILED"
    assert payload["validated"]["workflow_execution_failed"] is True
    assert payload["validated"]["failed_run_evidence_before_raise"] is True
    assert payload["validated"]["failed_run_id_execution_scoped"] is True
    assert payload["validated"]["failed_error_message_non_null"] is True
    assert payload["validated"]["workflow_resource_cleanup"] is True
    assert payload["validated"]["transient_retry_behavior"] is False
    assert payload["validated"]["full_schema_drift_enforcement"] is False
    row = payload["readback"]["run_evidence_rows"][0]
    assert row["run_id"].startswith("workflows:d8d78a62-5f77-4aa0-b513-e5f2c045ba22:")
    assert row["status"] == "FAILED"
    assert row["statement_type"] == "QUERY"
    assert row["error_message"] == "BigQuery Job failed."
    assert payload["review_boundary"]["superseded_by_certified_runner_smoke"] == (
        "docs/reports/gcp-workflows-certified-runner-smoke.json"
    )
    assert payload["review_boundary"]["remaining_before_runner_promotion"] == []
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_target_evidence_cleanup_smoke_report_records_cleanup_data() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-target-evidence-cleanup-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_target_evidence_cleanup_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C10"
    assert payload["status"] == "PASS"
    assert payload["validated"]["generated_cleanup_plan_artifact"] is True
    assert payload["validated"]["adapter_owned_cleanup_data_command"] is True
    assert payload["validated"]["adapter_owned_reset_data_command"] is True
    assert payload["validated"]["target_table_cleanup_statement_scoped"] is True
    assert payload["validated"]["evidence_cleanup_statement_scoped"] is True
    assert payload["validated"]["evidence_rows_removed"] is True
    assert payload["validated"]["dataset_wide_cleanup_not_generated"] is True
    assert payload["validated"]["multi_contract_rerun_execution_readback_certification"] is False
    assert payload["cleanup"]["status"] == "SUCCEEDED"
    assert payload["cleanup"]["query_count"] == 7
    assert payload["cleanup"]["evidence_before_count"] == 6
    assert payload["cleanup"]["evidence_after_count"] == 0
    assert "01_drop_target_bronze_orders_write_failure" in payload["cleanup"]["query_names"]
    assert payload["review_boundary"]["superseded_by_certified_runner_smoke"] == (
        "docs/reports/gcp-workflows-certified-runner-smoke.json"
    )
    assert payload["review_boundary"]["remaining_before_runner_promotion"] == []
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_quality_semantics_smoke_report_records_negative_quality_path() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-quality-semantics-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_quality_semantics_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C5"
    assert payload["status"] == "PASS"
    assert payload["validated"]["workflows_get_query_results_for_quality"] is True
    assert payload["validated"]["passed_quality_evidence"] is True
    assert payload["validated"]["failed_quality_evidence"] is True
    assert payload["validated"]["failed_rows_preserved"] is True
    assert payload["validated"]["workflow_raises_after_failed_quality_evidence"] is True
    assert payload["validated"]["long_workflow_step_ids_stay_unique"] is True
    assert payload["negative_workflow"]["execution_state"] == "FAILED"
    assert payload["negative_workflow"]["error_payload"] == "Quality check failed with 1 failed rows."
    assert payload["negative_workflow"]["quality_evidence_readback"] == [
        {
            "contract_name": "workflow_bronze_orders_quality_failure",
            "status": "FAILED",
            "failed_rows": 1,
            "last_evaluated_at": "2026-06-16 19:40:45",
        }
    ]
    assert payload["contract_basis"]["expected_failed_rows"] == 1
    assert "googleapis.bigquery.v2.jobs.getQueryResults" in " ".join(payload["implementation_notes"])
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_workflows_execution_runid_smoke_report_records_execution_scoped_ids() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-workflows-execution-runid-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_workflows_execution_runid_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-15C6"
    assert payload["status"] == "PASS"
    assert payload["validated"]["workflow_execution_id_from_sys_get_env"] is True
    assert payload["validated"]["run_evidence_uses_execution_scoped_run_id"] is True
    assert payload["validated"]["passed_quality_evidence_uses_execution_scoped_run_id"] is True
    assert payload["validated"]["failed_quality_evidence_uses_execution_scoped_run_id"] is True
    assert payload["positive_workflow"]["execution_state"] == "SUCCEEDED"
    assert payload["negative_workflow"]["execution_state"] == "FAILED"
    assert payload["positive_workflow"]["run_evidence"][0]["run_id"].startswith(
        "workflows:a320ba50-a07c-48cc-bf02-d53fc031938d:"
    )
    assert payload["negative_workflow"]["quality_evidence"] == [
        {
            "run_id": "workflows:c982289e-df34-4614-829e-47ea653dfb0f:bronze_orders_quality_failure:quality",
            "contract_name": "workflow_bronze_orders_quality_failure",
            "status": "FAILED",
            "failed_rows": 1,
        }
    ]
    assert "GOOGLE_CLOUD_WORKFLOW_EXECUTION_ID" in " ".join(payload["implementation_notes"])
    assert "https://docs.cloud.google.com/workflows/docs/reference/environment-variables" in payload["sources"]
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_dataplex_lineage_dq_scope_decision_excludes_native_integrations() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-dataplex-lineage-dq-scope-decision.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_dataplex_lineage_dq_scope_decision"
    assert payload["maturity_gate"] == "GCP-BQ-16"
    assert payload["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert payload["decision"]["stable_final_scope"] == "EXPLICIT_COMMAND_SURFACE_INCLUDED"
    assert set(payload["decision"]["included_surfaces"]) == {
        "dataplex_data_quality_scans",
        "dataplex_data_quality_bigquery_exports",
        "dataplex_lineage_artifact_planning",
        "dataplex_aspect_artifact_planning",
        "dataplex_lineage_aspect_command_surface",
        "native_lineage_event_publication_readback",
        "knowledge_catalog_aspect_modify_entry_readback",
    }
    assert set(payload["decision"]["excluded_surfaces"]) == {
        "automatic_native_lineage_aspect_emission_for_every_contract_run",
    }
    assert payload["adapter_behavior"]["sql_quality_checks"] is True
    assert payload["adapter_behavior"]["bigquery_quality_evidence"] is True
    assert payload["adapter_behavior"]["dataplex_data_scan_artifact_planning"] is True
    assert payload["adapter_behavior"]["dataplex_data_scan_execution_artifact_planning"] is True
    assert payload["adapter_behavior"]["dataplex_data_scans"] is True
    assert payload["adapter_behavior"]["dataplex_data_quality_bigquery_exports"] is True
    assert payload["adapter_behavior"]["dataplex_lineage_artifact_planning"] is True
    assert payload["adapter_behavior"]["dataplex_aspect_artifact_planning"] is True
    assert payload["adapter_behavior"]["dataplex_lineage_aspect_command_surface"] is True
    assert payload["adapter_behavior"]["native_lineage_events"] is True
    assert payload["adapter_behavior"]["knowledge_catalog_aspects"] is True
    assert payload["adapter_behavior"]["automatic_native_lineage_aspect_emission"] is False
    assert "explicit Dataplex lineage/aspect execution/readback as validated" in payload["decision"]["planner_behavior"]
    assert payload["execution_evidence"]["job_state"] == "SUCCEEDED"
    assert payload["execution_evidence"]["rows_scanned"] == 10000
    assert payload["execution_evidence"]["export_rows_read"] == 7
    assert payload["lineage_aspect_execution_evidence"]["lineage_events_read"] == 1
    assert payload["lineage_aspect_execution_evidence"]["modify_entry_readback"] is True
    assert "https://docs.cloud.google.com/dataplex/docs/reference/rest" in payload["sources"]
    assert "https://docs.cloud.google.com/data-catalog/docs/data-lineage" in payload["sources"]
    assert "https://cloud.google.com/data-catalog/docs/reference/data-lineage/rest" in payload["sources"]
    assert "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations/modifyEntry" in payload["sources"]
    assert payload["required_before_promotion"]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_dataplex_lineage_aspects_smoke_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-dataplex-lineage-aspects-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_dataplex_lineage_aspects_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-16B"
    assert payload["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert payload["lineage_execution"]["status"] == "PASS"
    assert payload["lineage_execution"]["readback"]["lineage_events_returned"] == 1
    assert payload["aspect_execution"]["status"] == "PASS"
    assert payload["aspect_execution"]["entry_search"]["total_size"] == 1
    assert payload["aspect_execution"]["modify_entry"]["status"] == "PASS"
    assert payload["validated"]["aspect_type_template_uses_required_field_indexes"] is True
    assert payload["validated"]["native_lineage_events_readback_contains_expected_source_target"] is True


def test_gcp_dataplex_lineage_aspect_runtime_decision_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-dataplex-lineage-aspect-runtime-decision.json").read_text(
        encoding="utf-8"
    )
    payload = json.loads(report)

    assert payload["kind"] == "contractforge_gcp_dataplex_lineage_aspect_runtime_decision"
    assert payload["maturity_gate"] == "GCP-BQ-16B3"
    assert payload["status"] == "PASS"
    assert "explicit adapter command surface" in payload["decision"]
    assert "automatic native Dataplex Data Lineage publication during every contract run" in payload["excluded_surface"]
    assert "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations/modifyEntry" in payload[
        "context7_sources"
    ]
    assert "aspectTypes" in payload["context7_sources"][1]
    assert "gmail.com" not in report.lower()
    assert "marco@" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_hashdiff_cross_adapter_production_parity_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-hashdiff-cross-adapter-production-parity.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["maturity_gate"] == "GCP-BQ-12C"
    assert payload["status"] == "PASS"
    assert payload["decision"] == "HASH_DIFF_UPSERT_PRODUCTION_PARITY_ACCEPTED"
    assert {item["adapter"] for item in payload["accepted_evidence"]} == {
        "contractforge-gcp",
        "contractforge-aws",
        "contractforge-snowflake",
        "contractforge-fabric",
    }
    assert set(payload["remaining_advanced_write_future_scope"]) == {
        "historical cross-adapter production-sized parity",
        "snapshot_reconcile_soft_delete cross-adapter production-sized parity",
    }
    assert payload["no_workaround_code_used"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_dataplex_data_quality_execution_smoke_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-dataplex-data-quality-execution-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["type"] == "dataplex_data_quality"
    assert payload["status"] == "SUCCEEDED"
    assert payload["job"]["state"] == "SUCCEEDED"
    assert payload["readback"]["status"] == "SUCCEEDED"
    assert payload["readback"]["row_count"] == 7
    assert payload["cleanup_readback"] == {"data_scan_found": False, "http_status": 404, "status": "SUCCEEDED"}
    assert {row["rule_name"] for row in payload["readback"]["rows"]} == {
        "customer-id-not-null",
        "segment-not-null",
        "status-not-null",
        "balance-not-null",
        "updated-at-not-null",
        "unique-key",
        "non-negative-balance",
    }
    assert {row["job_rows_scanned"] for row in payload["readback"]["rows"]} == {"10000"}
    assert payload["plan"]["data_scan"]["location"] == "us-east1"
    assert payload["plan"]["rest"]["create"]["body"]["dataQualitySpec"]["rules"][0]["name"] == "customer-id-not-null"
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_authenticated_rest_secret_manager_smoke_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-authenticated-rest-secret-manager-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["planning_status"] == "SUPPORTED_WITH_WARNINGS"
    assert payload["secret_cleanup"] == {
        "cf-gcp-auth-rest-basic-password": "DELETED",
        "gcp-auth-rest-basic-password": "DELETED",
    }
    assert any(item["name"] == "materialize_source" and item["job"]["state"] == "DONE" for item in payload["operations"])
    assert any(item["name"] == "persist_run_evidence" and item["job"]["state"] == "DONE" for item in payload["operations"])
    assert any(item["name"] == "persist_quality_evidence" and item["job"]["state"] == "DONE" for item in payload["operations"])
    assert "passwd" not in report
    assert "{{ secret:" not in report
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_authenticated_rest_http_secret_manager_variants_blocker_report() -> None:
    report = (
        ROOT / "docs" / "reports" / "gcp-auth-rest-http-secret-manager-variants-blocker.json"
    ).read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_auth_rest_http_secret_manager_variants_blocker"
    assert payload["maturity_gate"] == "GCP-BQ-20"
    assert payload["status"] == "SUPERSEDED"
    assert payload["superseded_by"] == "docs/reports/gcp-auth-rest-http-secret-manager-variants-smoke.json"
    assert payload["blocker"]["code"] == "GCLOUD_REAUTH_REQUIRED"
    assert payload["blocker"]["active_account"] == "marco@intentus.dev"
    assert payload["blocker"]["project"] == "midyear-system-499521-p3"
    assert set(payload["attempted_variants"]) == {
        "rest_api bearer_token",
        "rest_api api_key",
        "http_json bearer_token",
        "http_json api_key",
    }
    assert (
        "Local GCP smoke tests cover placeholder resolution before the shared core REST/HTTP reader is called."
        in payload["validated_before_block"]
    )
    assert payload["no_workaround_code_used"] is True
    assert "{{ secret:" not in report
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_authenticated_rest_http_secret_manager_variants_smoke_report() -> None:
    report = (
        ROOT / "docs" / "reports" / "gcp-auth-rest-http-secret-manager-variants-smoke.json"
    ).read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["secret_cleanup"] == {
        "gcp-rest-bearer-token": "DELETED",
        "gcp-rest-api-key": "DELETED",
        "gcp-http-bearer-token": "DELETED",
        "gcp-http-api-key": "DELETED",
    }
    assert {step["name"] for step in payload["steps"]} == {
        "rest_bearer",
        "rest_api_key",
        "http_json_bearer",
        "http_json_api_key",
    }
    for step in payload["steps"]:
        assert step["status"] == "SUCCEEDED"
        assert step["ok"] is True
        operations = step["result"]["operations"]
        assert any(item["name"] == "materialize_source" and item["job"]["output_rows"] == 1 for item in operations)
        assert any(item["name"] == "persist_run_evidence" and item["job"]["state"] == "DONE" for item in operations)
        assert any(item["name"] == "persist_lineage_evidence" and item["job"]["state"] == "DONE" for item in operations)
        assert any(item["name"] == "persist_quality_evidence" and item["job"]["state"] == "DONE" for item in operations)
    assert "cf-rest" not in report
    assert "cf-http" not in report
    assert "{{ secret:" not in report
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()
    assert "intentus" not in report.lower()


def test_gcp_http_text_materialization_local_smoke_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-http-text-materialization-local-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_http_text_materialization_local_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-20"
    assert payload["status"] == "PASS_LOCAL"
    assert payload["source_family"] == "http_text"
    assert payload["contract_semantics"]["parser"] == "line_oriented_text"
    assert payload["promotion_boundary"]["stable_runtime_claim"] == "adapter_runtime_path_only"
    assert payload["promotion_boundary"]["real_account_bigquery_e2e"] is False
    assert "BigQuery local load job receives declared schema_fields" in payload["validated_surface"]
    assert payload["no_workaround_code_used"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_http_text_bigquery_smoke_blocker_report_is_superseded() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-http-text-bigquery-smoke-blocker.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_http_text_bigquery_smoke_blocker"
    assert payload["maturity_gate"] == "GCP-BQ-20"
    assert payload["status"] == "SUPERSEDED"
    assert payload["superseded_by"] == "docs/reports/gcp-http-sources-bigquery-smoke.json"
    assert payload["blocker"]["code"] == "GCLOUD_REAUTH_REQUIRED"
    assert payload["blocker"]["project"] == "midyear-system-499521-p3"
    assert payload["no_workaround_code_used"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_http_sources_bigquery_smoke_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-http-sources-bigquery-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["project"].endswith("examples\\source-expansion\\gcp-http-sources\\project.yaml")
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["environment_key"] == "gcp"
    assert [step["name"] for step in payload["steps"]] == [
        "http_text_countries",
        "http_file_text_countries",
        "http_file_json_todo",
        "http_file_csv_countries",
    ]
    assert all(step["status"] == "SUCCEEDED" and step["ok"] is True for step in payload["steps"])
    output_rows = {
        step["name"]: next(
            operation["job"]["output_rows"]
            for operation in step["result"]["operations"]
            if operation["name"] == "materialize_source"
        )
        for step in payload["steps"]
    }
    assert output_rows == {
        "http_text_countries": 195,
        "http_file_text_countries": 195,
        "http_file_json_todo": 1,
        "http_file_csv_countries": 194,
    }
    assert all(
        any(operation["name"] == "persist_run_evidence" for operation in step["result"]["operations"])
        for step in payload["steps"]
    )
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_http_file_binary_bigquery_smoke_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-http-file-binary-bigquery-smoke.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)

    assert payload["project"].endswith("examples\\source-expansion\\gcp-http-file-binary\\project.yaml")
    assert payload["status"] == "SUCCEEDED"
    assert payload["ok"] is True
    assert payload["executed"] is True
    assert payload["environment_key"] == "gcp"
    assert payload["fixture_server"]["private_http_target_opt_in"] == "CONTRACTFORGE_ALLOW_PRIVATE_HTTP_TARGETS=1"
    assert payload["fixture_server"]["formats"] == ["avro", "orc", "parquet"]
    assert payload["fixture_server"]["row_count_per_fixture"] == 3
    assert [step["name"] for step in payload["steps"]] == [
        "http_file_avro_orders",
        "http_file_orc_orders",
        "http_file_parquet_orders",
    ]
    assert all(step["status"] == "SUCCEEDED" and step["ok"] is True for step in payload["steps"])
    output_rows = {
        step["name"]: next(
            operation["job"]["output_rows"]
            for operation in step["result"]["operations"]
            if operation["name"] == "materialize_source"
        )
        for step in payload["steps"]
    }
    assert output_rows == {
        "http_file_avro_orders": 3,
        "http_file_orc_orders": 3,
        "http_file_parquet_orders": 3,
    }
    assert all(
        any(operation["name"] == "persist_lineage_evidence" for operation in step["result"]["operations"])
        for step in payload["steps"]
    )
    assert all(
        any(
            operation["name"] == "quality" and operation["job"]["result_rows"] == [{"failed_rows": "0"}]
            for operation in step["result"]["operations"]
        )
        for step in payload["steps"]
    )
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()
    assert "intentus" not in report.lower()


def test_gcp_http_file_materialization_local_smoke_report() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-http-file-materialization-local-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_http_file_materialization_local_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-20"
    assert payload["status"] == "PASS_LOCAL"
    assert payload["source_family"] == "http_file"
    assert payload["contract_semantics"]["supported_formats"] == [
        "avro",
        "csv",
        "json",
        "jsonl",
        "ndjson",
        "orc",
        "parquet",
        "text",
    ]
    assert payload["contract_semantics"]["unsupported_without_format"] is True
    assert "avro, orc and parquet formats pass fetched bytes directly to BigQuery local load jobs" in payload["validated_surface"]
    assert payload["promotion_boundary"]["real_account_bigquery_e2e"] is False
    assert payload["no_workaround_code_used"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_governance_stable_scope_decision_records_included_and_excluded_surfaces() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-governance-stable-scope-decision.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_governance_stable_scope_decision"
    assert payload["maturity_gate"] == "GCP-BQ-17"
    assert payload["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert payload["decision"]["stable_final_scope"] == "GOVERNANCE_READBACK_AND_RECONCILIATION_INCLUDED"
    assert set(payload["decision"]["included_surfaces"]) == {
        "bigquery_row_access_policy_apply_readback_enforcement",
        "bigquery_direct_column_data_policy_masking",
        "data_catalog_policy_tag_column_access",
        "bigquery_table_column_descriptions",
        "governance_ledger_artifact_planning",
        "governance_ledger_evidence_write_readback",
        "governance_ledger_reconciliation_artifact_planning",
        "governance_ledger_reconciliation_command_readback",
        "run_quality_annotation_failed_run_evidence",
    }
    assert set(payload["decision"]["excluded_surfaces"]) == {
        "tag_based_masking",
        "policy_tag_backed_data_masking",
        "dataplex_or_knowledge_catalog_aspects",
        "overwrite_retention_for_row_policies_masks_and_policy_tags",
        "automatic_governance_policy_repair_or_delete",
    }
    assert payload["adapter_behavior"]["governance_e2e"] is True
    assert payload["adapter_behavior"]["row_access_policy_smoke"] is True
    assert payload["adapter_behavior"]["direct_column_data_masking_smoke"] is True
    assert payload["adapter_behavior"]["policy_tag_column_access_smoke"] is True
    assert payload["adapter_behavior"]["governance_ledger_artifact_planning"] is True
    assert payload["adapter_behavior"]["governance_ledger_evidence_write_readback"] is True
    assert payload["adapter_behavior"]["governance_ledger_reconciliation_artifact_planning"] is True
    assert payload["adapter_behavior"]["governance_ledger_reconciliation_command_readback"] is True
    assert payload["adapter_behavior"]["tag_based_masking"] is False
    assert payload["adapter_behavior"]["automatic_governance_repair"] is False
    assert "non-mutating reconciliation readback" in payload["decision"]["planner_behavior"]
    assert "docs/reports/gcp-governance-ledger-evidence-smoke.json" in payload["evidence"]
    assert "docs/reports/gcp-governance-ledger-reconciliation-plan.json" in payload["evidence"]
    assert "docs/reports/gcp-governance-ledger-reconciliation-smoke.json" in payload["evidence"]
    assert "https://docs.cloud.google.com/bigquery/docs/access-control" in payload["sources"]
    assert payload["required_before_promotion"]
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_governance_ledger_evidence_smoke_report_records_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-governance-ledger-evidence-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_governance_ledger_evidence_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-17B1"
    assert payload["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert payload["execution"]["status"] == "SUCCEEDED"
    assert any(operation["name"] == "persist_governance_evidence" for operation in payload["execution"]["operations"])
    assert payload["readback"]["row_count"] == 3
    assert set(payload["readback"]["surfaces"]) == {
        "bigquery_description",
        "bigquery_row_access_policy",
        "knowledge_catalog_or_dataplex_aspect",
    }
    assert payload["readback"]["raw_email_hits"] == 0
    assert payload["readback"]["redacted_email_hits"] == 1
    assert payload["no_workaround_code_used"] is True
    assert "analysts@example.com" not in report
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_governance_ledger_reconciliation_plan_report_records_command_boundary() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-governance-ledger-reconciliation-plan.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_governance_ledger_reconciliation_plan"
    assert payload["maturity_gate"] == "GCP-BQ-17B2"
    assert payload["status"] == "PASS"
    assert "deterministic non-mutating reconciliation artifact" in payload["scope"]["included"]
    assert "automatic policy repair" in payload["scope"]["excluded"]
    assert payload["decision"]["promotion_boundary"].startswith("This closes reconciliation artifact planning and the non-mutating command surface")
    assert payload["no_workaround_code_used"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_governance_ledger_reconciliation_smoke_report_records_readback() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-governance-ledger-reconciliation-smoke.json").read_text(
        encoding="utf-8"
    )
    payload = __import__("json").loads(report)

    assert payload["kind"] == "contractforge_gcp_governance_ledger_reconciliation_smoke"
    assert payload["maturity_gate"] == "GCP-BQ-17B"
    assert payload["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert payload["adapter_command_surface"]["mutating"] is False
    assert payload["validated_surfaces"]["row_access_policy"]["status"] == "IN_SYNC"
    assert payload["validated_surfaces"]["direct_data_policy"]["status"] == "IN_SYNC"
    assert payload["validated_surfaces"]["policy_tag"]["status"] == "IN_SYNC"
    assert payload["validated_surfaces"]["descriptions"]["status"] == "IN_SYNC"
    assert payload["validated_surfaces"]["governance_evidence"]["row_count"] == 3
    assert "automatic policy repair" in payload["review_boundary"]["excluded"]
    assert payload["no_workaround_code_used"] is True
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()


def test_gcp_stable_surface_evidence_manifest_is_complete() -> None:
    report = (ROOT / "docs" / "reports" / "gcp-stable-surface-evidence.json").read_text(encoding="utf-8")
    payload = __import__("json").loads(report)
    pyproject = (ROOT / "adapters" / "gcp" / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "adapters" / "gcp" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert payload["kind"] == "contractforge_gcp_stable_surface_evidence"
    assert payload["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert payload["supported_surface_ready"] is True
    assert payload["stable_final"] is True
    assert payload["stability_criteria"] == "docs/specs/gcp-capability-parity.md"
    assert any(command["name"] == "strict_final_boundary" for command in payload["verification_commands"])
    csv_project = next(project for project in payload["real_validation_projects"] if project["name"] == "gcp_bigquery_csv_smoke")
    assert "redacted source-review artifacts" in csv_project["validated_surfaces"]
    assert {project["name"] for project in payload["real_validation_projects"]} == {
        "gcp_bigquery_csv_smoke",
        "gcp_bigquery_file_formats_smoke",
        "gcp_bigquery_upsert_smoke",
        "gcp_bigquery_bronze_to_gold_smoke",
        "gcp_bigquery_schema_policy_smoke",
        "gcp_bigquery_schema_policy_strict_smoke",
        "gcp_bigquery_schema_policy_permissive_smoke",
        "gcp_bigquery_schema_policy_type_change_smoke",
        "gcp_bigquery_schema_policy_sql_source_smoke",
        "gcp_bigquery_schema_policy_gcs_source_smoke",
        "gcp_schema_policy_type_mutation_decision",
        "gcp_bigquery_governance_smokes",
        "gcp_governance_ledger_evidence_smoke",
        "gcp_governance_ledger_reconciliation_smoke",
        "gcp_bigquery_error_evidence_smoke",
        "gcp_biglake_iceberg_smoke",
        "gcp_raw_iceberg_registration_smoke",
        "gcp_http_sources_bigquery_smoke",
        "gcp_http_file_binary_bigquery_smoke",
        "gcp_authenticated_rest_secret_manager_smoke",
        "gcp_auth_rest_http_secret_manager_variants_smoke",
        "gcp_bigquery_advanced_write_smoke",
        "gcp_bigquery_advanced_write_preflight_smoke",
        "gcp_bigquery_historical_edge_smoke",
        "gcp_bigquery_snapshot_variant_smoke",
        "gcp_bigquery_hashdiff_production_benchmark",
        "gcp_hashdiff_cross_adapter_production_parity",
        "gcp_bigquery_advanced_write_production_benchmark",
        "gcp_workflows_runner_smoke",
        "gcp_workflows_command_readback_smoke",
        "gcp_workflows_runner_evidence_smoke",
        "gcp_workflows_quality_semantics_smoke",
        "gcp_workflows_execution_runid_smoke",
        "gcp_workflows_schema_evidence_smoke",
        "gcp_workflows_cleanup_command_smoke",
        "gcp_workflows_write_failure_evidence_smoke",
        "gcp_workflows_target_evidence_cleanup_smoke",
        "gcp_workflows_certified_runner_smoke",
        "gcp_dataplex_data_quality_execution_smoke",
        "gcp_dataplex_lineage_aspects_smoke",
        "gcp_dataplex_lineage_aspect_runtime_decision",
        "gcp_confluent_kafka_dataflow_source_promotion_smoke",
    }
    assert {boundary["code"] for boundary in payload["accepted_review_boundaries"]} == {
        "GCP_ADVANCED_WRITE_MODES_REVIEW",
        "GCP_STREAMING_REVIEW",
        "GCP_AUTHENTICATED_REST_HTTP_REVIEW",
        "GCP_SOURCE_FAMILY_PROMOTION_REVIEW",
        "GCP_DEPLOYMENT_ORCHESTRATION_REVIEW",
        "GCP_SCHEMA_POLICY_REVIEW",
        "GCP_DATAPLEX_LINEAGE_DQ_REVIEW",
        "GCP_GOVERNANCE_LEDGER_REVIEW",
    }
    assert "bounded BigQuery job polling" in payload["summary"]["basis"]
    assert "non-JDBC source-family promotion plans" in payload["summary"]["basis"]
    assert "advanced write-mode review" in payload["summary"]["basis"]
    assert "hash-diff changed-wave and null/duplicate key preflight smokes" in payload["summary"]["basis"]
    assert "hash-diff production benchmark and overlap serialization" in payload["summary"]["basis"]
    assert "accepted cross-adapter hash_diff_upsert production parity" in payload["summary"]["basis"]
    assert "historical/snapshot production benchmarks" in payload["summary"]["basis"]
    assert "historical delete-expression and late-arriving reject smokes" in payload["summary"]["basis"]
    assert "snapshot complete-source reactivation and tombstone smokes" in payload["summary"]["basis"]
    assert "live http_text and generic http_file text/JSON/CSV project execution" in payload["summary"]["basis"]
    assert "live http_file Avro/ORC/Parquet pass-through load materialization" in payload["summary"]["basis"]
    assert "authenticated REST/HTTP Secret Manager runtime resolution" in payload["summary"]["basis"]
    assert "live REST API-key and HTTP JSON bearer/API-key Secret Manager variants" in payload["summary"]["basis"]
    assert "Dataplex data-quality create plus execution/readback command" in payload["summary"]["basis"]
    assert "native Dataplex lineage/aspect planning plus explicit command surface" in payload["summary"]["basis"]
    assert "executable Dataflow source-promotion command/readback surface" in payload["summary"]["basis"]
    assert "live Confluent Dataflow streaming provider evidence" in payload["summary"]["basis"]
    assert "native Dataplex data-quality DataScan execution/export readback" in payload["summary"]["basis"]
    assert "explicit Dataplex runtime decision" in payload["summary"]["basis"]
    assert "governance-ledger evidence write/readback" in payload["summary"]["basis"]
    assert "governance ledger/reconciliation" in payload["summary"]["basis"]
    assert "raw Iceberg BigLake registration command/readback" in payload["summary"]["basis"]
    dataplex_smoke = next(
        project for project in payload["real_validation_projects"] if project["name"] == "gcp_dataplex_data_quality_execution_smoke"
    )
    assert dataplex_smoke["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert dataplex_smoke["evidence"] == "docs/reports/gcp-dataplex-data-quality-execution-smoke.json"
    dataplex_runtime_decision = next(
        project
        for project in payload["real_validation_projects"]
        if project["name"] == "gcp_dataplex_lineage_aspect_runtime_decision"
    )
    assert dataplex_runtime_decision["status"] == "DECIDED"
    assert dataplex_runtime_decision["evidence"] == "docs/reports/gcp-dataplex-lineage-aspect-runtime-decision.json"
    auth_smoke = next(
        project for project in payload["real_validation_projects"] if project["name"] == "gcp_authenticated_rest_secret_manager_smoke"
    )
    assert auth_smoke["status"] == "PASS"
    assert auth_smoke["evidence"] == "docs/reports/gcp-authenticated-rest-secret-manager-smoke.json"
    auth_variants_smoke = next(
        project
        for project in payload["real_validation_projects"]
        if project["name"] == "gcp_auth_rest_http_secret_manager_variants_smoke"
    )
    assert auth_variants_smoke["status"] == "PASS"
    assert auth_variants_smoke["evidence"] == "docs/reports/gcp-auth-rest-http-secret-manager-variants-smoke.json"
    assert "temporary secret cleanup" in auth_variants_smoke["validated_surfaces"]
    binary_http_smoke = next(
        project
        for project in payload["real_validation_projects"]
        if project["name"] == "gcp_http_file_binary_bigquery_smoke"
    )
    assert binary_http_smoke["status"] == "PASS"
    assert binary_http_smoke["evidence"] == "docs/reports/gcp-http-file-binary-bigquery-smoke.json"
    assert "contract-only generic http_file Parquet project step" in binary_http_smoke["validated_surfaces"]
    raw_iceberg_smoke = next(
        project
        for project in payload["real_validation_projects"]
        if project["name"] == "gcp_raw_iceberg_registration_smoke"
    )
    assert raw_iceberg_smoke["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert raw_iceberg_smoke["evidence"] == "docs/reports/gcp-raw-iceberg-registration-smoke.json"
    assert "registered table query readback" in raw_iceberg_smoke["validated_surfaces"]
    streaming_smoke = next(
        project
        for project in payload["real_validation_projects"]
        if project["name"] == "gcp_confluent_kafka_dataflow_source_promotion_smoke"
    )
    assert streaming_smoke["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert streaming_smoke["evidence"] == "docs/reports/gcp-confluent-kafka-dataflow-source-promotion-smoke.json"
    assert "zero-DLQ reconciliation" in streaming_smoke["validated_surfaces"]
    governance_evidence_smoke = next(
        project
        for project in payload["real_validation_projects"]
        if project["name"] == "gcp_governance_ledger_evidence_smoke"
    )
    assert governance_evidence_smoke["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert governance_evidence_smoke["evidence"] == "docs/reports/gcp-governance-ledger-evidence-smoke.json"
    assert "principal redaction before SQL execution and readback" in governance_evidence_smoke["validated_surfaces"]
    governance_reconciliation_smoke = next(
        project
        for project in payload["real_validation_projects"]
        if project["name"] == "gcp_governance_ledger_reconciliation_smoke"
    )
    assert governance_reconciliation_smoke["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert governance_reconciliation_smoke["evidence"] == "docs/reports/gcp-governance-ledger-reconciliation-smoke.json"
    assert "non-mutating comparison against contract intent" in governance_reconciliation_smoke["validated_surfaces"]
    governance_smoke = next(
        project for project in payload["real_validation_projects"] if project["name"] == "gcp_bigquery_governance_smokes"
    )
    assert "governance reconciliation planning artifact" in governance_smoke["validated_surfaces"]
    assert "repeated Workflows full-project rerun execution/readback" in payload["summary"]["basis"]
    assert "`bq` readback/reset/cleanup command paths" in payload["summary"]["basis"]
    assert {gate["id"] for gate in payload["next_promotion_gates"]} == {
        "GCP-BQ-12D",
        "GCP-BQ-20",
    }
    assert all(gate["status"] == "FUTURE" for gate in payload["next_promotion_gates"])
    future_gates = {gate["id"]: gate for gate in payload["next_promotion_gates"]}
    assert "docs/reports/cross-adapter-production-run-scope-check.json" in future_gates["GCP-BQ-12D"]["evidence"]
    assert "Development Status :: 4 - Beta" in pyproject
    assert "stable BigQuery batch surface" in changelog
    assert "redacted source-review JSON and Markdown artifacts" in changelog
    assert "non-JDBC source-family promotion paths" in changelog
    assert "source-family promotion-plan JSON artifacts" in changelog
    assert "authenticated REST/HTTP Secret Manager review artifacts and runtime resolution" in changelog
    assert "deployment manifest execution-readiness" in changelog
    assert "historical delete-expression expiration and late-arriving reject failure" in changelog
    assert "production-sized GCP BigQuery `hash_diff_upsert` benchmark" in changelog
    assert "Accepted `hash_diff_upsert` cross-adapter production parity" in changelog
    assert "production-sized GCP BigQuery advanced-write benchmark" in changelog
    assert "snapshot complete-source blocking, same-hash reactivation, tombstone and replay smokes" in changelog
    assert "gmail.com" not in report.lower()
    assert "antero" not in report.lower()
