"""Small SDK-free validation helpers for the AWS adapter."""

from __future__ import annotations


def required_text(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text
