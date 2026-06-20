from __future__ import annotations

import json

import yaml

from contractforge_databricks import render_databricks_project_bundle
from contractforge_databricks.cli import main


def test_render_databricks_project_bundle_maps_schedule_and_dependencies() -> None:
    bundle = render_databricks_project_bundle(
        {
            "name": "orders_medallion",
            "deployment": {
                "databricks": {
                    "job_key": "orders_job",
                    "job_name": "Orders Medallion",
                    "workspace_root_path": "/Workspace/Shared/orders",
                    "bundle_root": "/Workspace/Shared/orders/files",
                    "evidence_catalog": "workspace",
                    "evidence_schema": "orders_ops",
                    "core_wheel_path": "/Workspace/libs/contractforge_core.whl",
                    "databricks_wheel_path": "/Workspace/libs/contractforge_databricks.whl",
                }
            },
            "schedule": {
                "cron": "0 6 * * *",
                "timezone": "America/Sao_Paulo",
                "enabled": False,
                "max_concurrent_runs": 1,
                "queue": True,
                "adapters": {
                    "databricks": {
                        "pause_status": "PAUSED",
                        "tasks": {
                            "bronze_orders": {"task_key": "bronze"},
                            "silver_orders": {"task_key": "silver", "base_parameters": {"extra": "yes"}},
                        },
                        "extra_tasks": [
                            {
                                "name": "verify_source",
                                "task_key": "verify_source",
                                "notebook_path": "./notebooks/verify_source.py",
                                "base_parameters": {"expected": "2"},
                            }
                        ],
                    },
                },
            },
            "execution_order": [
                {
                    "name": "bronze_orders",
                    "depends_on": ["verify_source"],
                    "contracts": {"databricks": "contracts/databricks/bronze_orders.ingestion.yaml"},
                },
                {
                    "name": "silver_orders",
                    "depends_on": ["bronze_orders"],
                    "contracts": {"databricks": "contracts/databricks/silver_orders.ingestion.yaml"},
                },
            ],
        }
    )

    job = bundle["resources"]["jobs"]["orders_job"]
    tasks = job["tasks"]
    assert bundle["workspace"]["root_path"] == "/Workspace/Shared/orders"
    assert job["schedule"]["quartz_cron_expression"] == "0 0 6 * * ?"
    assert job["schedule"]["timezone_id"] == "America/Sao_Paulo"
    assert job["schedule"]["pause_status"] == "PAUSED"
    assert job["queue"] == {"enabled": True}
    assert job["max_concurrent_runs"] == 1
    assert [task["task_key"] for task in tasks] == ["verify_source", "bronze", "silver"]
    assert tasks[0]["notebook_task"]["notebook_path"] == "./notebooks/verify_source.py"
    assert tasks[1]["depends_on"] == [{"task_key": "verify_source"}]
    assert tasks[2]["depends_on"] == [{"task_key": "bronze"}]
    assert tasks[2]["notebook_task"]["base_parameters"]["contract"] == "contracts/databricks/silver_orders.ingestion.yaml"
    assert tasks[2]["notebook_task"]["base_parameters"]["extra"] == "yes"
    assert job["environments"][0]["spec"]["dependencies"] == [
        "${var.core_wheel_path}",
        "${var.databricks_wheel_path}",
    ]


def test_render_databricks_project_bundle_cli_writes_yaml(tmp_path, capsys) -> None:
    project = tmp_path / "project.yaml"
    output = tmp_path / "databricks.yml"
    project.write_text(
        """
name: demo
execution_order:
  - name: bronze
    contracts:
      databricks: contracts/bronze.ingestion.yaml
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["render-project-bundle", str(project), "--output", str(output), "--force"]) == 0
    payload = json.loads(capsys.readouterr().out)
    rendered = yaml.safe_load(output.read_text(encoding="utf-8"))

    assert payload["status"] == "SUCCESS"
    assert rendered["bundle"]["name"] == "demo"
    assert rendered["resources"]["jobs"]["demo"]["tasks"][0]["task_key"] == "bronze"
