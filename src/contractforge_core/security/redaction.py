"""Platform-neutral redaction helpers for artifacts and evidence."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "connection_string",
    "credential",
    "key",
    "passphrase",
    "password",
    "private",
    "sas",
    "secret",
    "session",
    "sharedaccesskey",
    "signature",
    "sfpassword",
    "token",
)
REDACTED = "***REDACTED***"
TEXT_PATTERNS = (
    re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE),
    re.compile(r"\b(Bearer|Basic)\s+[^,\s'\"}]+", re.IGNORECASE),
    re.compile(r"([a-z][a-z0-9+.-]*://)([^:/@\s]+):([^@\s]+)@", re.IGNORECASE),
    re.compile(
        r"(?i)([?&;](?:password|passwd|pwd|token|access_token|refresh_token|session_token|security_token|"
        r"x-amz-security-token|x-amz-credential|x-amz-signature|x-goog-credential|x-goog-signature|"
        r"sig|signature|sas|secret|client_secret|api_key|apikey|sfpassword|sharedaccesskey|code)=)"
        r"([^&;\s]+)"
    ),
    re.compile(
        r"(?i)\b(password|passwd|pwd|token|access_token|refresh_token|session_token|security_token|"
        r"credential|signature|sig|sas|secret|client_secret|api_key|apikey|authorization|"
        r"private_key|private-key|passphrase|sfpassword|sharedaccesskey|connection_string)"
        r"(\s*[:=]\s*)([^\s,;&})\]]+)"
    ),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL),
)


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: (REDACTED if _sensitive(key) else redact_value(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(text: str) -> str:
    redacted = text
    redacted = TEXT_PATTERNS[5].sub(REDACTED, redacted)
    redacted = TEXT_PATTERNS[0].sub(REDACTED, redacted)
    redacted = TEXT_PATTERNS[1].sub(lambda match: f"{match.group(1)} {REDACTED}", redacted)
    redacted = TEXT_PATTERNS[2].sub(lambda match: f"{match.group(1)}{REDACTED}:{REDACTED}@", redacted)
    redacted = TEXT_PATTERNS[3].sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)
    redacted = TEXT_PATTERNS[4].sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", redacted)
    return redacted


def _sensitive(key: str) -> bool:
    lower = key.lower()
    return any(token in lower for token in SENSITIVE_KEYS)
