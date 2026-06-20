"""Databricks review planning for generic REST API connector contracts."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.connectors import is_rest_api_connector as is_rest_api_connector, rest_api_descriptor


def render_rest_api_review_plan(source: dict[str, Any]) -> str:
    descriptor = rest_api_descriptor(source, redaction="***REDACTED***")
    payload = {
        "kind": "databricks_rest_api_review_plan",
        **descriptor,
        "recommended_databricks_targets": _recommended_targets(source, descriptor["pagination"]),
        "notes": [
            "Generic paginated REST API ingestion is not rendered as a custom Databricks Python API client by default.",
            "For bounded public files, prefer portable http_file/http_json/http_csv source types.",
            "For proprietary SaaS APIs, prefer native_passthrough so the adapter can target Lakeflow Connect or Databricks Connections.",
            "If no native connector exists, execute a reviewed landing step outside the semantic core and ingest landed files with incremental_files.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _recommended_targets(source: dict[str, Any], pagination: dict[str, Any]) -> list[str]:
    if not pagination or pagination.get("type") in {None, "none"}:
        return ["http_file_if_bounded", "databricks_connection"]
    system = str(source.get("provider") or source.get("name") or "").lower()
    if system in {"salesforce", "workday", "servicenow"}:
        return ["lakeflow_connect", "native_passthrough"]
    return ["native_passthrough", "land_to_object_storage_then_incremental_files"]
