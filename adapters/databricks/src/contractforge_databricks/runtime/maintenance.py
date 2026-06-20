"""Post-write Databricks maintenance hooks."""

from __future__ import annotations

from contractforge_core.execution import ExecutionOutcome
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.execution import SqlRunner
from contractforge_databricks.maintenance import MaintenancePlan, execute_maintenance_plan


def run_post_write_maintenance(
    *,
    runner: SqlRunner,
    contract: SemanticContract,
    target_table: str,
    outcome: ExecutionOutcome | None,
    rows_written: int,
) -> tuple[str, ...]:
    extensions = databricks_extensions(contract)
    if not extensions.get("optimize_after_write"):
        return ()
    rows_written = int((outcome.metrics if outcome else {}).get("rows_written", rows_written) or 0)
    if rows_written <= 0:
        return ()
    return execute_maintenance_plan(
        runner,
        MaintenancePlan(
            target_table=target_table,
            optimize=True,
            zorder_columns=_tuple(extensions.get("zorder_columns")),
        ),
    )


def _tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return (str(value),)
