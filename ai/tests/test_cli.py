import json
from pathlib import Path

import yaml

from contractforge_ai.cli import main


def test_review_cli_outputs_json(tmp_path: Path, capsys):
    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders.csv
  read:
    schema: "order_id STRING"
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
quality_rules:
  not_null: [order_id]
annotations:
  table:
    description: Orders
operations:
  technical_owner: data-engineering
""",
        encoding="utf-8",
    )

    exit_code = main(["review", str(contract), "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "PASS"' in output


def test_analyze_control_tables_cli_outputs_markdown(tmp_path: Path, capsys):
    evidence = tmp_path / "control-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "runs": [
                    {"run_id": "1", "status": "FAILED", "target_table": "main.silver.orders"},
                    {"run_id": "2", "status": "SUCCESS", "target_table": "main.silver.orders"},
                ],
                "quality": [{"rule_name": "not_null", "status": "FAILED"}],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["analyze-control-tables", "--input", str(evidence), "--format", "markdown"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "# ContractForge AI Operational Review" in output
    assert "observability.failure_rate" in output
    assert "observability.quality.failures" in output


def test_analyze_control_tables_cli_outputs_html(tmp_path: Path, capsys):
    evidence = tmp_path / "control-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "runs": [{"run_id": "1", "status": "SUCCESS", "target_table": "glue_catalog.bronze.orders"}],
                "quality": [{"rule_name": "not_null", "status": "PASSED"}],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["analyze-control-tables", "--input", str(evidence), "--format", "html"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "<!doctype html>" in output
    assert "ContractForge AI Operational Review" in output


def test_knowledge_index_cli_builds_and_queries_context(tmp_path: Path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "quality.md").write_text(
        "# Quality\n\nUse quarantine for row-level quality rules and fail for set-level checks.\n",
        encoding="utf-8",
    )
    index_path = tmp_path / "knowledge.json"

    build_exit = main(["knowledge-index", "build", str(docs), "--root", str(tmp_path), "--output", str(index_path), "--format", "json"])
    build_output = capsys.readouterr().out
    query_exit = main(
        [
            "knowledge-index",
            "query",
            "--index",
            str(index_path),
            "--query",
            "quarantine quality rules",
            "--format",
            "json",
        ]
    )
    query_output = capsys.readouterr().out

    assert build_exit == 0
    assert '"status": "BUILT"' in build_output
    assert query_exit == 0
    assert '"source_path": "docs/quality.md"' in query_output
    assert "quarantine" in query_output


def test_route_task_cli_returns_prompt_and_context(tmp_path: Path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "shape.md").write_text(
        "Use transform.shape to flatten structs, parse JSON payloads and explode arrays only after review.",
        encoding="utf-8",
    )
    index_path = tmp_path / "knowledge.json"

    build_exit = main(["knowledge-index", "build", str(docs), "--root", str(tmp_path), "--output", str(index_path)])
    capsys.readouterr()
    route_exit = main(
        [
            "route-task",
            "--intent",
            "Generate a shape for nested JSON with arrays",
            "--knowledge-index",
            str(index_path),
            "--format",
            "json",
        ]
    )
    route_output = capsys.readouterr().out
    payload = json.loads(route_output)

    assert build_exit == 0
    assert route_exit == 0
    assert payload["task"] == "shape_suggestion"
    assert payload["prompt_name"] is None
    assert payload["context_results"]


def test_route_task_cli_can_prefer_http_only_provider(capsys):
    route_exit = main(
        [
            "route-task",
            "--intent",
            "Suggest annotations and quality rules for an orders schema.",
            "--prefer-http-only",
            "--format",
            "json",
        ]
    )
    route_output = capsys.readouterr().out
    payload = json.loads(route_output)

    assert route_exit == 0
    assert payload["task"] == "metadata_suggestion"
    assert payload["provider_routing"]["selected"]["databricks_dependency_mode"] == "http_only"


def test_route_task_cli_outputs_html(capsys):
    exit_code = main(
        [
            "route-task",
            "--intent",
            "Plan a ContractForge AWS Glue project from S3 to Iceberg.",
            "--format",
            "html",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "<!doctype html>" in output
    assert "ContractForge" in output


def test_validate_artifact_cli_validates_contract(tmp_path: Path, capsys):
    contract = tmp_path / "orders.ingestion.yaml"
    contract.write_text(
        """
