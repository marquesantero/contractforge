"""Optional Lake Formation application helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from contractforge_aws.runtime.dependencies import require_boto3

_ACCOUNT_PLACEHOLDER = "REPLACE_WITH_AWS_ACCOUNT_ID"


@dataclass(frozen=True)
class LakeFormationApplyResult:
    permissions_granted: int
    data_cells_filters_created: int
    data_cells_filter_grants: int
    skipped_data_cells_filters: int


def apply_lake_formation_plan(
    plan: str | dict[str, Any],
    *,
    lakeformation_client: Any | None = None,
    account_id: str | None = None,
    allow_data_cells_filters: bool = False,
) -> LakeFormationApplyResult:
    """Apply an explicitly-rendered Lake Formation plan.

    Grant requests are directly applyable. Data cell filters remain
    review-required, so they are skipped unless the caller explicitly opts in
    and provides a concrete AWS account id for ``TableCatalogId``.
    """

    payload = _plan_payload(plan)
    client = lakeformation_client or require_boto3().client("lakeformation")
    permissions = _permissions(payload)
    filters = _filters(payload)
    granted = 0
    for request in permissions:
        client.grant_permissions(**request)
        granted += 1

    if not allow_data_cells_filters:
        return LakeFormationApplyResult(
            permissions_granted=granted,
            data_cells_filters_created=0,
            data_cells_filter_grants=0,
            skipped_data_cells_filters=len(filters),
        )

    concrete_account_id = _required_account_id(account_id)
    created = 0
    filter_grants = 0
    for entry in filters:
        request = _with_account_id(entry.get("create_data_cells_filter"), concrete_account_id)
        if request:
            client.create_data_cells_filter(**request)
            created += 1
        for grant in entry.get("grants") or ():
            client.grant_permissions(**_with_account_id(grant, concrete_account_id))
            filter_grants += 1
    return LakeFormationApplyResult(
        permissions_granted=granted,
        data_cells_filters_created=created,
        data_cells_filter_grants=filter_grants,
        skipped_data_cells_filters=0,
    )


def _plan_payload(plan: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan, str):
        loaded = json.loads(plan)
        if not isinstance(loaded, dict):
            raise ValueError("Lake Formation plan JSON must decode to an object")
        return loaded
    return dict(plan)


def _permissions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    values = plan.get("permissions")
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, dict)]


def _filters(plan: dict[str, Any]) -> list[dict[str, Any]]:
    values = plan.get("data_cells_filters")
    if not isinstance(values, list):
        return []
    return [dict(item) for item in values if isinstance(item, dict)]


def _required_account_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("account_id is required when applying Lake Formation data cell filters")
    return text


def _with_account_id(value: Any, account_id: str) -> dict[str, Any]:
    replaced = _replace_account_placeholder(value, account_id)
    if not isinstance(replaced, dict):
        raise ValueError("Lake Formation request must be an object")
    return replaced


def _replace_account_placeholder(value: Any, account_id: str) -> Any:
    if isinstance(value, dict):
        return {key: _replace_account_placeholder(item, account_id) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_account_placeholder(item, account_id) for item in value]
    return account_id if value == _ACCOUNT_PLACEHOLDER else value
