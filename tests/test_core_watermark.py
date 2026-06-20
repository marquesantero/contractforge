from __future__ import annotations

import pytest

from contractforge_core.watermark import decode_watermark_value, encode_watermark_values, extract_watermark_field_value


def test_encode_decode_typed_watermark_values() -> None:
    encoded = encode_watermark_values(
        {"updated_at": "2026-01-01T00:00:00Z", "version": 7},
        {"updated_at": "timestamp", "version": "bigint"},
    )

    decoded = decode_watermark_value(encoded, ("updated_at", "version"))

    assert decoded is not None
    assert decoded["updated_at"].type == "timestamp"
    assert decoded["updated_at"].value == "2026-01-01T00:00:00Z"
    assert decoded["version"].type == "bigint"
    assert decoded["version"].value == "7"


def test_decode_watermark_requires_expected_columns() -> None:
    encoded = encode_watermark_values({"updated_at": "2026-01-01"})

    with pytest.raises(ValueError, match="expected columns"):
        decode_watermark_value(encoded, ("updated_at", "version"))


def test_extract_single_connector_watermark_value() -> None:
    encoded = encode_watermark_values({"updated_at": "2026-01-01"})

    assert extract_watermark_field_value("plain-watermark") == "plain-watermark"
    assert extract_watermark_field_value(encoded, "updated_at") == "2026-01-01"

    with pytest.raises(ValueError, match="watermark column"):
        extract_watermark_field_value(encoded)
