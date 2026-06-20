"""Payload helpers for the ContractForge AI CLI."""

from __future__ import annotations


def with_enrichment(payload: dict, enrichment) -> dict:
    if enrichment is not None:
        payload["ai_enrichment"] = enrichment.to_dict()
    return payload
