"""Deterministic platform parity comparison for ContractForge projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contractforge_core.contracts import load_contract_bundle

from contractforge_ai.adapter_validation import validate_contract_with_adapter
from contractforge_ai.context.loaders import load_contract
from contractforge_ai.parity.models import ContractParityItem, ParityStatus, PlatformParityReport
from contractforge_ai.project_structure.io import iter_ingestion_files

DEFAULT_PARITY_ADAPTERS = ("databricks", "aws")


def compare_platforms(
    *,
    contract: str | Path | None = None,
    project_root: str | Path | None = None,
    adapters: tuple[str, ...] = DEFAULT_PARITY_ADAPTERS,
) -> PlatformParityReport:
    """Compare a contract or project root against adapter public planning APIs."""

    adapter_names = _adapter_names(adapters)
    contracts = [
        _parity_item(name, payload, adapters=adapter_names)
        for name, payload in _contract_payloads(contract=contract, project_root=project_root)
    ]
    return PlatformParityReport(
        status=_report_status(contracts),
        summary=_summary(contracts),
        adapters=list(adapter_names),
        contracts=contracts,
    )


def _contract_payloads(
    *,
    contract: str | Path | None,
    project_root: str | Path | None,
) -> list[tuple[str, dict[str, Any]]]:
    if contract and project_root:
        raise ValueError("Declare either contract or project_root, not both.")
    if contract:
        path = Path(contract)
        payload = load_contract_bundle(path).contract if _is_ingestion_contract(path) else load_contract(path)
        return [(path.as_posix(), payload)]
    if project_root:
        root = Path(project_root)
        return [
            (path.relative_to(root).as_posix(), load_contract_bundle(path).contract)
            for path in iter_ingestion_files(root)
        ]
    raise ValueError("contract or project_root is required.")


def _parity_item(name: str, contract: dict[str, Any], *, adapters: tuple[str, ...]) -> ContractParityItem:
    return ContractParityItem(
        name=name,
        source_type=_source_type(contract),
        target=_target_name(contract),
        write_mode=_write_mode(contract),
        platform_extension_namespaces=_platform_extension_namespaces(contract),
        adapter_outcomes=[
            validate_contract_with_adapter(contract, adapter=adapter)
            for adapter in adapters
        ],
    )


def _adapter_names(adapters: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for adapter in adapters or DEFAULT_PARITY_ADAPTERS:
        value = adapter.strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized or DEFAULT_PARITY_ADAPTERS)


def _report_status(contracts: list[ContractParityItem]) -> ParityStatus:
    statuses = [
        outcome.status
        for contract in contracts
        for outcome in contract.adapter_outcomes
    ]
    if not contracts or "INVALID" in statuses:
        return "INVALID"
    if "NEEDS_DECISIONS" in statuses:
        return "NEEDS_DECISIONS"
    return "READY"


def _summary(contracts: list[ContractParityItem]) -> str:
    contract_count = len(contracts)
    outcomes = [outcome for contract in contracts for outcome in contract.adapter_outcomes]
    ready = sum(1 for outcome in outcomes if outcome.status == "READY")
    review = sum(1 for outcome in outcomes if outcome.status == "NEEDS_DECISIONS")
    invalid = sum(1 for outcome in outcomes if outcome.status == "INVALID")
    return (
        f"{contract_count} contract(s), {len(outcomes)} adapter outcome(s): "
        f"{ready} ready, {review} need decisions, {invalid} invalid."
    )


def _source_type(contract: dict[str, Any]) -> str | None:
    source = contract.get("source")
    if isinstance(source, dict):
        return str(source.get("type") or source.get("connector") or "").strip() or None
    return None


def _target_name(contract: dict[str, Any]) -> str | None:
    target = contract.get("target")
    if isinstance(target, dict):
        parts = [target.get("catalog"), target.get("schema"), target.get("table")]
        return ".".join(str(part) for part in parts if part)
    return None


def _write_mode(contract: dict[str, Any]) -> str | None:
    value = contract.get("mode") or contract.get("write_mode")
    return str(value).strip() if value else None


def _platform_extension_namespaces(contract: dict[str, Any]) -> list[str]:
    extensions = contract.get("extensions")
    if not isinstance(extensions, dict):
        return []
    return sorted(str(key) for key in extensions)


def _is_ingestion_contract(path: Path) -> bool:
    return ".ingestion." in path.name
