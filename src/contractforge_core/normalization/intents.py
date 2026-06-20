"""Normalize validated mappings into semantic intent objects."""

from __future__ import annotations

from typing import Any

from contractforge_core.semantic.models import GovernanceIntent, OperationsIntent, SourceIntent, TargetIntent


def source_intent(source: Any) -> SourceIntent:
    if isinstance(source, str):
        return SourceIntent(name=source, kind="table", location=source)
    if isinstance(source, dict):
        intent = source.get("intent")
        if source.get("type") == "connector":
            name = source.get("name") or source.get("connector") or "connector_source"
            location = source.get("path") or source.get("url") or source.get("table")
            kind = str(intent or f"connector:{source.get('connector')}")
            return SourceIntent(name=str(name), kind=kind, location=location, raw=source)
        table_ref = source.get("ref") or source.get("table_ref")
        name = source.get("name") or source.get("path") or source.get("table") or table_ref or source.get("object") or "source"
        location = source.get("path") or source.get("url") or source.get("table") or table_ref
        return SourceIntent(name=str(name), kind=str(intent or source.get("type", "source")), location=location, raw=source)
    raise ValueError("Contract requires a source.")


def target_intent(contract: dict[str, Any]) -> TargetIntent:
    target = contract.get("target")
    if not isinstance(target, dict) or not target.get("table"):
        raise ValueError("Contract requires target.table (declare target: {catalog, schema, table}).")

    namespace = ".".join(str(part) for part in (target.get("catalog"), target.get("schema")) if part)

    return TargetIntent(
        name=str(target["table"]),
        layer=str(contract.get("layer") or "bronze"),
        namespace=namespace or None,
        domain=str(contract["domain"]) if contract.get("domain") else None,
        catalog_type=str(target["catalog_type"]) if target.get("catalog_type") else None,
    )


def governance_intent(contract: dict[str, Any], access: Any, annotations: Any) -> GovernanceIntent | None:
    owner = contract.get("owner")
    row_filters: tuple[str, ...] = ()
    column_masks: tuple[str, ...] = ()

    if isinstance(access, dict):
        row_filters = tuple(str(item.get("name") or item.get("function")) for item in access.get("row_filters", ()))
        column_masks = tuple(str(item.get("column")) for item in access.get("column_masks", ()))

    if owner or row_filters or column_masks or access or annotations:
        return GovernanceIntent(
            owner=owner,
            row_filters=row_filters,
            column_masks=column_masks,
            access=access if isinstance(access, dict) else None,
            annotations=annotations if isinstance(annotations, dict) else None,
        )
    return None


def operations_intent(contract: dict[str, Any], operations: Any, source: Any, execution: Any = None) -> OperationsIntent:
    execution_dict = execution if isinstance(execution, dict) else {}
    source_available_now = isinstance(source, dict) and source.get("trigger") == "available_now"
    execution_available_now = execution_dict.get("preferred") == "available_now"
    available_now = source_available_now or execution_available_now
    require_evidence = not bool(contract.get("dry_run", False))
    if isinstance(operations, dict) and operations.get("operations"):
        require_evidence = True
    metadata = _operation_metadata(contract, operations, execution)
    return OperationsIntent(
        available_now_streaming=available_now,
        require_production_evidence=require_evidence,
        metadata=metadata or None,
    )


def _operation_metadata(contract: dict[str, Any], operations: Any, execution: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if isinstance(operations, dict):
        metadata.update(operations)
    for key in (
        "sla",
        "runtime_parameters",
        "schemas",
        "on_quality_fail",
        "select_columns",
        "column_mapping",
        "filter_expression",
        "watermark_columns",
        "idempotency_key",
        "idempotency_policy",
        "retry_attempts",
        "retry_backoff_seconds",
        "applied_presets",
        "parent_run_id",
        "run_group_id",
        "master_job_id",
        "master_run_id",
    ):
        value = contract.get(key)
        if key == "idempotency_policy" and value == "always_run":
            continue
        if key == "on_quality_fail" and value == "fail":
            continue
        if value not in (None, "", [], {}):
            metadata[key] = contract[key]
    if isinstance(execution, dict):
        metadata["execution"] = execution
    return metadata
