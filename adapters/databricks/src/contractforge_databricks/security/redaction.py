"""Compatibility exports for platform-neutral redaction helpers."""

from contractforge_core.security import REDACTED, redact_text, redact_value

__all__ = ["REDACTED", "redact_text", "redact_value"]
