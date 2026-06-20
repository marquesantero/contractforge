"""Render AWS Glue Spark source reads."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import (
    TableRefResolver,
    catalog_source_query,
    catalog_source_table_or_path,
    file_reader_options,
    file_source_format,
    is_bounded_stream_source,
    is_catalog_source,
    is_delta_share_source,
    is_file_source,
    is_http_file_source,
    is_rest_api_connector,
    jdbc_common_options,
)
from contractforge_aws.sources.http_file import render_http_file_source, source_requires_http_basic_auth
from contractforge_aws.sources.jdbc import is_jdbc_source, render_jdbc_source
from contractforge_aws.sources.rest_api import render_rest_api_source
from contractforge_aws.sources.streams import render_bounded_stream_source, render_delta_share_source
from contractforge_aws.sources.classification import is_aws_source_renderable
from contractforge_aws.security import (
    contains_secret_placeholder,
    is_rds_iam_options,
    render_secret_aware_literal,
    validate_source_security,
)
from contractforge_aws.sources.interpret import (
    BOOKMARK_ELIGIBLE_FORMATS,
    glue_incremental_file_format_options,
    incremental_files_is_bookmark_renderable,
    interpret_incremental_files_source,
    is_incremental_file_source,
)


_INCREMENTAL_TRANSFORMATION_CTX = "cf_incremental_files"


def render_source_dataframe(
    source: dict[str, Any],
    *,
    dataframe_name: str = "df",
    table_ref_resolver: TableRefResolver | None = None,
) -> str:
    validate_source_security(source)
    for matches, renderer in _SOURCE_RENDERERS:
        if matches(source):
            return renderer(source, dataframe_name=dataframe_name, table_ref_resolver=table_ref_resolver)
    raise ValueError(f"AWS Glue renderer does not support source type {source.get('type')!r} yet")


def can_render_source(source: dict[str, Any]) -> bool:
    """Return whether the source read can be rendered for AWS Glue.

    True only for source families classified as renderable by the adapter-owned
    AWS source support map. Non-renderable review cases route to the review
    outline instead of raising.
    """

    return is_aws_source_renderable(source)


def source_requires_secret_resolver(source: dict[str, Any]) -> bool:
    """Return whether rendering the source emits a Secrets Manager lookup.

    Every source branch renders contract literals secret-aware, so any
    ``{{ secret:scope/key }}`` placeholder anywhere in the source requires the
    runtime resolver helper, not just JDBC.
    """

    return contains_secret_placeholder(source)


def source_requires_rds_iam(source: dict[str, Any]) -> bool:
    """Return whether rendering the source emits a runtime RDS IAM token call."""

    return is_jdbc_source(source) and is_rds_iam_options(jdbc_common_options(source))


def source_requires_http_fetch(source: dict[str, Any]) -> bool:
    """Return whether rendering the source emits a runtime HTTP fetch helper."""

    return is_http_file_source(source)


def source_requires_http_basic_helper(source: dict[str, Any]) -> bool:
    return is_http_file_source(source) and source_requires_http_basic_auth(source)


def source_requires_rest_helper(source: dict[str, Any]) -> bool:
    """Return whether rendering the source emits the core REST client helper."""

    return is_rest_api_connector(source)


def _render_incremental_files_source(
    source: dict[str, Any],
    *,
    dataframe_name: str,
    table_ref_resolver: TableRefResolver | None = None,
) -> str:
    if not incremental_files_is_bookmark_renderable(source):
        raise ValueError(
            "AWS Glue incremental_files rendering requires source.path, a bookmark-eligible format "
            f"({', '.join(sorted(BOOKMARK_ELIGIBLE_FORMATS))})"
        )
    interpreted = interpret_incremental_files_source(source)
    path = interpreted["path"]
    file_format = file_source_format(interpreted)
    options = glue_incremental_file_format_options(interpreted)
    lines = [
        "# Incremental new-file discovery via AWS Glue job bookmarks.",
        "# Register the job with --job-bookmark-option job-bookmark-enable for state to persist.",
        f"{dataframe_name} = glue_context.create_dynamic_frame.from_options(",
        "    connection_type='s3',",
        f"    format={file_format!r},",
        f"    connection_options={{'paths': [{render_secret_aware_literal(str(path))}], 'recurse': True}},",
    ]
    if options:
        lines.append(f"    format_options={_literal_dict(options)},")
    lines.extend([f"    transformation_ctx={_INCREMENTAL_TRANSFORMATION_CTX!r},", ").toDF()"])
    return "\n".join(lines) + "\n"


def _render_file_source(
    source: dict[str, Any],
    *,
    dataframe_name: str,
    table_ref_resolver: TableRefResolver | None = None,
) -> str:
    path = source.get("path")
    if not path:
        raise ValueError("AWS file source rendering requires source.path")
    file_format = file_source_format(source)
    lines = [
        f"{dataframe_name} = (",
        "    spark.read",
        f"    .format({file_format!r})",
    ]
    for key, value in sorted(file_reader_options(source).items()):
        lines.append(f"    .option({key!r}, {render_secret_aware_literal(str(value))})")
    lines.extend([f"    .load({render_secret_aware_literal(str(path))})", ")"])
    return "\n".join(lines) + "\n"


def _render_catalog_source(
    source: dict[str, Any],
    *,
    dataframe_name: str,
    table_ref_resolver: TableRefResolver | None = None,
) -> str:
    if source.get("type") == "sql":
        return f"{dataframe_name} = spark.sql({render_secret_aware_literal(str(catalog_source_query(source, table_ref_resolver=table_ref_resolver)))})\n"
    table = catalog_source_table_or_path(source, table_ref_resolver=table_ref_resolver)
    return f"{dataframe_name} = spark.table({render_secret_aware_literal(str(table))})\n"


def _literal_dict(values: dict[str, Any]) -> str:
    body = ", ".join(f"{str(key)!r}: {_literal_value(value)}" for key, value in sorted(values.items()))
    return "{" + body + "}"


def _literal_value(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    return render_secret_aware_literal(str(value))


# Ordered (predicate, renderer) dispatch for source reads. Order matters:
# incremental_files is matched before the generic file reader.
def _renderer_without_refs(renderer):
    def _wrapped(
        source: dict[str, Any],
        *,
        dataframe_name: str,
        table_ref_resolver: TableRefResolver | None = None,
    ) -> str:
        return renderer(source, dataframe_name=dataframe_name)

    return _wrapped


_SOURCE_RENDERERS = (
    (is_jdbc_source, _renderer_without_refs(render_jdbc_source)),
    (is_catalog_source, _render_catalog_source),
    (is_incremental_file_source, _render_incremental_files_source),
    (is_http_file_source, _renderer_without_refs(render_http_file_source)),
    (is_rest_api_connector, _renderer_without_refs(render_rest_api_source)),
    (is_bounded_stream_source, _renderer_without_refs(render_bounded_stream_source)),
    (is_delta_share_source, _renderer_without_refs(render_delta_share_source)),
    (is_file_source, _render_file_source),
)
