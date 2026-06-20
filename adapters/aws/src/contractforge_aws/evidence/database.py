"""AWS evidence database naming."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.names import glue_database_name


def evidence_database(contract: SemanticContract, override: str | None = None) -> str:
    return override or f"{glue_database_name(contract)}_ops"
