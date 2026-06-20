"""Public API for the ContractForge Snowflake adapter."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from contractforge_snowflake.adapter import SnowflakeAdapter
from contractforge_snowflake.api import (
    build_snowflake_publish_bundle,
    plan_snowflake_contract,
    render_snowflake_contract,
)
from contractforge_snowflake.capabilities import (
    SNOWFLAKE_SUBTARGET_SNOWPIPE,
    SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
    SNOWFLAKE_SUBTARGET_STREAMS_TASKS,
    SNOWFLAKE_SUBTARGET_TASK_GRAPH,
    snowflake_sql_warehouse_capabilities,
)
from contractforge_snowflake.dashboards import render_control_dashboard_artifacts, render_control_dashboard_sql
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import render_deployment_ledger_insert_sql
from contractforge_snowflake.maintenance import build_control_retention_plan, execute_control_retention_plan
from contractforge_snowflake.runtime import (
    SnowflakeAccessHistoryLineageResult,
    build_snowflake_project_cleanup_plan,
    deploy_snowflake_project,
    publish_snowflake_contract,
    reconcile_snowflake_access_history_lineage,
    reconcile_snowflake_cost_evidence,
    run_snowflake_contract,
    run_snowflake_project,
    wait_snowflake_project_tasks,
)
from contractforge_snowflake.subtargets import list_snowflake_subtargets

try:
    __version__ = _version("contractforge-snowflake")
except PackageNotFoundError:  # pragma: no cover - editable/source tree without installed metadata
    __version__ = "0.2.0"

__all__ = [
    "SNOWFLAKE_SUBTARGET_SNOWPIPE",
    "SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE",
    "SNOWFLAKE_SUBTARGET_STREAMS_TASKS",
    "SNOWFLAKE_SUBTARGET_TASK_GRAPH",
    "SnowflakeAdapter",
    "SnowflakeAccessHistoryLineageResult",
    "SnowflakeEnvironment",
    "__version__",
    "build_snowflake_publish_bundle",
    "build_control_retention_plan",
    "build_snowflake_project_cleanup_plan",
    "deploy_snowflake_project",
    "execute_control_retention_plan",
    "list_snowflake_subtargets",
    "plan_snowflake_contract",
    "publish_snowflake_contract",
    "reconcile_snowflake_access_history_lineage",
    "reconcile_snowflake_cost_evidence",
    "render_control_dashboard_artifacts",
    "render_control_dashboard_sql",
    "render_deployment_ledger_insert_sql",
    "render_snowflake_contract",
    "run_snowflake_contract",
    "run_snowflake_project",
    "snowflake_sql_warehouse_capabilities",
    "wait_snowflake_project_tasks",
]
