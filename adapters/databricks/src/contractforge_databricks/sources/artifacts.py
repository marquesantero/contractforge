"""Source artifact routing for Databricks bundles."""

from __future__ import annotations

from typing import Any

from contractforge_core.connectors import JDBC_CONNECTORS
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.rendering.names import artifact_prefix
from contractforge_databricks.sources.autoloader import render_autoloader_python
from contractforge_databricks.sources.bounded_streams import is_bounded_stream_source, render_bounded_stream_python
from contractforge_databricks.sources.delta_share import is_delta_share_source, render_delta_share_python
from contractforge_databricks.sources.files import (
    is_catalog_source,
    is_file_source,
    render_catalog_source_python,
    render_file_source_python,
)
from contractforge_databricks.sources.http_file import is_http_file_source, render_http_file_python
from contractforge_databricks.sources.interpret import interpret_incremental_files_source, is_incremental_file_source
from contractforge_databricks.sources.jdbc import render_jdbc_python
from contractforge_databricks.sources.native_passthrough import render_native_passthrough_plan
from contractforge_databricks.sources.rest_api import is_rest_api_connector, render_rest_api_review_plan
from contractforge_databricks.sources.table_refs import contract_with_databricks_source_refs


def render_source_artifacts(
    contract: SemanticContract,
    *,
    environment: DatabricksEnvironment | None = None,
) -> dict[str, str]:
    if not contract.source.raw:
        return {}
    runtime_contract = contract_with_databricks_source_refs(contract)
    source = runtime_contract.source.raw or {}
    prefix = artifact_prefix(contract)
    artifacts: dict[str, str] = {}
    if is_incremental_file_source(source):
        artifacts[f"{prefix}.source_autoloader.py"] = render_autoloader_python(
            interpret_incremental_files_source(source, environment=environment)
        )
    if _is_jdbc_source(source):
        artifacts[f"{prefix}.source_jdbc.py"] = render_jdbc_python(source)
    if _can_render_file_source(source):
        artifacts[f"{prefix}.source_files.py"] = render_file_source_python(source)
    if _can_render_catalog_source(source):
        artifacts[f"{prefix}.source_catalog.py"] = render_catalog_source_python(
            source,
        )
    if _can_render_http_file_source(source):
        artifacts[f"{prefix}.source_http_file.py"] = render_http_file_python(source)
    if is_bounded_stream_source(source):
        artifacts[f"{prefix}.source_bounded_stream.py"] = render_bounded_stream_python(source)
    if _can_render_delta_share_source(source):
        artifacts[f"{prefix}.source_delta_share.py"] = render_delta_share_python(source)
    if source.get("type") == "native_passthrough":
        artifacts[f"{prefix}.native_passthrough.json"] = render_native_passthrough_plan(source)
    if is_rest_api_connector(source):
        artifacts[f"{prefix}.source_rest_api_review.json"] = render_rest_api_review_plan(source)
    return artifacts


def _is_jdbc_source(source: dict[str, Any]) -> bool:
    source_type = source.get("type")
    connector = source.get("connector")
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    has_url = bool(source.get("url") or options.get("url"))
    is_jdbc = source_type == "jdbc" or connector in JDBC_CONNECTORS
    return is_jdbc and has_url


def _can_render_file_source(source: dict[str, Any]) -> bool:
    return is_file_source(source) and not is_incremental_file_source(source) and bool(source.get("path"))


def _can_render_catalog_source(source: dict[str, Any]) -> bool:
    if not is_catalog_source(source):
        return False
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    return bool(
        source.get("table")
        or source.get("path")
        or source.get("ref")
        or source.get("table_ref")
        or source.get("query")
        or options.get("query")
    )


def _can_render_http_file_source(source: dict[str, Any]) -> bool:
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    return is_http_file_source(source) and bool(source.get("url") or request.get("url"))


def _can_render_delta_share_source(source: dict[str, Any]) -> bool:
    options = source.get("options") if isinstance(source.get("options"), dict) else {}
    return is_delta_share_source(source) and bool(source.get("profile_file") or options.get("profileFile")) and bool(
        source.get("table") or options.get("table")
    )
