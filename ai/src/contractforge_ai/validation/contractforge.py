"""Validation adapter for ContractForge Core."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from contractforge_ai.models import EvidenceItem, Finding, Traceability, ValidationResult


def validate_with_contractforge(contract: dict[str, Any]) -> ValidationResult:
    """Validate a contract with the required ContractForge Core package."""

    if not isinstance(contract, dict):
        return ValidationResult(
            status="FAIL",
            summary="ContractForge validation requires a contract mapping.",
            findings=[
                _finding(
                    code="contractforge.validation.invalid_type",
                    severity="critical",
                    title="Contract is not a mapping",
                    detail="The ContractForge adapter can only validate dictionary-like contracts.",
                    recommendation="Regenerate the contract or inspect the generator output.",
                )
            ],
            traceability=_traceability("invalid_type", confidence=1.0, review_required=True),
        )

    try:
        contracts_module = import_module("contractforge_core.contracts")
    except ModuleNotFoundError as exc:
        if exc.name == "contractforge_core":
            return ValidationResult(
                status="FAIL",
                summary="ContractForge Core package is not available in this environment.",
                findings=[
                    _finding(
                        code="contractforge.validation.package_unavailable",
                        severity="critical",
                        title="ContractForge Core package is not available",
                        detail="ContractForge AI requires contractforge-core but could not import contractforge_core.contracts.",
                        recommendation="Install contractforge-ai with its required dependencies or install contractforge-core in this environment.",
                    )
                ],
                traceability=_traceability("package_unavailable", confidence=1.0, review_required=True),
            )
        return ValidationResult(
            status="FAIL",
            summary=f"ContractForge Core dependency is not available: {exc.name}.",
            findings=[
                _finding(
                    code="contractforge.validation.dependency_unavailable",
                    severity="critical",
                    title="ContractForge Core dependency is not available",
                    detail=(
                        f"The ContractForge validation adapter found the ContractForge Core package, "
                        f"but importing it failed because dependency {exc.name!r} is unavailable."
                    ),
                    recommendation="Install contractforge-ai with its required dependencies or repair the contractforge-core installation.",
                )
            ],
            traceability=_traceability("dependency_unavailable", confidence=1.0, review_required=True),
        )
    except Exception as exc:
        return ValidationResult(
            status="WARN",
            summary=f"ContractForge Core package import failed: {type(exc).__name__}: {exc}",
            findings=[
                _finding(
                    code="contractforge.validation.import_failed",
                    severity="medium",
                    title="ContractForge Core import failed",
                    detail=f"Import failed with {type(exc).__name__}: {exc}",
                    recommendation="Check the installed contractforge-core package and its dependencies.",
                )
            ],
            traceability=_traceability("import_failed", confidence=0.80, review_required=True),
        )

    semantic_contract_from_mapping = getattr(contracts_module, "semantic_contract_from_mapping", None)
    if semantic_contract_from_mapping is None:
        return ValidationResult(
            status="FAIL",
            summary="ContractForge Core is installed but semantic contract normalization is not available.",
            findings=[
                _finding(
                    code="contractforge.validation.unsupported_package",
                    severity="critical",
                    title="Unsupported ContractForge Core package shape",
                    detail="contractforge_core.contracts.semantic_contract_from_mapping was not found.",
                    recommendation="Use a contractforge-core version that exposes public contract normalization.",
                )
            ],
            traceability=_traceability("unsupported_package", confidence=0.80, review_required=True),
        )

    normalized = dict(contract)
    normalized.pop("_metadata", None)
    try:
        semantic = semantic_contract_from_mapping(normalized)
    except Exception as exc:
        return ValidationResult(
            status="FAIL",
            summary=f"ContractForge Core rejected the generated contract: {type(exc).__name__}: {exc}",
            findings=[
                _finding(
                    code="contractforge.validation.contract_rejected",
                    severity="critical",
                    title="ContractForge Core rejected the generated contract",
                    detail=f"Validation failed with {type(exc).__name__}: {exc}",
                    recommendation="Fix the generated contract before treating the scaffold as usable.",
                )
            ],
            traceability=_traceability("contract_rejected", confidence=1.0, review_required=True),
        )

    return ValidationResult(
        status="PASS",
        summary="ContractForge Core accepted the generated contract.",
        findings=[],
        traceability=Traceability(
            confidence=1.0,
            evidence=[
                EvidenceItem(
                    source="contractforge_core",
                    reason="Validated generated contract with ContractForge Core semantic normalization.",
                    value={
                        "target_table": getattr(getattr(semantic, "target", None), "name", None),
                        "layer": getattr(getattr(semantic, "target", None), "layer", None),
                        "mode": getattr(getattr(semantic, "write", None), "mode", None),
                    },
                    confidence=1.0,
                )
            ],
            review_required=False,
        ),
    )


def _finding(
    *,
    code: str,
    severity: str,
    title: str,
    detail: str,
    recommendation: str,
) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        recommendation=recommendation,
        evidence=[
            EvidenceItem(
                source="contractforge_core",
                reason=f"ContractForge validation adapter produced {code!r}.",
                confidence=1.0,
            )
        ],
    )


def _traceability(reason: str, *, confidence: float, review_required: bool) -> Traceability:
    return Traceability(
        confidence=confidence,
        evidence=[
            EvidenceItem(
                source="contractforge_core",
                reason=f"ContractForge validation adapter result: {reason}.",
                confidence=confidence,
            )
        ],
        review_required=review_required,
    )
