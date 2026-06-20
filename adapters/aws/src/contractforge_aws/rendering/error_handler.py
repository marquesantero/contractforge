"""Render protected AWS Glue error-evidence handling blocks."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.failure_runtime import render_evidence_failure_write
from contractforge_aws.evidence.runtime import render_error_evidence_write


def render_error_evidence_handler(
    contract: SemanticContract,
    *,
    evidence_database_name: str | None = None,
) -> list[str]:
    """Render an ``except`` block that preserves the original job failure.

    Error evidence is observability, not the primary workload. If writing the
    error row fails because Glue Catalog, Iceberg or permissions are unavailable,
    the generated job reports that secondary failure and re-raises the original
    exception.
    """

    return [
        "except Exception as _cf_exc:",
        "    try:",
        *_indent(render_error_evidence_write(contract, evidence_database_name=evidence_database_name).splitlines(), 2),
        "",
        *_indent(render_evidence_failure_write(contract, evidence_database_name=evidence_database_name).splitlines(), 2),
        "    except Exception as _cf_evidence_exc:",
        "        print('ContractForge AWS error evidence write failed: ' + _cf_redact_error_text(str(_cf_evidence_exc)))",
        "    raise",
        "",
    ]


def _indent(lines: list[str], levels: int) -> list[str]:
    prefix = "    " * levels
    return [f"{prefix}{line}" if line.strip() else "" for line in lines]
