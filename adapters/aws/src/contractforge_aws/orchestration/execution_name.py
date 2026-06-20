"""Execution naming helpers for AWS project orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


def execution_name(project: Mapping[str, Any], _settings: Mapping[str, str]) -> str:
    """Return a unique, readable Step Functions execution name."""

    name = str(project.get("name") or "contractforge_project").strip().replace("_", "-")
    suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{name}-run-{suffix}-{uuid4().hex[:8]}"
