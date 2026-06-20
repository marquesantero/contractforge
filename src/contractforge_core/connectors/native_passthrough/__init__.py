"""Facade for the native passthrough connector family."""

from contractforge_core.connectors.native_passthrough.native_passthrough import (
    is_native_passthrough_source,
    native_passthrough_descriptor,
    redact_secret_fields,
)

__all__ = [
    "is_native_passthrough_source",
    "native_passthrough_descriptor",
    "redact_secret_fields",
]
