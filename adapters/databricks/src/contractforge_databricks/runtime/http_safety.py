"""Compatibility re-exports for the core HTTP target safety policy."""

from contractforge_core.connectors.api.rest import (
    ALLOWED_SCHEMES,
    ALLOW_PRIVATE_FLAG,
    validate_http_target,
)

__all__ = ["ALLOWED_SCHEMES", "ALLOW_PRIVATE_FLAG", "validate_http_target"]
