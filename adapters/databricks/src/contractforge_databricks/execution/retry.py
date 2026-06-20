"""Retry helpers for Databricks Delta concurrency operations."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def is_retryable_delta_concurrency_error(exc: Exception) -> bool:
    text = str(exc).upper()
    return any(token in text for token in ("CONCURRENT", "CONFLICT", "RETRY", "DELTA_CONCURRENT"))


def with_delta_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    jitter: Callable[[], float] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    last_exc: Exception | None = None
    jitter_fn = jitter or random.random
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not is_retryable_delta_concurrency_error(exc) or attempt == attempts:
                raise
            sleep(backoff_seconds * attempt + jitter_fn())
    raise last_exc  # type: ignore[misc]
