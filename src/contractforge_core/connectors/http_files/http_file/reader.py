"""Bounded HTTP file fetcher."""

from __future__ import annotations

import atexit
import os
import tempfile
import urllib.error
import urllib.request
from typing import Any

from contractforge_core.connectors.http_files.http_file.retry import (
    is_retryable_http_error,
    is_retryable_network_error,
    sleep_retry_backoff,
)
from contractforge_core.connectors.http_files.http_file.safety import validate_http_file_target
from contractforge_core.connectors.http_files.http_file.source import (
    http_file_format,
    http_file_headers,
    http_file_url,
)

_TEMP_DOWNLOADS: set[str] = set()


def read_http_file_payload(source: dict[str, Any]) -> bytes:
    request = source.get("request", {}) if isinstance(source.get("request"), dict) else {}
    url = str(source.get("url") or request.get("url") or "").strip()
    if not url:
        raise ValueError("HTTP file source requires url or request.url")
    method = str(request.get("method") or "GET").upper()
    if method != "GET":
        raise ValueError("HTTP file source supports only GET")

    final_url = http_file_url(source)
    validate_http_file_target(final_url, context="HTTP file source URL")
    payload = _request_with_retry(
        final_url,
        headers=http_file_headers(source),
        timeout=int(source.get("limits", {}).get("timeout_seconds", 60)),
        attempts=int(source.get("limits", {}).get("retry_attempts", source.get("read", {}).get("retry_attempts", 1))),
        backoff=float(
            source.get("limits", {}).get("retry_backoff_seconds", source.get("read", {}).get("retry_backoff_seconds", 0))
        ),
    )
    max_bytes = source.get("limits", {}).get("max_bytes")
    if max_bytes is not None and len(payload) > int(max_bytes):
        raise ValueError(f"HTTP payload exceeds source.limits.max_bytes={int(max_bytes)}")
    return payload


def download_http_file(source: dict[str, Any]) -> str:
    """Download a GET HTTP file to a local temp path and return that path."""

    payload = read_http_file_payload(source)
    suffix = "." + http_file_format(source).replace("text", "txt")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(payload)
        _TEMP_DOWNLOADS.add(handle.name)
        return handle.name


def cleanup_http_file_downloads() -> None:
    """Best-effort cleanup for bounded HTTP file downloads created by this process."""

    for path in tuple(_TEMP_DOWNLOADS):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:
            continue
        else:
            _TEMP_DOWNLOADS.discard(path)


def _request_with_retry(url: str, *, headers: dict[str, str], timeout: int, attempts: int, backoff: float) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            opener = urllib.request.build_opener(_NoRedirect)
            request = urllib.request.Request(url, headers=headers, method="GET")
            with opener.open(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if not is_retryable_http_error(exc):
                raise
        except Exception as exc:
            last_error = exc
            if not is_retryable_network_error(exc):
                raise
        if attempt < max(1, attempts):
            sleep_retry_backoff(backoff, attempt)
    assert last_error is not None
    raise last_error


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"HTTP file source refused a redirect to {newurl}")

atexit.register(cleanup_http_file_downloads)