_metadata:
  draft: true
  review_required: true
source:
  type: connector
  connector: files
  path: /landing/orders
target:
  catalog: main
  schema: bronze
  table: b_orders
mode: scd0_append
operations:
  technical_owner: data-engineering
""".lstrip(),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "validate-artifact",
            "--contract",
            str(contract),
            "--skip-contractforge",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "READY"
    assert payload["ready"] is True


def test_validate_artifact_cli_returns_nonzero_for_invalid_model_output(tmp_path: Path, capsys):
    output = tmp_path / "model.json"
    output.write_text('{"kind": "project_plan"}', encoding="utf-8")

    exit_code = main(
        [
            "validate-artifact",
            "--model-output",
            str(output),
            "--prompt",
            "project.plan.enrichment.v1",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "INVALID"


def test_validate_artifact_cli_accepts_project_root(tmp_path: Path, capsys):
    _write_cli_project_root(tmp_path)

    exit_code = main(["validate-artifact", "--project-root", str(tmp_path), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "READY"
    assert payload["ready"] is True
    assert {item["kind"] for item in payload["files"]} >= {"project", "environment", "connection", "ingestion_bundle"}


def test_critique_output_cli_downgrades_low_evidence_output(tmp_path: Path, capsys):
    output = tmp_path / "output.json"
    output.write_text(
        json.dumps(
            {
                "kind": "project_plan",
                "summary": "This is production-ready.",
                "recommendations": ["Deploy it."],
                "evidence": [],
                "decisions_required": ["Confirm keys."],
                "review_required": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["critique-output", "--input", str(output), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "NEEDS_DECISIONS"
    assert any(finding["code"] == "critique.ready_claim_with_decisions" for finding in payload["findings"])


def test_critique_output_cli_outputs_html(tmp_path: Path, capsys):
    output = tmp_path / "output.json"
    output.write_text(
        json.dumps(
            {
                "kind": "project_plan",
                "summary": "Needs adapter planning.",
                "recommendations": ["Run deterministic validation."],
                "evidence": ["Project folder exists."],
                "decisions_required": ["Select target adapter."],
                "review_required": True,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["critique-output", "--input", str(output), "--format", "html"])
    rendered = capsys.readouterr().out

    assert exit_code == 1
    assert "<!doctype html>" in rendered
    assert "ContractForge AI Critique Report" in rendered
    assert "critique" in rendered


def test_review_cli_supports_bundle_metadata(tmp_path: Path, capsys):
    contract = tmp_path / "b_orders.ingestion.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders.csv
  read:
    schema: "order_id STRING"
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
quality_rules:
  not_null: [order_id]
""",
        encoding="utf-8",
    )
    (tmp_path / "b_orders.annotations.yaml").write_text(
        """
annotations:
  table:
    description: Orders
""",
        encoding="utf-8",
    )
    (tmp_path / "b_orders.operations.yaml").write_text(
        """
operations:
  technical_owner: data-engineering
""",
        encoding="utf-8",
    )

    exit_code = main(["review", str(contract), "--bundle", "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "PASS"' in output
    assert '"bundle_review": true' in output


def test_review_cli_with_ai_offline_keeps_deterministic_result(tmp_path: Path, capsys):
    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders.csv
  read:
    schema: "order_id STRING"
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
quality_rules:
  not_null: [order_id]
annotations:
  table:
    description: Orders
operations:
  technical_owner: data-engineering
""",
        encoding="utf-8",
    )

    exit_code = main(["review", str(contract), "--with-ai", "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "PASS"' in output
    assert '"ai_enrichment"' in output
    assert '"status": "SKIPPED"' in output


def test_review_cli_fail_on_high(tmp_path: Path):
    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: json
  path: /tmp/orders
target:
  catalog: main
  schema: silver
  table: orders
mode: scd1_hash_diff
""",
        encoding="utf-8",
    )

    assert main(["review", str(contract), "--fail-on", "high"]) == 1


def test_review_cli_fail_on_code(tmp_path: Path):
    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders
target:
  catalog: main
  schema: silver
  table: orders
mode: scd1_hash_diff
merge_keys: [order_id]
quality_rules:
  not_null: [status]
""",
        encoding="utf-8",
    )

    assert main(["review", str(contract), "--fail-on-code", "write.keys.nullable"]) == 1


def test_review_cli_outputs_markdown(tmp_path: Path, capsys):
    contract = tmp_path / "orders.yaml"
    contract.write_text(
        """
source:
  type: connector
  connector: files
  format: csv
  path: /tmp/orders
target:
  catalog: main
  schema: silver
  table: orders
mode: scd1_hash_diff
merge_keys: [order_id]
quality_rules:
  not_null: [status]
""",
        encoding="utf-8",
    )

    exit_code = main(["review", str(contract), "--format", "markdown"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "## ContractForge AI Review" in output
    assert "| Severity | Code | Location | Recommendation |" in output
    assert "`write.keys.nullable`" in output


def test_project_plan_cli_writes_artifacts(tmp_path: Path, capsys):
    plan = tmp_path / "plan.yaml"
    out_dir = tmp_path / "out"
    plan.write_text(
        """
name: orders
target: contractforge-yaml
artifacts:
  - path: README.md
    kind: markdown
    content: "# Orders\\n"
report:
  title: Orders project
  summary: Generated project scaffold.
""",
        encoding="utf-8",
    )

    exit_code = main(["project-plan", "--input", str(plan), "--output-dir", str(out_dir)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "created"' in output
    assert (out_dir / "README.md").read_text(encoding="utf-8") == "# Orders\n"


def test_generate_project_cli_writes_contractforge_yaml_project(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    out_dir = tmp_path / "generated"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate-project",
            "--target",
            "contractforge-yaml",
            "--schema",
            str(schema),
            "--project-name",
            "Orders",
            "--connector",
            "files",
            "--source-path",
            "/landing/orders",
            "--target-catalog",
            "main",
            "--target-schema",
            "bronze",
            "--target-table",
            "b_orders",
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "created"' in output
    assert (out_dir / "contracts/bronze/b_orders.ingestion.yaml").exists()
    assert (out_dir / "PROJECT_REVIEW.html").exists()
    assert not (out_dir / "DECISIONS.md").exists()
    assert not (out_dir / "RUNBOOK.md").exists()
    assert not (out_dir / "VALIDATION.md").exists()


def test_generate_project_cli_writes_databricks_dab_project(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    out_dir = tmp_path / "generated_dab"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate-project",
            "--target",
            "databricks-dab",
            "--schema",
            str(schema),
            "--project-name",
            "Orders DAB",
            "--connector",
            "files",
            "--source-path",
            "/landing/orders",
            "--target-catalog",
            "main",
            "--target-schema",
            "bronze",
            "--target-table",
            "b_orders",
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "created"' in output
    assert (out_dir / "databricks.yml").exists()
    assert (out_dir / "resources/jobs.yml").exists()
    assert (out_dir / "notebooks/run_bronze_b_orders.py").exists()
    assert (out_dir / "PROJECT_REVIEW.html").exists()
    assert not (out_dir / "RUNBOOK.md").exists()
    assert not (out_dir / "VALIDATION.md").exists()


def test_generate_project_cli_accepts_naming_file(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    naming = tmp_path / "naming.yaml"
    out_dir = tmp_path / "generated_named"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )
    naming.write_text(
        """
policy: caf_default
contract_basename: orders_contract
bundle_name: orders-bundle
job_name: Orders Ingestion
task_key: orders_ingestion_task
""".lstrip(),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate-project",
            "--target",
            "databricks-dab",
            "--schema",
            str(schema),
            "--project-name",
            "Orders",
            "--connector",
            "files",
            "--source-path",
            "/landing/orders",
            "--target-catalog",
            "main",
            "--target-schema",
            "bronze",
            "--target-table",
            "b_orders",
            "--naming-file",
            str(naming),
            "--output-dir",
            str(out_dir),
        ]
    )
    capsys.readouterr()

    assert exit_code == 0
    assert (out_dir / "contracts/bronze/orders_contract.ingestion.yaml").exists()
    ingestion = yaml.safe_load((out_dir / "contracts/bronze/orders_contract.ingestion.yaml").read_text(encoding="utf-8"))
    jobs = yaml.safe_load((out_dir / "resources/jobs.yml").read_text(encoding="utf-8"))

    assert ingestion["target"]["table"] == "b_orders"
    assert ingestion["naming"]["contract_basename"] == "orders_contract"
    assert jobs["resources"]["jobs"]["orders_ingestion"]["tasks"][0]["task_key"] == "orders_ingestion_task"


def test_generate_project_cli_writes_dbt_project(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    out_dir = tmp_path / "generated_dbt"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate-project",
            "--target",
            "dbt",
            "--schema",
            str(schema),
            "--project-name",
            "Orders dbt",
            "--connector",
            "files",
            "--source-path",
            "/landing/orders",
            "--target-catalog",
            "main",
            "--target-schema",
            "bronze",
            "--target-table",
            "b_orders",
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "created"' in output
    assert (out_dir / "dbt_project.yml").exists()
    assert (out_dir / "models/sources.yml").exists()
    assert (out_dir / "models/staging/stg_b_orders.sql").exists()
    assert (out_dir / "models/staging/stg_b_orders.yml").exists()
    assert (out_dir / "PROJECT_REVIEW.html").exists()
    assert not (out_dir / "RUNBOOK.md").exists()
    assert not (out_dir / "VALIDATION.md").exists()


def test_generate_project_cli_writes_contractforge_python_project(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    out_dir = tmp_path / "generated_python"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate-project",
            "--target",
            "contractforge-python",
            "--schema",
            str(schema),
            "--project-name",
            "Orders Python",
            "--connector",
            "files",
            "--source-path",
            "/landing/orders",
            "--target-catalog",
            "main",
            "--target-schema",
            "bronze",
            "--target-table",
            "b_orders",
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "created"' in output
    assert (out_dir / "pyproject.toml").exists()
    assert (out_dir / "src/orders_python/run_ingestion.py").exists()
    assert (out_dir / "contracts/bronze/b_orders.ingestion.yaml").exists()
    assert (out_dir / "PROJECT_REVIEW.html").exists()
    assert not (out_dir / "RUNBOOK.md").exists()
    assert not (out_dir / "VALIDATION.md").exists()


def test_generate_project_cli_writes_classic_pyspark_project(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    out_dir = tmp_path / "generated_classic"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate-project",
            "--target",
            "classic-pyspark",
            "--schema",
            str(schema),
            "--project-name",
            "Orders Classic",
            "--connector",
            "files",
            "--source-path",
            "/landing/orders",
            "--target-catalog",
            "main",
            "--target-schema",
            "bronze",
            "--target-table",
            "b_orders",
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "created"' in output
    assert (out_dir / "classic_pyspark/run_bronze_b_orders.py").exists()
    assert (out_dir / "notebooks/classic_run_bronze_b_orders.py").exists()
    assert (out_dir / "contracts/bronze/b_orders.ingestion.yaml").exists()
    assert (out_dir / "PROJECT_REVIEW.html").exists()
    assert not (out_dir / "MIGRATION.md").exists()
    assert not (out_dir / "RUNBOOK.md").exists()
    assert not (out_dir / "VALIDATION.md").exists()


def test_profiles_cli_outputs_json(capsys):
    exit_code = main(["profiles", "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"name": "databricks-job"' in output
    assert '"name": "local-cli"' in output


def test_profile_cli_validates_config_file(tmp_path: Path, capsys):
    config = tmp_path / "profile.json"
    config.write_text('{"catalog": "main"}', encoding="utf-8")

    exit_code = main(["profile", "databricks-job", "--config", str(config), "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "WARN"' in output
    assert '"ctrl_schema"' in output


def test_environment_report_cli_outputs_json(monkeypatch, capsys):
    def fake_discover_environment():
        class Report:
            def to_dict(self):
                return {
                    "python_version": "3.11.0",
                    "platform": "test",
                    "packages": {"contractforge": True},
                    "commands": {"git": True},
                    "provider_environment": {"OPENAI_API_KEY": {"configured": True, "value": "[REDACTED]"}},
                    "databricks": {"cli_available": True},
                    "warnings": [],
                }

        return Report()

    monkeypatch.setattr("contractforge_ai.cli_onboarding_commands.discover_environment", fake_discover_environment)

    exit_code = main(["environment-report", "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"python_version": "3.11.0"' in output
    assert "secret" not in output.lower()
    assert "[REDACTED]" in output


def test_explain_run_cli_with_ai_offline_keeps_deterministic_result(tmp_path: Path, capsys):
    evidence = tmp_path / "failed.json"
    evidence.write_text(
        """
{
  "run": {
    "status": "FAILED",
    "source_connector": "http_file",
    "runtime_type": "serverless",
    "error_message": "Temporary failure in name resolution"
  }
}
""",
        encoding="utf-8",
    )

    exit_code = main(["explain-run", "--input", str(evidence), "--with-ai", "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"primary_category": "network_or_egress"' in output
    assert '"ai_enrichment"' in output
    assert '"status": "SKIPPED"' in output


def test_init_cli_dry_run_outputs_planned_artifacts(tmp_path: Path, capsys):
    exit_code = main(
        [
            "init",
            "--profile",
            "databricks-job",
            "--catalog",
            "main",
            "--ctrl-schema",
            "ops",
            "--output-dir",
            str(tmp_path),
            "--dry-run",
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"path": "contractforge-ai.yaml"' in output
    assert '"path": "SETUP_REPORT.md"' in output
    assert not (tmp_path / "contractforge-ai.yaml").exists()


def test_init_cli_writes_onboarding_files(tmp_path: Path, capsys):
    exit_code = main(
        [
            "init",
            "--profile",
            "local-cli",
            "--output-dir",
            str(tmp_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Wrote onboarding artifacts" in output
    assert (tmp_path / "contractforge-ai.yaml").exists()
    assert (tmp_path / "SETUP_REPORT.md").exists()


def test_agent_instructions_cli_dry_run_outputs_planned_assets(tmp_path: Path, capsys):
    exit_code = main(
        [
            "agent-instructions",
            "--target",
            "all",
            "--project-name",
            "Orders Platform",
            "--output-dir",
            str(tmp_path),
            "--dry-run",
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"AGENT_INSTRUCTIONS.md"' in output
    assert '".github/copilot-instructions.md"' in output
    assert not (tmp_path / "AGENT_INSTRUCTIONS.md").exists()


def test_agent_instructions_cli_writes_target_assets(tmp_path: Path, capsys):
    exit_code = main(
        [
            "agent-instructions",
            "--target",
            "claude",
            "--project-name",
            "Orders Platform",
            "--validation-command",
            "contractforge-ai review contracts/silver/orders.yaml --fail-on high",
            "--output-dir",
            str(tmp_path),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Wrote onboarding artifacts" in output
    assert (tmp_path / "AGENT_INSTRUCTIONS.md").exists()
    assert (tmp_path / "AGENT_CHECKLIST.md").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert "contractforge-ai review contracts/silver/orders.yaml --fail-on high" in (
        tmp_path / "AGENT_CHECKLIST.md"
    ).read_text(encoding="utf-8")


def test_plan_project_cli_outputs_structured_json(capsys):
    exit_code = main(
        [
            "plan-project",
            "--intent",
            "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders.",
            "--schema",
            "schemas/orders.json",
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"connector": "http_file"' in output
    assert '"target_table": "b_orders"' in output
    assert '"contractforge-yaml"' in output


def test_plan_project_cli_reads_intent_file(tmp_path: Path, capsys):
    intent_file = tmp_path / "intent.txt"
    intent_file.write_text(
        "Build a Databricks silver project from abfss://landing/orders into main.silver.orders using upsert.",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "plan-project",
            "--intent-file",
            str(intent_file),
            "--schema",
            "schemas/orders.json",
            "--format",
            "markdown",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "# Project Planning Result" in output
    assert "databricks-dab" in output


def test_plan_project_cli_with_ai_offline_attaches_skipped_enrichment(capsys):
    exit_code = main(
        [
            "plan-project",
            "--intent",
            "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders.",
            "--schema",
            "schemas/orders.json",
            "--with-ai",
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"ai_enrichment"' in output
    assert '"status": "SKIPPED"' in output


def test_guided_project_cli_refuses_to_write_when_decisions_remain(tmp_path: Path, capsys):
    schema = tmp_path / "orders.json"
    out_dir = tmp_path / "guided"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "guided-project",
            "--intent",
            "Create a silver ingestion from s3a://landing/orders into main.silver.orders using scd1_hash_diff.",
            "--schema",
            str(schema),
            "--output-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 2
    assert '"status": "NEEDS_DECISIONS"' in output
    assert '"project": null' in output
    assert not out_dir.exists()


def test_generate_cli_writes_intent_first_medallion_project(tmp_path: Path, capsys):
    schema = tmp_path / "orders.json"
    out_dir = tmp_path / "generated"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}, {"name": "amount", "type": "DOUBLE"}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate",
            "--prompt",
            "Use table main.raw.orders_sample and create a bronze to gold project. Gold final columns: order_id, amount.",
            "--schema",
            str(schema),
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"generation"' in output
    assert (out_dir / "AI_REVIEW.html").exists()
    assert (out_dir / "contracts/bronze/b_orders.ingestion.yaml").exists()
    assert (out_dir / "contracts/silver/s_orders.ingestion.yaml").exists()
    assert (out_dir / "contracts/gold/g_orders.ingestion.yaml").exists()
    assert not (out_dir / "README.md").exists()


def test_generate_cli_accepts_aws_target_and_adds_aws_environment(tmp_path: Path, capsys):
    schema = tmp_path / "orders.json"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}, {"name": "amount", "type": "DOUBLE"}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate",
            "--prompt",
            "Create a bronze project from s3://landing/orders into analytics.bronze.b_orders.",
            "--schema",
            str(schema),
            "--target",
            "aws-glue-iceberg",
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["intent"]["output_target"] == "aws-glue-iceberg"
    assert payload["intent"]["platform_hints"] == ["aws"]
    artifact_paths = {artifact["path"] for artifact in payload["project"]["artifacts"]}
    assert "project.yaml" in artifact_paths
    assert "environments/aws.environment.yaml" in artifact_paths


def test_review_architecture_cli_detects_governed_concepts(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "kernel.py").write_text(
        "class StateSignature: pass\nclass PolicyEngine: pass\nclass AuditTrail: pass\nclass ContextRegistry: pass\n",
        encoding="utf-8",
    )

    exit_code = main(["review-architecture", str(repo), "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"score"' in output
    assert "Typed intent/signature model" in output
    assert "Policy gate before execution/generation" in output


def test_review_architecture_cli_outputs_html(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (src / "kernel.py").write_text(
        "class StateSignature: pass\nclass PolicyEngine: pass\nclass AuditTrail: pass\n",
        encoding="utf-8",
    )

    exit_code = main(["review-architecture", str(repo), "--format", "html"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "<!doctype html>" in output
    assert "Governed Architecture Review" in output


def test_guided_project_cli_writes_when_review_required_is_allowed(tmp_path: Path, capsys):
    schema = tmp_path / "orders.json"
    out_dir = tmp_path / "guided"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "guided-project",
            "--intent",
            "Create a silver ingestion from s3a://landing/orders into main.silver.orders using scd1_hash_diff.",
            "--schema",
            str(schema),
            "--allow-review-required",
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"guided_project"' in output
    assert '"status": "created"' in output
    assert (out_dir / "contracts/silver/orders.ingestion.yaml").exists()
    assert (out_dir / "contracts/silver/orders.annotations.yaml").exists()


def test_guided_project_cli_uses_context_dir_when_schema_is_missing(tmp_path: Path, capsys):
    context_dir = tmp_path / "context"
    context_dir.mkdir()
    (context_dir / "orders.json").write_text(
        json.dumps([{"order_id": "A-1", "amount": 10.5}]),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "guided-project",
            "--intent",
            "Create a bronze ingestion from /landing/orders into main.bronze.b_orders",
            "--context-dir",
            str(context_dir),
            "--runtime",
            "serverless",
            "--allow-review-required",
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "created"' in output
    assert (out_dir / "AI_REVIEW.html").exists()
    assert not (out_dir / "CONTEXT.md").exists()
    assert (out_dir / "context/context-package.json").exists()
    assert (out_dir / "context/inferred-schema-profile.yaml").exists()
    assert (out_dir / "contracts/bronze/b_orders.ingestion.yaml").exists()
    assert not (out_dir / "DECISIONS.md").exists()
    assert not (out_dir / "README.md").exists()


def test_guided_project_cli_dry_run_explicit_dab_target(tmp_path: Path, capsys):
    schema = tmp_path / "orders.json"
    out_dir = tmp_path / "guided_dab"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "guided-project",
            "--intent",
            "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders.",
            "--schema",
            str(schema),
            "--target",
            "databricks-dab",
            "--output-dir",
            str(out_dir),
            "--dry-run",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"path": "databricks.yml"' in output
    assert '"path": "resources/jobs.yml"' in output
    assert '"status": "created"' in output
    assert not (out_dir / "databricks.yml").exists()


def test_guided_project_cli_reads_requirements_yaml(tmp_path: Path, capsys):
    schema = tmp_path / "orders.json"
    requirements = tmp_path / "requirements.yaml"
    out_dir = tmp_path / "guided_requirements"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )
    requirements.write_text(
        f"""
intent: Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders.
schema_path: {schema.as_posix()}
preferred_target: contractforge-yaml
default_layer: bronze
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "guided-project",
            "--requirements",
            str(requirements),
            "--output-dir",
            str(out_dir),
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"guided_project"' in output
    assert (out_dir / "contracts/bronze/b_orders.ingestion.yaml").exists()


def test_guided_project_cli_flags_override_requirements(tmp_path: Path, capsys):
    schema = tmp_path / "orders.json"
    requirements = tmp_path / "requirements.json"
    out_dir = tmp_path / "guided_requirements_override"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )
    requirements.write_text(
        json.dumps(
            {
                "intent": "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders.",
                "schema_path": str(schema),
                "preferred_target": "contractforge-yaml",
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "guided-project",
            "--requirements",
            str(requirements),
            "--target",
            "databricks-dab",
            "--output-dir",
            str(out_dir),
            "--dry-run",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"selected_target": "databricks-dab"' in output
    assert '"path": "databricks.yml"' in output
    assert not (out_dir / "databricks.yml").exists()


def test_guided_project_cli_requirements_need_schema_path(tmp_path: Path, capsys):
    requirements = tmp_path / "requirements.yaml"
    requirements.write_text(
        "intent: Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders.\n",
        encoding="utf-8",
    )

    try:
        main(["guided-project", "--requirements", str(requirements), "--format", "json"])
    except SystemExit as exc:
        exit_code = exc.code
    else:
        exit_code = 0
    error = capsys.readouterr().err

    assert exit_code == 2
    assert "schema_path" in error


def test_eval_enrichment_cli_outputs_quality_report(tmp_path: Path, capsys):
    deterministic = tmp_path / "deterministic.json"
    enrichment = tmp_path / "enrichment.json"
    deterministic.write_text(
        '{"status": "NEEDS_DECISIONS", "decisions_required": [{"question": "Confirm merge keys."}]}',
        encoding="utf-8",
    )
    enrichment.write_text(
        """
{
  "status": "ENRICHED",
  "provider": "fake",
  "data": {
    "kind": "project_plan",
    "summary": "Use YAML and preserve merge-key review.",
    "recommendations": ["Confirm merge keys."],
    "evidence": ["Deterministic planner required merge-key review."],
    "decisions_required": ["Confirm merge keys."],
    "confidence": 0.82,
    "review_required": true
  }
}
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "eval-enrichment",
            "--deterministic",
            str(deterministic),
            "--enrichment",
            str(enrichment),
            "--kind",
            "project_plan",
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"status": "PASS"' in output
    assert '"score": 1.0' in output


def test_eval_provider_cli_skips_offline_provider(capsys):
    exit_code = main(["eval-provider", "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"provider": "offline"' in output
    assert '"status": "SKIPPED"' in output
    assert '"provider.offline"' in output


def test_route_provider_cli_outputs_ranked_recommendations(capsys):
    exit_code = main(
        [
            "route-provider",
            "--task",
            "project_planning",
            "--require-strict-schema",
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"selected"' in output
    assert '"structured_output_strategy": "strict_schema"' in output
    assert '"deepseek"' in output


def test_eval_prompts_cli_outputs_json(capsys):
    exit_code = main(["eval-prompts", "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"case": "review-redacts-secret-like-contract-values"' in output
    assert '"status": "PASS"' in output


def test_eval_prompts_cli_lists_templates(capsys):
    exit_code = main(["eval-prompts", "--list-templates"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "review.enrichment.v1" in output
    assert "project.plan.enrichment.v1" in output


def test_validate_output_cli_accepts_valid_model_output(tmp_path: Path, capsys):
    output_file = tmp_path / "model-output.json"
    output_file.write_text(
        """
{
  "kind": "review",
  "summary": "Merge keys need quality protection.",
  "recommendations": ["Add not_null."],
  "evidence": ["Deterministic finding."],
  "assumptions": [],
  "decisions_required": [],
  "confidence": 0.8,
  "review_required": true
}
""",
        encoding="utf-8",
    )

    exit_code = main(["validate-output", "--prompt", "review.enrichment.v1", "--input", str(output_file)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Structured output validation: PASS" in output


def test_validate_output_cli_fails_invalid_model_output(tmp_path: Path, capsys):
    output_file = tmp_path / "model-output.json"
    output_file.write_text('{"kind": "review"}', encoding="utf-8")

    exit_code = main(["validate-output", "--prompt", "review.enrichment.v1", "--input", str(output_file), "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "structured_output.required_missing" in output


def _write_cli_project_root(root: Path) -> None:
    (root / "connections").mkdir()
    (root / "environments").mkdir()
    contract_dir = root / "contracts" / "bronze" / "orders"
    contract_dir.mkdir(parents=True)
    (root / "project.yaml").write_text(
        """
name: orders_project
environments:
  databricks: environments/databricks.environment.yaml
connections:
  source: connections/source.yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false
execution_order:
  - name: bronze_orders
    contracts:
      databricks: contracts/bronze/orders/orders.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )
    (root / "environments" / "databricks.environment.yaml").write_text(
        """
name: dev
adapter: databricks
evidence:
  catalog: main
  schema: ops
""".lstrip(),
        encoding="utf-8",
    )
    (root / "connections" / "source.yaml").write_text(
        """
source:
  type: connector
  connector: files
  path: /landing/orders
  system: orders
""".lstrip(),
        encoding="utf-8",
    )
    (contract_dir / "orders.ingestion.yaml").write_text(
        """
source:
  type: connection
  connection_path: project://connections/source.yaml
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
