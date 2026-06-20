"""Platform-neutral operational error normalization."""

from __future__ import annotations

from typing import Any, Mapping

from contractforge_core.security import redact_text

FAILURE_STATUSES = {"FAILED", "ABORTED"}

PREFERRED_ERROR_TOKENS = (
    "CAUSED BY:",
    "STORAGEEXCEPTION:",
    "PSQLEXCEPTION:",
    "SQLEXCEPTION:",
    "ANALYSISEXCEPTION:",
    "DELTA",
)


def short_error_message(text: str, *, limit: int = 1000, preferred_tokens: tuple[str, ...] = PREFERRED_ERROR_TOKENS) -> str:
    redacted = redact_text(text or "")
    lines = [line.strip() for line in redacted.splitlines() if line.strip()]
    if not lines:
        return ""
    preferred = _preferred_line(lines, preferred_tokens)
    return preferred[:limit]


def exception_message(exc: Exception, *, limit: int = 1000, preferred_tokens: tuple[str, ...] = PREFERRED_ERROR_TOKENS) -> str:
    return short_error_message(str(exc), limit=limit, preferred_tokens=preferred_tokens)


class ContractForgeExecutionError(RuntimeError):
    """Raised when an execution result reports a failed terminal status."""

    def __init__(self, result: Mapping[str, Any]) -> None:
        self.result = dict(result)
        self.status = str(result.get("status") or "UNKNOWN")
        self.run_id = result.get("run_id") or result.get("stream_run_id")
        self.target = result.get("target") or result.get("target_table")
        raw_message = str(result.get("error_message") or result.get("message") or "")
        self.error_message = short_error_message(raw_message) or f"Execution returned status {self.status}"
        run = f", run_id={self.run_id}" if self.run_id else ""
        super().__init__(
            f"ContractForge execution failed for {self.target or 'unknown target'} "
            f"(status={self.status}{run}): {self.error_message}"
        )


def raise_for_failure_result(result: Mapping[str, Any]) -> None:
    """Raise when a result mapping reports a failed terminal status."""
    if str(result.get("status") or "").upper() in FAILURE_STATUSES:
        raise ContractForgeExecutionError(result)


def _preferred_line(lines: list[str], preferred_tokens: tuple[str, ...]) -> str:
    for line in reversed(lines):
        upper = line.upper()
        if any(token in upper for token in preferred_tokens):
            return line
    return lines[-1]
