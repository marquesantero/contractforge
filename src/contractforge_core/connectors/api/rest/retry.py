"""HTTP retry policy for the platform-neutral bounded REST/HTTP client."""

from __future__ import annotations

import time
import urllib.error

RETRYABLE_HTTP_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def is_retryable_http_error(exc: urllib.error.HTTPError) -> bool:
    return exc.code in RETRYABLE_HTTP_STATUS


def is_retryable_network_error(exc: Exception) -> bool:
    return isinstance(exc, (urllib.error.URLError, TimeoutError, OSError))


def sleep_retry_backoff(backoff: float, attempt: int) -> None:
    if backoff > 0:
        time.sleep(backoff * attempt)
