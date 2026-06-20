"""Compatibility re-exports for the core REST pagination helpers."""

from contractforge_core.connectors.api.rest.pagination import (
    json_path,
    link_header_next,
    max_pages_for_source,
    next_url,
    page_urls,
    pagination_type,
    url_with_params,
)

__all__ = [
    "json_path",
    "link_header_next",
    "max_pages_for_source",
    "next_url",
    "page_urls",
    "pagination_type",
    "url_with_params",
]
