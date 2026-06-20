from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace

from contractforge_ai.cli import main
from contractforge_ai.adapter_validation.registry import AdapterPlannerSpec, DEFAULT_ADAPTER_PLANNERS
from contractforge_ai.project_structure import validate_project_structure


def test_validate_project_structure_accepts_canonical_project(tmp_path) -> None:
    _write_valid_project(tmp_path)

    result = validate_project_structure(tmp_path)

    assert result.status == "READY"
    assert result.ready is True
    assert {item.kind for item in result.files} >= {"project", "environment", "connection", "ingestion_bundle"}


def test_validate_project_structure_rejects_legacy_flat_ingestion_fields(tmp_path) -> None:
    ingestion = _write_valid_project(tmp_path)
    ingestion.write_text(
        """
source:
  type: table
  table: raw.orders
target_table: orders
target_schema: bronze
catalog: main
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )

    result = validate_project_structure(tmp_path)

    assert result.status == "INVALID"
    assert {finding.code for finding in result.findings} >= {"project_structure.ingestion.legacy_field"}


def test_validate_project_structure_rejects_wrapped_split_sections(tmp_path) -> None:
    ingestion = _write_valid_project(tmp_path)
    operations = ingestion.with_name("orders.operations.yaml")
    operations.write_text(
        """
operations:
  criticality: high
""".lstrip(),
        encoding="utf-8",
    )

    result = validate_project_structure(tmp_path)

    assert result.status == "INVALID"
    assert any(finding.code == "project_structure.ingestion_bundle.invalid" for finding in result.findings)


def test_validate_project_structure_requires_connection_file(tmp_path) -> None:
    _write_valid_project(tmp_path)
    (tmp_path / "connections" / "postgres.yaml").unlink()

    result = validate_project_structure(tmp_path)

    assert result.status == "INVALID"
    assert any(finding.code == "project_structure.connection.missing" for finding in result.findings)


def test_validate_project_structure_marks_inline_connection_secret_unsafe(tmp_path) -> None:
    _write_valid_project(tmp_path)
    (tmp_path / "connections" / "postgres.yaml").write_text(
        """
source:
  type: connector
  connector: postgres
  options:
    url: jdbc:postgresql://host/db
auth:
  type: basic
  username: app
  password: plain-text-password
""".lstrip(),
        encoding="utf-8",
    )

    result = validate_project_structure(tmp_path)

    assert result.status == "UNSAFE"
    assert any(finding.code == "project_structure.connection.inline_secret" for finding in result.findings)


def test_validate_project_structure_cli_outputs_json(tmp_path, capsys) -> None:
    _write_valid_project(tmp_path)

    assert main(["validate-project-structure", str(tmp_path), "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "READY"
    assert payload["ready"] is True


def test_validate_project_structure_cli_outputs_rich_html(tmp_path, capsys) -> None:
    _write_valid_project(tmp_path)

    assert main(["validate-project-structure", str(tmp_path), "--format", "html"]) == 0

    output = capsys.readouterr().out
    assert "<!doctype html>" in output
    assert "ContractForge Project Structure Validation" in output
    assert "Readiness Analysis" in output
    assert "Project Files" in output
    assert "Evidence And Adapter Planning" in output
    assert "finding-card" in output
    assert "evidence-card" in output
    assert "Raw Validation Payload" in output
    assert "Consolidated Validation Markdown" not in output
    assert "**" not in output


def test_validate_project_structure_can_run_optional_adapter_planning(tmp_path, monkeypatch) -> None:
    _write_valid_project(tmp_path)
    calls = _install_fake_databricks_adapter(
        monkeypatch,
        status="SUPPORTED_WITH_WARNINGS",
        warnings=(SimpleNamespace(code="review_env", message="Review environment-specific settings."),),
        artifacts={
            "orders.databricks.yml": "resources: {}",
            "orders.strategy.json": "{}",
            "orders.evidence.sql": "select 1",
        },
    )

    result = validate_project_structure(tmp_path, adapters=("databricks",))

    assert result.status == "READY_WITH_WARNINGS"
    assert result.ready is True
    assert len(calls) == 1
    assert any(finding.code == "adapter.databricks.planning.warning.review_env" for finding in result.findings)
    adapter_evidence = next(item for item in result.evidence if item.source == "contractforge_databricks")
    assert adapter_evidence.value["artifact_count"] == 3
    assert adapter_evidence.value["artifact_types"] == ["databricks_asset_bundle", "evidence_sql", "strategy_json"]


def test_validate_project_structure_plans_generic_contract_paths_for_requested_adapters(tmp_path, monkeypatch) -> None:
    _write_generic_project(tmp_path)
    calls = _install_fake_databricks_adapter(monkeypatch, status="SUPPORTED")

    result = validate_project_structure(tmp_path, adapters=("databricks",))

    assert result.status == "READY"
    assert len(calls) == 1
    assert any(item.kind == "ingestion_bundle" and item.adapter is None for item in result.files)
    assert any(item.source == "contractforge_databricks" for item in result.evidence)


def _write_valid_project(root) -> object:
    (root / "connections").mkdir()
    (root / "environments").mkdir()
    bundle = root / "contracts" / "databricks" / "bronze" / "orders"
    bundle.mkdir(parents=True)
    ingestion = bundle / "orders.ingestion.yaml"
    (root / "project.yaml").write_text(
        """
name: orders_project
environments:
  databricks: environments/databricks.environment.yaml
connections:
  postgres: connections/postgres.yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false
execution_order:
  - name: bronze_orders
    contracts:
      databricks: contracts/databricks/bronze/orders/orders.ingestion.yaml
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
    (root / "connections" / "postgres.yaml").write_text(
        """
source:
  type: connector
  connector: postgres
  system: demo
  options:
    url: "{{ secret:scope/jdbc-url }}"
    driver: org.postgresql.Driver
auth:
  type: basic
  username: "{{ secret:scope/user }}"
  password: "{{ secret:scope/password }}"
read:
  fetchsize: 1000
""".lstrip(),
        encoding="utf-8",
    )
    ingestion.write_text(
        """
source:
  type: connection
  connection_path: project://connections/postgres.yaml
  table: public.orders
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    ingestion.with_name("orders.annotations.yaml").write_text(
        """
table:
  description: Bronze orders
columns:
  order_id:
    description: Business order id
""".lstrip(),
        encoding="utf-8",
    )
    ingestion.with_name("orders.operations.yaml").write_text(
        """
criticality: medium
ownership:
  technical_owner: data-platform
""".lstrip(),
        encoding="utf-8",
    )
    return ingestion


def _write_generic_project(root) -> object:
    (root / "connections").mkdir()
    (root / "environments").mkdir()
    bundle = root / "contracts" / "bronze"
    bundle.mkdir(parents=True)
    ingestion = bundle / "orders.ingestion.yaml"
    (root / "project.yaml").write_text(
        """
name: orders_project
environments:
  databricks: environments/databricks.environment.yaml
connections:
  postgres: connections/postgres.yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false
execution_order:
  - name: bronze_orders
    contracts:
      databricks: contracts/bronze/orders.ingestion.yaml
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
    (root / "connections" / "postgres.yaml").write_text(
        """
source:
  type: connector
  connector: postgres
  system: demo
  options:
    url: "{{ secret:scope/jdbc-url }}"
auth:
  type: basic
  username: "{{ secret:scope/user }}"
  password: "{{ secret:scope/password }}"
""".lstrip(),
        encoding="utf-8",
    )
    ingestion.write_text(
        """
source:
  type: connection
  connection_path: project://connections/postgres.yaml
  table: public.orders
target:
  catalog: main
  schema: bronze
  table: orders
mode: scd0_append
""".lstrip(),
        encoding="utf-8",
    )
    ingestion.with_name("orders.annotations.yaml").write_text(
        """
table:
  description: Bronze orders
""".lstrip(),
        encoding="utf-8",
    )
    ingestion.with_name("orders.operations.yaml").write_text(
        """
criticality: medium
""".lstrip(),
        encoding="utf-8",
    )
    return ingestion


def _install_fake_databricks_adapter(
    monkeypatch,
    *,
    status: str,
    warnings=(),
    blockers=(),
    artifacts: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    package_name = "contractforge_databricks"
    module_name = "contractforge_databricks.api"
    package = types.ModuleType(package_name)
    package.__path__ = []
    module = types.ModuleType(module_name)
    calls = []

    def planner(contract, **kwargs):
        calls.append({"contract": contract, "kwargs": kwargs})
        return SimpleNamespace(status=status, warnings=warnings, blockers=blockers)

    def renderer(contract, **kwargs):
        return SimpleNamespace(artifacts=artifacts or {})

    module.plan_databricks_contract = planner
    module.render_databricks_contract = renderer
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, module_name, module)
    monkeypatch.setitem(
        DEFAULT_ADAPTER_PLANNERS,
        "databricks",
        AdapterPlannerSpec(
            name="databricks",
            module=module_name,
            function="plan_databricks_contract",
            render_function="render_databricks_contract",
        ),
    )
    return calls
