"""Databricks source metadata evidence helpers."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.connectors import source_metadata_from_contract as core_source_metadata_from_contract
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.rendering.names import target_full_name


def source_metadata_from_contract(contract: SemanticContract) -> dict[str, Any]:
    return core_source_metadata_from_contract(contract, target_table=target_full_name(contract))


def render_source_metadata_json(contract: SemanticContract) -> str:
    return json.dumps(source_metadata_from_contract(contract), indent=2, sort_keys=True) + "\n"
