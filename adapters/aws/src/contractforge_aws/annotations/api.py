"""Runtime-facing AWS annotation helpers."""

from __future__ import annotations

from typing import Any

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG
from contractforge_aws.annotations.rendering import render_annotations_plan
from contractforge_aws.annotations.runtime import (
    GlueCatalogAnnotationApplyResult,
    apply_glue_catalog_annotations_plan,
)
from contractforge_aws.subtargets import validate_aws_subtarget


def apply_aws_annotations_plan(
    plan: str | dict[str, Any],
    *,
    glue_client: Any | None = None,
    catalog_id: str | None = None,
    skip_archive: bool = True,
) -> GlueCatalogAnnotationApplyResult:
    return apply_glue_catalog_annotations_plan(
        plan,
        glue_client=glue_client,
        catalog_id=catalog_id,
        skip_archive=skip_archive,
    )


def apply_aws_annotations_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    glue_client: Any | None = None,
    catalog_id: str | None = None,
    skip_archive: bool = True,
) -> GlueCatalogAnnotationApplyResult:
    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    plan = render_annotations_plan(semantic)
    if not plan:
        target = semantic.target
        return GlueCatalogAnnotationApplyResult(target.namespace or "default", target.name, "NOOP")
    return apply_glue_catalog_annotations_plan(
        plan,
        glue_client=glue_client,
        catalog_id=catalog_id,
        skip_archive=skip_archive,
    )


__all__ = ["apply_aws_annotations_contract", "apply_aws_annotations_plan"]
