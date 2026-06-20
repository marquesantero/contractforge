"""Pagination helpers for the platform-neutral bounded REST client."""

from __future__ import annotations

import urllib.parse
from typing import Any


def page_urls(url: str, source: dict[str, Any]) -> list[str]:
    pagination = _dict(source.get("pagination"))
    page_type = pagination_type(source)
    max_pages = max_pages_for_source(source)
    if page_type in {"none", "cursor", "link_header"}:
        return [url]
    if page_type == "page":
        page_param = str(pagination.get("page_param") or "page")
        start_page = int(pagination.get("start_page") or 1)
        return [url_with_params(url, {page_param: str(page)}) for page in range(start_page, start_page + max_pages)]
    if page_type == "offset":
        offset_param = str(pagination.get("offset_param") or "offset")
        limit_param = str(pagination.get("limit_param") or "limit")
        page_size = int(pagination.get("page_size") or 100)
        return [
            url_with_params(url, {offset_param: str(idx * page_size), limit_param: str(page_size)})
            for idx in range(max_pages)
        ]
    raise ValueError(f"pagination.type={page_type!r} is not supported")


def next_url(
    source: dict[str, Any],
    payload: Any,
    response_headers: dict[str, str],
    final_url: str,
    base_url: str,
) -> str | None:
    page_type = pagination_type(source)
    if page_type == "cursor":
        pagination = _dict(source.get("pagination"))
        cursor = json_path(payload, str(pagination.get("next_cursor_path") or "next_cursor"))
        if not cursor:
            return None
        return url_with_params(base_url, {str(pagination.get("cursor_param") or "cursor"): str(cursor)})
    if page_type == "link_header":
        linked = link_header_next(response_headers.get("Link") or response_headers.get("link"))
        return None if linked == final_url else linked
    return None


def json_path(payload: Any, path: str) -> Any:
    if not path or path == "$":
        return payload
    current = payload
    for part in path.lstrip("$").strip(".").split("."):
        if not part:
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def url_with_params(url: str, params: dict[str, str]) -> str:
    if not params:
        return url
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)


def link_header_next(value: str | None) -> str | None:
    if not value:
        return None
    for part in value.split(","):
        if 'rel="next"' not in part:
            continue
        left = part.split(";", 1)[0].strip()
        if left.startswith("<") and left.endswith(">"):
            return left[1:-1]
    return None


def pagination_type(source: dict[str, Any]) -> str:
    return str(_dict(source.get("pagination")).get("type") or "none").lower()


def max_pages_for_source(source: dict[str, Any]) -> int:
    pagination = _dict(source.get("pagination"))
    limits = _dict(source.get("limits"))
    return int(limits.get("max_pages") or pagination.get("max_pages") or 1)


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
