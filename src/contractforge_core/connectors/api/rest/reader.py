"""Platform-neutral bounded REST API records reader.

Returns a list of record dicts from a bounded REST source. Adapters resolve
secrets and materialize the records into a platform DataFrame; this reader does
the request, pagination, limits and record extraction with the standard
library, so every adapter shares one implementation.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from contractforge_core.connectors.api.rest.auth import rest_request_headers
from contractforge_core.connectors.api.rest.pagination import (
    json_path,
    max_pages_for_source,
    next_url,
    page_urls,
    pagination_type,
    url_with_params,
)
from contractforge_core.connectors.api.rest.retry import (
    is_retryable_http_error,
    is_retryable_network_error,
    sleep_retry_backoff,
)
from contractforge_core.connectors.api.rest.safety import validate_http_target
from contractforge_core.connectors.api.rest.transport import NoRedirect as _NoRedirect  # noqa: F401 - re-exported for test access
from contractforge_core.connectors.api.rest.transport import open_request as _open_request
from contractforge_core.watermark import extract_watermark_field_value


def read_rest_api_records(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Read all records from a bounded REST source (secrets must be pre-resolved)."""

    request = _dict(source.get("request"))
    url = str(source.get("url") or request.get("url") or "").strip()
    if not url:
        raise ValueError("REST API source requires url or request.url")
    method = str(request.get("method") or "GET").upper()
    if method not in {"GET", "POST"}:
        raise ValueError("REST API runtime supports only GET and POST")
    url = url_with_params(url, _string_dict(request.get("params")))
    incremental = _dict(source.get("incremental"))
    watermark = _watermark_value(source)
    if watermark and incremental.get("watermark_param"):
        url = url_with_params(url, {str(incremental["watermark_param"]): watermark})
    limits = _dict(source.get("limits"))
    read = _dict(source.get("read"))
    timeout = int(limits.get("timeout_seconds", 60))
    attempts = int(limits.get("retry_attempts", read.get("retry_attempts", 1)))
    backoff = float(limits.get("retry_backoff_seconds", read.get("retry_backoff_seconds", 0)))
    max_page_bytes = int(limits.get("max_page_bytes", 0) or 0)
    max_total_bytes = int(limits.get("max_total_bytes", 0) or 0)
    max_records = int(limits.get("max_records", 0) or 0)
    rate_limit_per_minute = int(limits.get("rate_limit_per_minute", 0) or 0)
    min_request_interval = 60.0 / rate_limit_per_minute if rate_limit_per_minute > 0 else 0.0
    response = _dict(source.get("response"))
    response_mode = str(response.get("mode") or "records").lower()
    if response_mode not in {"records", "raw"}:
        raise ValueError("source.response.mode must be 'records' or 'raw'")
    raw_column = str(response.get("raw_column") or "raw_response").strip()
    if response_mode == "raw" and not _is_simple_column(raw_column):
        raise ValueError("source.response.raw_column must be a simple column name")

    body = _request_body(request, incremental, watermark)
    headers = rest_request_headers(source, incremental, watermark)
    records: list[dict[str, Any]] = []
    total_bytes = 0
    pages = 0
    static_urls = page_urls(url, source)
    static_index = 0
    dynamic_url: str | None = None
    last_request_at = 0.0
    while static_index < len(static_urls) or dynamic_url:
        current_url = dynamic_url or static_urls[static_index]
        if not dynamic_url:
            static_index += 1
        validate_http_target(current_url, context="REST API source URL")
        _respect_rate_limit(min_request_interval, last_request_at)
        payload, response_headers, final_url, response_bytes, raw_text = _request_with_retry(
            current_url,
            method=method,
            headers=headers,
            body=body,
            timeout=timeout,
            attempts=attempts,
            backoff=backoff,
            parse_json=response_mode == "records" or pagination_type(source) == "cursor",
        )
        last_request_at = time.monotonic()
        pages += 1
        total_bytes += response_bytes
        _enforce_limits(response_bytes, total_bytes, max_page_bytes, max_total_bytes)
        if response_mode == "raw":
            records.append({raw_column: raw_text, "response_page_number": pages})
        else:
            records.extend(_records_from_payload(payload, response.get("records_path")))
        _enforce_record_limit(len(records), max_records)
        if pages >= max_pages_for_source(source):
            break
        dynamic_url = next_url(source, payload, response_headers, final_url, url)
        if dynamic_url:
            sleep_retry_backoff(float(limits.get("page_backoff_seconds", 0) or 0), 1)
    return records


