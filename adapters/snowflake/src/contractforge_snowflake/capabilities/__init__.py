"""Snowflake capability declarations."""

from contractforge_snowflake.capabilities.sql_warehouse import (
    SNOWFLAKE_SUBTARGET_SNOWPIPE,
    SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE,
    SNOWFLAKE_SUBTARGET_STREAMS_TASKS,
    SNOWFLAKE_SUBTARGET_TASK_GRAPH,
    snowflake_sql_warehouse_capabilities,
)

__all__ = [
    "SNOWFLAKE_SUBTARGET_SNOWPIPE",
    "SNOWFLAKE_SUBTARGET_SQL_WAREHOUSE",
    "SNOWFLAKE_SUBTARGET_STREAMS_TASKS",
    "SNOWFLAKE_SUBTARGET_TASK_GRAPH",
    "snowflake_sql_warehouse_capabilities",
]
