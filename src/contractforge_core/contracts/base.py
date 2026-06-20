"""Shared Pydantic model configuration and error formatting."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class StrictContractModel(BaseModel):
    """Base class for first-class contract models."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class ExtensibleContractModel(BaseModel):
    """Base class for provider extension maps."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)


_NOISY_LOC_TOKENS = {"function-after[validate_connector()]"}
_UNION_VARIANT_RE = re.compile(r"^(?:function-(?:before|after)\[.*?\]|[A-Z][A-Za-z0-9_]+(?:Contract|Model)?)$")


def _clean_loc(location: tuple[Any, ...]) -> tuple[Any, ...]:
    """Strip union-variant tokens that leak through pydantic error locations."""

    cleaned: list[Any] = []
    for part in location:
        text = str(part)
        if text in _NOISY_LOC_TOKENS:
            continue
        if _UNION_VARIANT_RE.match(text):
            # Drop tokens like 'ConnectorSourceContract' or 'function-after[_validate_connector(), Model]'
            continue
        cleaned.append(part)
    return tuple(cleaned)


def _path(location: tuple[Any, ...]) -> str:
    return ".".join(str(part) for part in _clean_loc(location))


def _friendly_message(error: dict[str, Any], cleaned_loc: tuple[Any, ...]) -> str:
    base = str(error.get("msg", "Invalid value"))
    error_type = str(error.get("type", ""))
    if error_type == "extra_forbidden":
        field = str(cleaned_loc[-1]) if cleaned_loc else ""
        if field:
            return f"unexpected field '{field}'; remove it or move it to the canonical location"
        return "unexpected field; remove it or move it to the canonical location"
    if error_type == "missing":
        field = str(cleaned_loc[-1]) if cleaned_loc else "value"
        return f"required field '{field}' is missing"
    return base


def contract_validation_error(exc: ValidationError, *, prefix: str = "contract") -> ValueError:
    """Convert Pydantic errors into concise, deduplicated ContractForge validation errors.

    Pydantic emits one record per Union variant, so a single offending field
    typically produces 3+ duplicate "Extra inputs are not permitted" entries
    that differ only by the variant token in the location. We strip those
    variant tokens, deduplicate by (path, message), and rewrite the most
    common error kinds (extra_forbidden, missing) into actionable wording.
    """

    seen: set[tuple[str, str]] = set()
    messages: list[str] = []
    for error in exc.errors():
        cleaned_loc = _clean_loc(error.get("loc", ()))
        path = ".".join(str(part) for part in cleaned_loc) or prefix
        message = _friendly_message(error, cleaned_loc)
        key = (path, message)
        if key in seen:
            continue
        seen.add(key)
        messages.append(f"{prefix}.{path}: {message}")
    if not messages:
        # Fallback: at least one duplicate slipped through with empty cleanup.
        messages = [f"{prefix}: {error.get('msg', 'invalid')}" for error in exc.errors()]
    return ValueError("; ".join(messages))

