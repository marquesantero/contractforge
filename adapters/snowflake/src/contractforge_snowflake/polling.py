"""Polling defaults shared by Snowflake runtime helpers."""

from __future__ import annotations

MIN_POLL_INTERVAL_SECONDS = 1.0


def clamped_poll_interval(value: float, *, minimum: float = MIN_POLL_INTERVAL_SECONDS) -> float:
    """Return a non-busy polling interval."""

    return max(float(minimum), float(value))


__all__ = ["MIN_POLL_INTERVAL_SECONDS", "clamped_poll_interval"]
