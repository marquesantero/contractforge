"""Security helpers for the Fabric adapter."""

from contractforge_core.security import REDACTED, redact_text, redact_value
from contractforge_fabric.security.secrets import (
    SECRET_PLACEHOLDER_RE,
    contains_secret_placeholder,
    render_secret_aware_literal,
    render_secret_resolver_helper,
    secret_placeholder_refs,
)

__all__ = [
    "REDACTED",
    "SECRET_PLACEHOLDER_RE",
    "contains_secret_placeholder",
    "redact_text",
    "redact_value",
    "render_secret_aware_literal",
    "render_secret_resolver_helper",
    "secret_placeholder_refs",
]
