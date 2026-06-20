"""Facade for the bounded REST API connector."""

from contractforge_core.connectors.api.rest.auth import rest_request_headers
from contractforge_core.connectors.api.rest.pagination import (
    json_path,
    link_header_next,
    max_pages_for_source,
    next_url,
    page_urls,
    pagination_type,
    url_with_params,
)
from contractforge_core.connectors.api.rest.reader import read_rest_api_records
from contractforge_core.connectors.api.rest.retry import (
    RETRYABLE_HTTP_STATUS,
    is_retryable_http_error,
    is_retryable_network_error,
    sleep_retry_backoff,
)
from contractforge_core.connectors.api.rest.safety import (
    ALLOW_PRIVATE_FLAG,
    ALLOWED_SCHEMES,
    validate_http_target,
)
from contractforge_core.connectors.api.rest.source import (
    REST_API_CONNECTORS,
    is_rest_api_connector,
    rest_api_descriptor,
)

__all__ = [
    "ALLOWED_SCHEMES",
    "ALLOW_PRIVATE_FLAG",
    "REST_API_CONNECTORS",
    "RETRYABLE_HTTP_STATUS",
    "is_retryable_http_error",
    "is_retryable_network_error",
    "is_rest_api_connector",
    "json_path",
    "link_header_next",
    "max_pages_for_source",
    "next_url",
    "page_urls",
    "pagination_type",
    "read_rest_api_records",
    "rest_api_descriptor",
    "rest_request_headers",
    "sleep_retry_backoff",
    "url_with_params",
    "validate_http_target",
]
