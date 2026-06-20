"""Portable typed watermark encoding."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class WatermarkField:
    type: str
    value: str | None


TypedWatermark = dict[str, WatermarkField]


def encode_watermark_values(values: dict[str, object], types: dict[str, str] | None = None) -> str:
    """Encode deterministic typed watermark JSON from column values."""
    type_map = types or {}
    payload = {
        column: {
            "type": str(type_map.get(column, "string")),
            "value": None if value is None else str(value),
        }
        for column, value in values.items()
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def decode_watermark_value(raw: str | None, columns: tuple[str, ...]) -> TypedWatermark | None:
    """Decode typed watermark JSON and validate expected columns."""
    if not raw:
        return None
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"Invalid watermark payload: {raw}")
    missing = [column for column in columns if column not in parsed]
    if missing:
        raise ValueError(f"Watermark does not contain expected columns: {missing}")
    decoded: TypedWatermark = {}
    for column in columns:
        item = parsed[column]
        if not isinstance(item, dict) or "value" not in item:
            raise ValueError(f"Invalid watermark field for column {column}: {item}")
        decoded[column] = WatermarkField(
            type=str(item.get("type") or "string"),
            value=None if item.get("value") is None else str(item.get("value")),
        )
    return decoded


def extract_watermark_field_value(raw: str | None, column: str | None = None) -> str | None:
    """Extract a single connector watermark value from plain or typed payloads."""
    if raw in (None, ""):
        return None
    text = str(raw)
    if not text.strip().startswith("{"):
        return text
    if not column:
        raise ValueError("typed watermark extraction requires a watermark column")
    decoded = decode_watermark_value(text, (column,))
    if decoded is None:
        return None
    return decoded[column].value
