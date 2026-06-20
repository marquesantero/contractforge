"""Runtime watermark collection for Databricks prepared views."""

from __future__ import annotations

from typing import Any

from contractforge_core.runtime import PreparedInput, QueryOne
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.state.queries import render_select_previous_watermark_sql
from contractforge_databricks.watermark import render_select_watermark_candidate_sql


def collect_watermark_candidate(
    *,
    contract: SemanticContract,
    prepared: PreparedInput,
    query_one: QueryOne | None,
) -> tuple[str | None, str | None]:
    columns = _watermark_columns(contract)
    if not columns or query_one is None:
        return (None, None)
    row = query_one(
        render_select_watermark_candidate_sql(
            table_name=prepared.source_view,
            columns=columns,
            types=prepared.source_schema,
        )
    )
    value = _row_value(row, "watermark_value")
    return ("|".join(columns), None if value is None else str(value))


def collect_previous_watermark(
    *,
    contract: SemanticContract,
    query_one: QueryOne | None,
    catalog: str = "main",
    schema: str = "ops",
) -> tuple[str | None, str | None]:
    columns = _watermark_columns(contract)
    if not columns or query_one is None:
        return (None, None)
    row = query_one(
        render_select_previous_watermark_sql(
            target_table=target_full_name(contract),
            state_table=f"{catalog}.{schema}.ctrl_ingestion_state",
        )
    )
    value = _row_value(row, "watermark_value")
    return ("|".join(columns), None if value is None else str(value))


def _watermark_columns(contract: SemanticContract) -> tuple[str, ...]:
    metadata = contract.operations.metadata if contract.operations and contract.operations.metadata else {}
    value = metadata.get("watermark_columns")
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()


def _row_value(row: Any, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "asDict"):
        return row.asDict().get(key)
    return getattr(row, key, None)
