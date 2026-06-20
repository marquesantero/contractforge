"""Facade for the API connector family."""

from contractforge_core.connectors.api.rest import (
    REST_API_CONNECTORS,
    is_rest_api_connector,
    read_rest_api_records,
    rest_api_descriptor,
    rest_request_headers,
)

__all__ = [
    "REST_API_CONNECTORS",
    "is_rest_api_connector",
    "read_rest_api_records",
    "rest_api_descriptor",
    "rest_request_headers",
]
