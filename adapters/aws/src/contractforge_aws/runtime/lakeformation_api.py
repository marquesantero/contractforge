"""Runtime-facing Lake Formation helper API."""

from __future__ import annotations

from typing import Any

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG
from contractforge_aws.governance.lakeformation import render_lake_formation_artifact
from contractforge_aws.governance.runtime import LakeFormationApplyResult, apply_lake_formation_plan
from contractforge_aws.subtargets import validate_aws_subtarget


def apply_aws_lake_formation_plan(
    plan: str | dict[str, Any],
    *,
    lakeformation_client: Any | None = None,
    account_id: str | None = None,
    allow_data_cells_filters: bool = False,
) -> LakeFormationApplyResult:
    return apply_lake_formation_plan(
        plan,
        lakeformation_client=lakeformation_client,
        account_id=account_id,
        allow_data_cells_filters=allow_data_cells_filters,
    )


def apply_aws_lake_formation_contract(
    contract: dict[str, Any],
    *,
    subtarget: str = AWS_SUBTARGET_GLUE_ICEBERG,
    lakeformation_client: Any | None = None,
    account_id: str | None = None,
    allow_data_cells_filters: bool = False,
) -> LakeFormationApplyResult:
    validate_aws_subtarget(subtarget)
    semantic = semantic_contract_from_mapping(contract)
    plan = render_lake_formation_artifact(semantic)
    if not plan:
        return LakeFormationApplyResult(0, 0, 0, 0)
    return apply_lake_formation_plan(
        plan,
        lakeformation_client=lakeformation_client,
        account_id=account_id,
        allow_data_cells_filters=allow_data_cells_filters,
    )


__all__ = [
    "apply_aws_lake_formation_contract",
    "apply_aws_lake_formation_plan",
]
