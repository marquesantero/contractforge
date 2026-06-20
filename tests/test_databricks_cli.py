import json
from pathlib import Path

from contractforge_databricks.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_presets_list(capsys) -> None:
    assert main(["presets", "list", "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)
    names = {item["name"] for item in payload}

    assert "silver_historical" in names
    assert "runtime_databricks_serverless" in names


def test_cli_templates_show_metadata(capsys) -> None:
    assert main(["templates", "show", "silver_jdbc_scd1_upsert", "--metadata-only", "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["name"] == "silver_jdbc_scd1_upsert"
    assert payload["category"] == "silver"
    assert payload["files"] == ["ingestion", "annotations", "operations", "access"]


def test_cli_templates_write_split_bundle(tmp_path, capsys) -> None:
    output = tmp_path / "contracts" / "silver" / "s_orders"

    assert main(["templates", "write", "silver_jdbc_scd1_upsert", "--output", str(output), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert (tmp_path / "contracts" / "silver" / "s_orders.ingestion.yaml").exists()
    assert (tmp_path / "contracts" / "silver" / "s_orders.access.yaml").exists()


def test_cli_templates_wizard_can_write_selected_bundle(tmp_path, capsys) -> None:
    output = tmp_path / "contracts" / "bronze" / "b_orders"

    assert (
        main(
            [
                "templates",
                "wizard",
                "--layer",
                "bronze",
                "--source",
                "incremental_files",
                "--output",
                str(output),
                "--indent",
                "0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert payload["selected_template"] == payload["recommendations"][0]["name"]
    assert (tmp_path / "contracts" / "bronze" / "b_orders.ingestion.yaml").exists()
    assert (tmp_path / "contracts" / "bronze" / "b_orders.operations.yaml").exists()


def test_cli_dashboard_writes_artifacts(tmp_path, capsys) -> None:
    assert (
        main(
            [
                "dashboard",
                "--catalog",
                "ops",
                "--schema",
                "audit",
                "--lookback-days",
                "14",
                "--output-dir",
                str(tmp_path),
                "--indent",
                "0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert (tmp_path / "control_tables_dashboard.sql").exists()
    assert "`ops`.`audit`.`ctrl_ingestion_runs`" in (tmp_path / "control_tables_dashboard.sql").read_text()


def test_cli_stabilization_report_is_strict_final_ready(capsys) -> None:
    assert main(["stabilization-report"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert payload["supported_surface_ready"] is True
    assert payload["stable_final"] is True
    assert payload["stability_criteria"] == "docs/specs/databricks-ga-criteria.md"
    assert payload["waiver_registry"] == "docs/specs/databricks-ga-waivers.md"
    assert payload["evidence_manifest"] == "docs/reports/databricks-stable-surface-evidence.json"
    assert {item["name"] for item in payload["real_validation_projects"]} >= {
        "databricks_reference_runtime_suite",
        "databricks_same_contract_e2e",
        "databricks_confluent_kafka_available_now",
    }
    assert {item["decision"] for item in payload["accepted_review_boundaries"]} == {"EXCLUDED_FROM_STABLE_FINAL"}
    assert payload["next_promotion_gates"] == []


def test_cli_stabilization_report_strict_final_passes_for_documented_scope(capsys) -> None:
    assert main(["stabilization-report", "--strict-final"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stable_final"] is True


def test_databricks_stable_surface_manifest_is_complete() -> None:
    manifest = json.loads((ROOT / "docs" / "reports" / "databricks-stable-surface-evidence.json").read_text(encoding="utf-8"))

    assert manifest["kind"] == "contractforge_databricks_stable_surface_evidence"
    assert manifest["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert manifest["supported_surface_ready"] is True
    assert manifest["stable_final"] is True
    assert manifest["stability_criteria"] == "docs/specs/databricks-ga-criteria.md"
    assert manifest["waiver_registry"] == "docs/specs/databricks-ga-waivers.md"
    assert {project["name"] for project in manifest["real_validation_projects"]} >= {
        "databricks_reference_runtime_suite",
        "databricks_same_contract_e2e",
        "databricks_confluent_kafka_available_now",
    }
    assert {boundary["decision"] for boundary in manifest["accepted_review_boundaries"]} == {"EXCLUDED_FROM_STABLE_FINAL"}


def test_cli_render_contract_writes_artifacts(tmp_path, capsys) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "source": {"type": "incremental_files", "path": "s3://bucket/orders", "format": "json"},
                "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
                "mode": "scd0_append",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "artifacts"

    assert main(["render", str(contract), "--output-dir", str(output), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert (output / "main_bronze_orders.review.md").exists()


def test_cli_render_split_bundle_uses_environment_contract(tmp_path, capsys) -> None:
    base = tmp_path / "contracts" / "bronze" / "b_orders"
    base.parent.mkdir(parents=True)
    base.with_suffix(".ingestion.yaml").write_text(
        """
source:
  type: table
  table: main.raw.orders
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    base.with_suffix(".environment.yaml").write_text(
        """
name: dev
adapter: databricks
evidence:
  catalog: audit
  schema: ops
""".lstrip(),
        encoding="utf-8",
    )
    output = tmp_path / "artifacts"

    assert main(["render", str(base.with_suffix(".ingestion.yaml")), "--output-dir", str(output), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert "`audit`.`ops`.`ctrl_ingestion_runs`" in (output / "main_bronze_orders.evidence_ddl.sql").read_text()


def test_cli_maintenance_ctrl_retention(capsys) -> None:
    assert (
        main(
            [
                "maintenance",
                "ctrl-retention",
                "--catalog",
                "ops",
                "--schema",
                "audit",
                "--retention-days",
                "30",
                "--target",
                "runs",
                "--vacuum",
                "--indent",
                "0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "DRY_RUN"
    assert payload["plan"][0]["target"] == "runs"
    assert "DELETE FROM `ops`.`audit`.`ctrl_ingestion_runs`" in payload["plan"][0]["commands"][0]


def test_cli_maintenance_cost_report(capsys) -> None:
    assert (
        main(
            [
                "maintenance",
                "cost-report",
                "--catalog",
                "ops",
                "--schema",
                "audit",
                "--lookback-days",
                "14",
                "--group-by",
                "target_table",
                "--dbu-per-hour",
                "2.0",
                "--currency-per-dbu",
                "0.5",
                "--success-only",
                "--limit",
                "25",
                "--indent",
                "0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "QUERY_ONLY"
    assert payload["limit"] == 25
    assert payload["cost_model"]["hourly_rate"] == 1.0
    assert "FROM `ops`.`audit`.`ctrl_ingestion_runs`" in payload["query"]
    assert "AND status = 'SUCCESS'" in payload["query"]


def test_cli_governance_preview_writes_databricks_artifacts(tmp_path, capsys) -> None:
    base = tmp_path / "contracts" / "silver" / "s_customers"
    _write_split_governance_bundle(base)
    output = tmp_path / "review"

    assert main(["governance-preview", str(base.with_suffix(".ingestion.yaml")), "--output-dir", str(output), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "SUCCESS"
    assert (output / "s_customers.governance.sql").exists()
    assert "COMMENT ON TABLE `main`.`silver`.`customers`" in (output / "s_customers.governance.sql").read_text()
    assert "INSERT INTO `audit`.`ops`.`ctrl_ingestion_operations`" in (output / "s_customers.operations_evidence.sql").read_text()


def test_cli_governance_apply_plan_is_reviewable_sql(tmp_path, capsys) -> None:
    base = tmp_path / "contracts" / "silver" / "s_customers"
    _write_split_governance_bundle(base)

    assert main(["governance-apply-plan", str(base.with_suffix(".ingestion.yaml")), "--indent", "0"]) == 0

    payload = json.loads(capsys.readouterr().out)
    sql = payload["s_customers.governance_apply_plan.sql"]

    assert "ContractForge Databricks governance apply plan" in sql
    assert "GRANT SELECT ON TABLE `main`.`silver`.`customers` TO `analysts`" in sql
    assert "INSERT INTO `audit`.`ops`.`ctrl_ingestion_operations`" in sql


def _write_split_governance_bundle(base) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    (base.with_suffix(".ingestion.yaml")).write_text(
        """
source:
  type: table
  table: main.raw.customers
target:
  catalog: main
  schema: silver
  table: customers
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    (base.with_suffix(".annotations.yaml")).write_text(
        """
target:
  catalog: main
  schema: silver
  table: customers
table:
  description: Customer table
  tags:
    domain: crm
columns:
  email:
    description: Email address
""".lstrip(),
        encoding="utf-8",
    )
    (base.with_suffix(".operations.yaml")).write_text(
        """
target:
  catalog: main
  schema: silver
  table: customers
criticality: high
expected_frequency: daily
freshness_sla_minutes: 60
alert_on_failure: true
""".lstrip(),
        encoding="utf-8",
    )
    (base.with_suffix(".access.yaml")).write_text(
        """
target:
  catalog: main
  schema: silver
  table: customers
access_policy:
  mode: validate_only
grants:
  - principal: analysts
    privileges: [SELECT]
""".lstrip(),
        encoding="utf-8",
    )
    (base.with_suffix(".environment.yaml")).write_text(
        """
name: dev
adapter: databricks
evidence:
  catalog: audit
  schema: ops
""".lstrip(),
        encoding="utf-8",
    )
