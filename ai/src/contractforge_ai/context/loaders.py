"""Contract loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from contractforge_ai.context.redaction import redact_secrets


def load_contract(path: str | Path) -> dict[str, Any]:
    """Load a YAML or JSON contract and return a redacted dictionary."""

    contract_path = Path(path)
    raw = contract_path.read_text(encoding="utf-8")

    if contract_path.suffix.lower() == ".json":
        data = json.loads(raw)
    else:
        loaded = yaml.safe_load(raw)
        data = loaded if loaded is not None else {}

    if not isinstance(data, dict):
        raise ValueError(f"Contract must be a mapping: {contract_path}")

    return redact_secrets(data)

