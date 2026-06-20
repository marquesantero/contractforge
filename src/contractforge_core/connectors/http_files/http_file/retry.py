"""Retry policy for the bounded HTTP file connector."""

from __future__ import annotations

import time
import urllib.error

RETRYABLE_HTTP_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def is_retryable_http_error(exc: urllib.error.HTTPError) -> bool:
    return int(getattr(exc, "code", 0) or 0) in RETRYABLE_HTTP_STATUS


def is_retryable_network_error(exc: Exception) -> bool:
    return isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError))


def sleep_retry_backoff(backoff_seconds: float, attempt: int) -> None:
    if backoff_seconds <= 0:
        return
    time.sleep(backoff_seconds * max(1, attempt))
