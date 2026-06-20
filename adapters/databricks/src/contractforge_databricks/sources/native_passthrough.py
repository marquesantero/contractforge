"""Databricks native passthrough planning artifacts."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.connectors import native_passthrough_descriptor


def render_native_passthrough_plan(source: dict[str, Any]) -> str:
    descriptor = native_passthrough_descriptor(source)

    payload = {
        "kind": "databricks_native_passthrough_plan",
        **descriptor,
        "recommended_databricks_targets": _recommended_targets(str(descriptor["system"])),
        "notes": [
            "Use Databricks-native ingestion where available, such as Lakeflow Connect or Databricks Connections.",
            "Do not implement proprietary SaaS API clients inside contractforge_databricks unless no native path exists.",
            "Adapter execution must remain platform-owned and auditable.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _recommended_targets(system: str) -> list[str]:
    normalized = system.lower()
    if normalized in {"salesforce", "workday", "servicenow", "google_analytics", "google_ads"}:
        return ["lakeflow_connect"]
    if normalized in {"sftp", "ftp"}:
        return ["databricks_connection", "autoloader"]
    return ["databricks_connection", "lakeflow_connect_if_available"]
