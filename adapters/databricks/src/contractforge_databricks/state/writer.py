"""State writer using an injected SQL runner."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from contractforge_databricks.execution.sql_merge import SqlRunner
from contractforge_databricks.state.queries import render_lock_status_sql, render_record_control_metadata_sql
from contractforge_databricks.state.sql import (
    render_acquire_lock_sql,
    render_release_lock_sql,
    render_upsert_state_sql,
)


logger = logging.getLogger("contractforge_databricks")


class StateWriter:
    def __init__(
        self,
        runner: SqlRunner,
        *,
        catalog: str = "main",
        schema: str = "ops",
        query_one: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> None:
        self.runner = runner
        self.catalog = catalog
        self.schema = schema
        self.query_one = query_one

    def acquire_lock(self, *, target_table: str, run_id: str, owner: str | None = None, ttl_minutes: int = 60) -> None:
        self.runner.sql(
            render_acquire_lock_sql(
                target_table=target_table,
                run_id=run_id,
                owner=owner,
                ttl_minutes=ttl_minutes,
                catalog=self.catalog,
                schema=self.schema,
            )
        )
        if self.query_one is None:
            return
        row = self.query_one(
            render_lock_status_sql(
                target_table=target_table,
                locks_table=f"{self.catalog}.{self.schema}.ctrl_ingestion_locks",
            )
        )
        if not row or row.get("run_id") != run_id or row.get("status") != "ACTIVE":
            raise RuntimeError(
                f"Lock is busy for {target_table}. This run_id={run_id} did not acquire the lock. "
                f"Current lock: {row}"
            )

    def release_lock(self, *, target_table: str, run_id: str) -> None:
        try:
            self.runner.sql(
                render_release_lock_sql(
                    target_table=target_table,
                    run_id=run_id,
                    catalog=self.catalog,
                    schema=self.schema,
                )
            )
        except Exception as exc:
            logger.warning("Failed to release lock for %s: %s", target_table, exc)

    def upsert_state(self, **kwargs: object) -> None:
        self.runner.sql(render_upsert_state_sql(catalog=self.catalog, schema=self.schema, **kwargs))

    def record_control_metadata(self, *, framework_version: str, ctrl_schema_version: int) -> None:
        self.runner.sql(
            render_record_control_metadata_sql(
                framework_version=framework_version,
                ctrl_schema_version=ctrl_schema_version,
                metadata_table=f"{self.catalog}.{self.schema}.ctrl_ingestion_metadata",
            )
        )
