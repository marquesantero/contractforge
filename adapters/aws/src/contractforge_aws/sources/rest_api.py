"""Render AWS Glue bounded REST API sources via the core REST client.

The bounded REST request/pagination/auth/records logic lives in the core
(``contractforge_core.connectors.api.rest``). The AWS adapter renders the contract
source as a Python literal (with auth secrets rendered as runtime Secrets
Manager lookups) and calls the core reader inside the Glue job, then
materializes the returned records into a Spark DataFrame. The Glue job must have
``contractforge-core`` available (``--additional-python-modules contractforge-core``).
"""

from __future__ import annotations

from typing import Any

from contractforge_aws.security import render_secret_aware_literal

__all__ = ["render_rest_api_source", "render_rest_api_helper"]


def render_rest_api_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    return "\n".join(
        [
            "# Bounded REST pull via the ContractForge core REST client.",
            "# Requires contractforge-core in the Glue job (--additional-python-modules contractforge-core).",
            f"_cf_rest_source = {_render_value(source)}",
            f"{dataframe_name} = _cf_rest_dataframe(spark, _cf_rest_source)",
        ]
    ) + "\n"


def render_rest_api_helper() -> str:
    """Render the Glue-runtime ``_cf_rest_dataframe`` helper definition."""

    return "\n".join(
        [
            "def _cf_rest_dataframe(spark, source):",
            '    """Read a bounded REST source into a DataFrame via the core REST client."""',
            "    import json",
            "    from contractforge_core.connectors import read_rest_api_records",
            "    records = read_rest_api_records(source)",
            "    if not records:",
            "        return spark.createDataFrame([], 'cf_empty_response string')",
            "    rdd = spark.sparkContext.parallelize([json.dumps(record) for record in records])",
            "    return spark.read.json(rdd)",
            "",
        ]
    )


def _render_value(value: Any) -> str:
    """Render a contract value as a Python literal, secret-aware for strings."""

    if isinstance(value, dict):
        body = ", ".join(f"{key!r}: {_render_value(item)}" for key, item in value.items())
        return "{" + body + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_value(item) for item in value) + "]"
    if isinstance(value, str):
        return render_secret_aware_literal(value)
    return repr(value)
