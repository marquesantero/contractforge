"""Secret redaction helpers used before data is sent to any model provider."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|sas)",
    re.IGNORECASE,
)

SECRET_TEMPLATE_RE = re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE)
SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|sas)\s*([:=])\s*([^\s,;\[]+)",
    re.IGNORECASE,
)
BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[^'\"\s,\]}]+", re.IGNORECASE)
OPENAI_STYLE_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")


def redact_secrets(value: Any) -> Any:
    """Return a copy of *value* with common secret fields and templates redacted."""

    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if SECRET_KEY_RE.search(str(key)):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_secrets(item)
        return redacted

    if isinstance(value, str):
        redacted = SECRET_TEMPLATE_RE.sub("[REDACTED_SECRET_REF]", value)
        redacted = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted)
        redacted = BEARER_TOKEN_RE.sub("Bearer [REDACTED]", redacted)
        return OPENAI_STYLE_KEY_RE.sub("[REDACTED_API_KEY]", redacted)

    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_secrets(item) for item in value]

    return value
