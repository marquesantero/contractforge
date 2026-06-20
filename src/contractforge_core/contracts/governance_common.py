"""Shared governance contract helpers."""

from __future__ import annotations

from pydantic import Field

from contractforge_core.contracts.base import StrictContractModel


def non_empty(value: str | None) -> str | None:
    return value or None


class TargetReferenceContractModel(StrictContractModel):
    catalog: str | None = None
    schema_: str | None = Field(default=None, alias="schema")
    table: str | None = None
