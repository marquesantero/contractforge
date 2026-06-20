"""Small JSON/YAML helpers for core CLI modules."""

from __future__ import annotations

import json
from typing import Any


def yaml_load(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("YAML support requires PyYAML; use JSON files or install PyYAML") from exc
    return yaml.safe_load(text)


def yaml_dump(payload: dict[str, Any]) -> str:
    try:
        import yaml  # type: ignore
    except Exception:  # pragma: no cover
        return json.dumps(payload, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
