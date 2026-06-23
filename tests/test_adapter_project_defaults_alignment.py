from __future__ import annotations

from pathlib import Path

from contractforge_aws.cli.support import load_contract_input as load_aws_contract_input
from contractforge_databricks.cli_io import load_contract_input as load_databricks_contract_input
from contractforge_fabric.deployment import deploy_fabric_project
from contractforge_gcp.deployment.project import deploy_gcp_project
from contractforge_snowflake.runtime.project import _load_contract_input as load_snowflake_contract_input


def test_aws_loads_project_defaults_for_simple_project_contract(tmp_path) -> None:
    contract_path = _write_simple_project_contract(tmp_path, "aws", catalog="lake", schema="bronze")

    contract, _environment = load_aws_contract_input(contract_path)

    assert contract["target"] == {"table": "orders", "catalog": "lake", "schema": "bronze"}


def test_databricks_loads_project_defaults_for_simple_project_contract(tmp_path) -> None:
    contract_path = _write_simple_project_contract(tmp_path, "databricks", catalog="workspace", schema="bronze")

    contract, _environment = load_databricks_contract_input(contract_path)

    assert contract["target"] == {"table": "orders", "catalog": "workspace", "schema": "bronze"}


def test_snowflake_loads_project_defaults_for_simple_project_contract(tmp_path) -> None:
    contract_path = _write_simple_project_contract(tmp_path, "snowflake", catalog="CONTRACTFORGE_TEST_DB", schema="PUBLIC")

    contract, _environment = load_snowflake_contract_input(contract_path)

    assert contract["target"] == {"table": "orders", "catalog": "CONTRACTFORGE_TEST_DB", "schema": "PUBLIC"}


def test_fabric_deploy_project_uses_project_defaults_for_simple_contract(tmp_path) -> None:
    project_path = _write_simple_project_contract(
        tmp_path,
        "fabric",
        catalog="workspace",
        schema="bronze",
        environment_body="""
parameters:
  fabric:
    workspace_id: workspace-1
    lakehouse_id: lakehouse-1
""",
    ).parents[2] / "project.yaml"

    result = deploy_fabric_project(project_path, dry_run=True)

    assert result.ok is True
    assert result.deployment_records[0]["target_table"] == "workspace.bronze.orders"


def test_gcp_deploy_project_uses_project_defaults_for_simple_contract(tmp_path) -> None:
    project_path = _write_simple_project_contract(
        tmp_path,
        "gcp",
        catalog="test-project",
        schema="bronze",
        environment_body="""
parameters:
  gcp:
    project_id: test-project
    dataset: bronze
    location: US
""",
    ).parents[2] / "project.yaml"

    result = deploy_gcp_project(project_path, dry_run=True)

    assert result.ok is True
    assert result.steps[0].target_table == "test-project.bronze.orders"


def _write_simple_project_contract(
    root: Path,
    adapter: str,
    *,
    catalog: str,
    schema: str,
    environment_body: str | None = None,
) -> Path:
    contract_path = root / "contracts" / adapter / "orders.yaml"
    environment_path = root / "environments" / f"{adapter}.environment.yaml"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    environment_path.parent.mkdir(parents=True, exist_ok=True)
    environment_path.write_text((environment_body or f"name: dev\nadapter: {adapter}\n").lstrip(), encoding="utf-8")
    contract_path.write_text(
        """
source:
  type: table
  table: raw.orders
target:
  table: orders
layer: bronze
mode: append
""".lstrip(),
        encoding="utf-8",
    )
    (root / "project.yaml").write_text(
        f"""
name: {adapter}_defaults_alignment
environments:
  {adapter}: environments/{adapter}.environment.yaml
defaults:
  adapters:
    {adapter}:
      catalog: {catalog}
      schemas:
        bronze: {schema}
execution_order:
  - name: bronze_orders
    layer: bronze
    contracts:
      {adapter}: contracts/{adapter}/orders.yaml
""".lstrip(),
        encoding="utf-8",
    )
    return contract_path
