"""Load project plans from JSON or YAML files."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from contractforge_ai.projects.models import ProjectPlan


def load_project_plan(path: str | Path) -> ProjectPlan:
    """Load a project plan from a JSON or YAML file."""

    source = Path(path)
    raw = source.read_text(encoding="utf-8")
    payload = yaml.safe_load(raw) if source.suffix.lower() in {".yaml", ".yml"} else json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Project plan input must be a JSON/YAML object.")
    return ProjectPlan.from_dict(payload)