def _request_with_retry(
    url: str, *, method: str, headers: dict[str, str], body: bytes | None, timeout: int, attempts: int, backoff: float, parse_json: bool
) -> tuple[Any, dict[str, str], str, int, str]:
    last_error: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            request = urllib.request.Request(url, method=method, headers=headers, data=body)
            with _open_request(request, timeout=timeout) as response:
                raw = response.read()
                encoding = response.headers.get_content_charset() if hasattr(response.headers, "get_content_charset") else None
                response_headers = dict(response.headers.items())
                final_url = response.geturl()
        except urllib.error.HTTPError as exc:
            last_error = exc
            if not is_retryable_http_error(exc):
                raise
        except Exception as exc:
            last_error = exc
            if not is_retryable_network_error(exc):
                raise
        else:
            text = raw.decode(encoding or "utf-8")
            payload = json.loads(text) if parse_json and text else None
            return payload, response_headers, final_url, len(raw), text
        if attempt < max(1, attempts):
            sleep_retry_backoff(backoff, attempt)
    assert last_error is not None
    raise last_error


def _records_from_payload(payload: Any, records_path: object) -> list[dict[str, Any]]:
    selected = json_path(payload, str(records_path)) if records_path else payload
    if selected is None:
        return []
    if isinstance(selected, list):
        return [item if isinstance(item, dict) else {"value": item} for item in selected]
    if isinstance(selected, dict):
        return [selected]
    return [{"value": selected}]


def _request_body(request: dict[str, Any], incremental: dict[str, Any] | None = None, watermark: str | None = None) -> bytes | None:
    if "json" in request:
        payload = request["json"]
        if watermark and incremental and incremental.get("watermark_body_field"):
            if not isinstance(payload, dict):
                raise ValueError("source.incremental.watermark_body_field requires source.request.json object")
            payload = {**payload, str(incremental["watermark_body_field"]): watermark}
        return json.dumps(payload).encode("utf-8")
    if watermark and incremental and incremental.get("watermark_body_field"):
        raise ValueError("source.incremental.watermark_body_field requires source.request.json")
    body = request.get("body")
    if body is None:
        return None
    return body.encode("utf-8") if isinstance(body, str) else bytes(body)


def _enforce_limits(response_bytes: int, total_bytes: int, max_page_bytes: int, max_total_bytes: int) -> None:
    if max_page_bytes > 0 and response_bytes > max_page_bytes:
        raise ValueError(f"REST API response exceeded limits.max_page_bytes: {response_bytes} > {max_page_bytes}")
    if max_total_bytes > 0 and total_bytes > max_total_bytes:
        raise ValueError(f"REST API response exceeded limits.max_total_bytes: {total_bytes} > {max_total_bytes}")


def _enforce_record_limit(records_read: int, max_records: int) -> None:
    if max_records > 0 and records_read > max_records:
        raise ValueError(f"REST API response exceeded limits.max_records: {records_read} > {max_records}")


def _respect_rate_limit(min_request_interval: float, last_request_at: float) -> None:
    if min_request_interval <= 0 or last_request_at <= 0:
        return
    elapsed = time.monotonic() - last_request_at
    if elapsed < min_request_interval:
        time.sleep(min_request_interval - elapsed)


def _watermark_value(source: dict[str, Any]) -> str | None:
    incremental = _dict(source.get("incremental"))
    runtime = _dict(source.get("runtime"))
    read = _dict(source.get("read"))
    value = (
        incremental.get("watermark_value")
        or runtime.get("watermark_value")
        or read.get("_contractforge_watermark_previous")
    )
    return extract_watermark_field_value(str(value), str(incremental.get("watermark_column") or "")) if value is not None else None


def _is_simple_column(value: str) -> bool:
    return bool(value) and value.replace("_", "").isalnum() and not value[0].isdigit()


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_dict(value: object) -> dict[str, str]:
    return {str(key): str(item) for key, item in _dict(value).items()}

