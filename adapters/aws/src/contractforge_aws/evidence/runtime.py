"""Compatibility facade for AWS Glue run/error evidence rendering."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.evidence.database import evidence_database
from contractforge_aws.evidence.error_runtime import render_error_evidence_helper, render_error_evidence_write
from contractforge_aws.evidence.run_context_runtime import render_evidence_context
from contractforge_aws.evidence.run_helper_runtime import render_evidence_helper
from contractforge_aws.evidence.run_success_runtime import render_evidence_success_write


def render_evidence_write(
    contract: SemanticContract,
    *,
    dataframe_name: str = "df",
    rows_read_expression: str | None = None,
    evidence_database_name: str | None = None,
) -> str:
    return "\n".join(
        [
            render_evidence_context(
                contract,
                dataframe_name=dataframe_name,
                rows_read_expression=rows_read_expression,
                evidence_database_name=evidence_database_name,
            ),
            render_evidence_success_write(contract, evidence_database_name=evidence_database_name),
        ]
    )

