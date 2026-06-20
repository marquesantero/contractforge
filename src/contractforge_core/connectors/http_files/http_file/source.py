"""Platform-neutral HTTP bounded-file source helpers."""

from __future__ import annotations

import base64
import urllib.parse
from typing import Any

HTTP_FILE_TYPES = frozenset({"http_file", "http_csv", "http_json", "http_text"})


def is_http_file_source(source: dict[str, Any]) -> bool:
    return source.get("type") in HTTP_FILE_TYPES or source.get("connector") in HTTP_FILE_TYPES


def http_file_format(source: dict[str, Any]) -> str:
    source_type = source.get("type") or source.get("connector")
    if source_type == "http_csv":
        return "csv"
    if source_type == "http_json":
        return "json"
    if source_type == "http_text":
        return "text"
    file_format = source.get("format")
    if not file_format:
        raise ValueError("http_file source requires format")
    return "json" if file_format in {"jsonl", "ndjson"} else str(file_format)


def http_file_headers(source: dict[str, Any]) -> dict[str, str]:
    request = source.get("request", {})
    headers = {str(key): str(value) for key, value in request.get("headers", {}).items()}
    auth = source.get("auth", {})
    auth_type = str(auth.get("type") or "none").strip().lower()
    if auth_type == "bearer_token":
        token = auth.get("token")
        if not token:
            raise ValueError("HTTP bearer_token auth requires auth.token")
        headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        header = auth.get("header", "X-Api-Key")
        value = auth.get("value")
        if not value:
            raise ValueError("HTTP api_key auth requires auth.value")
        headers[str(header)] = str(value)
    elif auth_type == "basic":
        username = auth.get("username")
        password = auth.get("password")
        if not username or not password:
            raise ValueError("HTTP basic auth requires auth.username and auth.password")
        raw = f"{username}:{password}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    elif auth_type in {"", "none"}:
        pass
    else:
        raise ValueError(f"auth.type={auth_type!r} is not supported for HTTP file sources")
    return headers


def http_file_params(source: dict[str, Any]) -> dict[str, str]:
    request = source.get("request", {})
    return {str(key): str(value) for key, value in request.get("params", {}).items()}


def http_file_url(source: dict[str, Any]) -> str:
    request = source.get("request", {}) if isinstance(source.get("request"), dict) else {}
    url = str(source.get("url") or request.get("url") or "").strip()
    if not url:
        raise ValueError("HTTP file source requires request.url")
    params = http_file_params(source)
    if not params:
        return url
    separator = "&" if "?" in url else "?"
    return url + separator + urllib.parse.urlencode(params)


def http_file_reader_options(source: dict[str, Any]) -> dict[str, str]:
    options = {}
    for key, value in source.get("options", {}).items():
        if key != "format":
            options[str(key)] = str(value).lower() if isinstance(value, bool) else str(value)
    return options
