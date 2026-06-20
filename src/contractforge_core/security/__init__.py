"""Platform-neutral security helpers."""

from contractforge_core.security.redaction import REDACTED, redact_text, redact_value

redact_secrets = redact_value

__all__ = ["REDACTED", "redact_secrets", "redact_text", "redact_value"]
