"""Databricks runtime execution for bounded REST API connector sources.

The request/pagination/auth/records logic lives in the core REST client; this
module resolves Databricks secret placeholders, delegates the read to the core,
and materializes the returned records into a Spark DataFrame.
"""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import is_rest_api_connector
from contractforge_core.connectors.api.rest import read_rest_api_records as _core_read_rest_api_records
from contractforge_databricks.runtime.json_materialization import materialize_json_records
from contractforge_databricks.runtime.source_schema import source_declared_schema
from contractforge_databricks.security import resolve_databricks_secret_placeholders


def read_rest_api_records(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Read records from a bounded REST source, resolving secrets via Databricks first."""

    resolved = dict(source)
    if resolved.get("auth") is not None:
        resolved["auth"] = resolve_databricks_secret_placeholders(resolved.get("auth"))
    return _core_read_rest_api_records(resolved)


def resolve_rest_api_dataframe(spark: Any, source: dict[str, Any]) -> Any:
    if not is_rest_api_connector(source):
        raise ValueError(
            "REST API runtime resolution requires source.type=rest_api or source.type=connector and connector=rest_api"
        )
    records = read_rest_api_records(source)
    schema = source_declared_schema(source)
    read = _dict(source.get("read"))
    return materialize_json_records(
        spark,
        records,
        schema=schema,
        read_options=_dict(read.get("json_options")),
        staging_path=read.get("staging_path"),
    )


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
