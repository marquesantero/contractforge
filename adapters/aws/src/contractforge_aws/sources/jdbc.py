"""Render AWS Glue JDBC sources."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import JDBC_CONNECTORS, jdbc_common_options
from contractforge_aws.security import (
    assert_no_inline_jdbc_secrets,
    is_rds_iam_options,
    redact_value,
    render_secret_aware_literal,
)
from contractforge_aws.sources.rds_iam import split_rds_iam_options

_JDBC_GLUE_CONNECTION_TYPES = {
    "postgres": "postgresql",
    "mysql": "mysql",
    "mariadb": "mysql",
    "sqlserver": "sqlserver",
    "oracle": "oracle",
    "redshift": "redshift",
}
_JDBC_URL_PREFIXES = {
    "jdbc:postgresql:": "postgresql",
    "jdbc:mysql:": "mysql",
    "jdbc:mariadb:": "mysql",
    "jdbc:sqlserver:": "sqlserver",
    "jdbc:oracle:": "oracle",
    "jdbc:redshift:": "redshift",
}


def is_jdbc_source(source: dict[str, Any]) -> bool:
    connector = source.get("connector") or source.get("type")
    return connector in JDBC_CONNECTORS or source.get("type") == "jdbc"


def jdbc_uses_bookmarks(source: dict[str, Any]) -> bool:
    return _jdbc_bookmark_config(source) is not None


def render_jdbc_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    bookmark = _jdbc_bookmark_config(source)
    if bookmark:
        return _render_bookmark_source(source, bookmark, dataframe_name=dataframe_name)
    return _render_spark_source(source, dataframe_name=dataframe_name)


def _render_spark_source(source: dict[str, Any], *, dataframe_name: str) -> str:
    expressions, review_options = _jdbc_option_expressions(source)
    lines = [
        f"{dataframe_name} = (",
        "    spark.read",
        "    .format('jdbc')",
    ]
    for key in sorted(expressions):
        lines.append(f"    .option({key!r}, {expressions[key]})")
    lines.extend(["    .load()", ")"])
    lines.append("# JDBC options (sensitive values redacted for review):")
    lines.append(f"# {redact_value(review_options)!r}")
    return "\n".join(lines) + "\n"


def _render_bookmark_source(source: dict[str, Any], bookmark: dict[str, Any], *, dataframe_name: str) -> str:
    expressions, review_options = _jdbc_option_expressions(source)
    lines = [
        "# Incremental JDBC discovery via AWS Glue job bookmarks.",
        "# Register the job with --job-bookmark-option job-bookmark-enable for state to persist.",
        "_cf_jdbc_options = {",
    ]
    for key in sorted(expressions):
        lines.append(f"    {key!r}: {expressions[key]},")
    lines.extend(
        [
            f"    'jobBookmarkKeys': {bookmark['keys']!r},",
            f"    'jobBookmarkKeysSortOrder': {bookmark['sort_order']!r},",
            "}",
            f"{dataframe_name} = glue_context.create_dynamic_frame.from_options(",
            f"    connection_type={bookmark['connection_type']!r},",
            "    connection_options=_cf_jdbc_options,",
            "    transformation_ctx='cf_jdbc_bookmark',",
            ").toDF()",
            "# JDBC options (sensitive values redacted for review):",
            f"# {redact_value(review_options)!r}",
        ]
    )
    return "\n".join(lines) + "\n"


def _jdbc_option_expressions(source: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    options = jdbc_common_options(source)
    assert_no_inline_jdbc_secrets(options)
    if is_rds_iam_options(options):
        render_options, password_expression = split_rds_iam_options(options)
        expressions = {key: render_secret_aware_literal(str(value)) for key, value in render_options.items()}
        expressions["password"] = password_expression
        review_options = dict(render_options)
        review_options["password"] = "<resolved at runtime via RDS IAM>"
        return expressions, review_options
    expressions = {key: render_secret_aware_literal(str(value)) for key, value in options.items()}
    return expressions, dict(options)


def _jdbc_bookmark_config(source: dict[str, Any]) -> dict[str, Any] | None:
    incremental = source.get("incremental") if isinstance(source.get("incremental"), dict) else {}
    column = str(incremental.get("watermark_column") or "").strip()
    connection_type = _glue_connection_type(source)
    if not column or "." in column or not connection_type:
        return None
    sort_order = str(incremental.get("sort_order") or incremental.get("watermark_sort_order") or "asc").lower()
    if sort_order not in {"asc", "desc"}:
        raise ValueError("AWS JDBC bookmark sort_order must be 'asc' or 'desc'")
    return {"keys": [column], "sort_order": sort_order, "connection_type": connection_type}


def _glue_connection_type(source: dict[str, Any]) -> str | None:
    connector = str(source.get("connector") or source.get("type") or "").lower()
    if connector in _JDBC_GLUE_CONNECTION_TYPES:
        return _JDBC_GLUE_CONNECTION_TYPES[connector]
    url = str(source.get("url") or source.get("options", {}).get("url") or "").lower()
    return next((value for prefix, value in _JDBC_URL_PREFIXES.items() if url.startswith(prefix)), None)
