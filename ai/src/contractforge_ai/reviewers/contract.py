"""Deterministic contract review engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contractforge_ai.context.loaders import load_contract
from contractforge_ai.models import EvidenceItem, Finding, ReviewResult, Severity, Traceability
from contractforge_ai.write_modes import canonical_write_mode

HIGH_RISK_MODES = {"scd1_upsert", "scd1_hash_diff", "scd2_historical", "snapshot_soft_delete"}
FILE_CONNECTORS = {"files", "local_files", "s3", "azure_blob", "object_storage", "http_file", "autoloader"}
JSON_FORMATS = {"json", "jsonl"}


@dataclass(frozen=True)
class BundleReviewContext:
    """Sibling contract files considered during bundle-aware review."""

    enabled: bool = False
    annotations_path: Path | None = None
    operations_path: Path | None = None
    annotations_loaded: bool = False
    operations_loaded: bool = False


def review_contract(path: str | Path, *, bundle: bool = False) -> ReviewResult:
    """Review a ContractForge contract and return deterministic findings."""

    contract_path = Path(path)
    contract, bundle_context = _load_review_contract(contract_path, bundle=bundle)
    findings: list[Finding] = []

    _check_target(contract, findings)
    _check_write_mode(contract, findings)
    _check_quality(contract, findings)
    _check_file_schema(contract, findings)
    _check_governance(contract, findings, bundle_context)
    _check_streaming(contract, findings)

    risk = _max_risk([finding.severity for finding in findings])
    status = "FAIL" if risk in {"critical"} else "WARN" if findings else "PASS"
    summary = _summary(status, findings)

    return ReviewResult(
        status=status,
        risk=risk,
        contract_path=str(contract_path),
        findings=findings,
        summary=summary,
        traceability=Traceability(
            confidence=1.0,
            evidence=[
                EvidenceItem(
                    source="contract",
                    path=str(contract_path),
                    reason="Deterministic review evaluated the loaded contract.",
                    value={
                        "findings": len(findings),
                        "bundle_review": bundle_context.enabled,
                        "annotations_loaded": bundle_context.annotations_loaded,
                        "operations_loaded": bundle_context.operations_loaded,
                    },
                    confidence=1.0,
                )
            ],
            review_required=bool(findings),
        ),
    )


def _load_review_contract(path: Path, *, bundle: bool) -> tuple[dict[str, Any], BundleReviewContext]:
    contract = load_contract(path)
    if not bundle:
        return contract, BundleReviewContext()

    annotations_path = _sibling_contract_path(path, "annotations")
    operations_path = _sibling_contract_path(path, "operations")
    annotations_loaded = _merge_sibling_contract(contract, "annotations", annotations_path)
    operations_loaded = _merge_sibling_contract(contract, "operations", operations_path)

    return contract, BundleReviewContext(
        enabled=True,
        annotations_path=annotations_path,
        operations_path=operations_path,
        annotations_loaded=annotations_loaded,
        operations_loaded=operations_loaded,
    )


def _sibling_contract_path(path: Path, kind: str) -> Path:
    marker = ".ingestion"
    name = path.name
    if marker in name:
        return path.with_name(name.replace(marker, f".{kind}", 1))
    return path.with_name(f"{path.stem}.{kind}{path.suffix}")


def _merge_sibling_contract(contract: dict[str, Any], key: str, path: Path) -> bool:
    if contract.get(key) or not path.exists():
        return False

    sibling = load_contract(path)
    payload = sibling.get(key) if isinstance(sibling.get(key), dict) else sibling
    if not isinstance(payload, dict) or not payload:
        return False

    contract[key] = payload
    return True


def _finding(
    *,
    code: str,
    severity: Severity,
    title: str,
    detail: str,
    recommendation: str,
    path: str | None = None,
) -> Finding:
    """Create a finding with standard deterministic contract-review evidence."""

    return Finding(
        code=code,
        severity=severity,
        title=title,
        detail=detail,
        recommendation=recommendation,
        path=path,
        evidence=[
            EvidenceItem(
                source="contract",
                path=path,
                reason=f"Deterministic rule {code!r} identified this condition.",
                confidence=1.0,
            )
        ],
    )


def _check_target(contract: dict[str, Any], findings: list[Finding]) -> None:
    target = _mapping(contract.get("target"))
    catalog = target.get("catalog") or contract.get("catalog")
    schema = target.get("schema") or contract.get("target_schema")
    table = target.get("table") or contract.get("target_table")

    if not table:
        findings.append(
            _finding(
                code="target.table.missing",
                severity="critical",
                title="Target table is missing",
                detail="The contract does not declare target.table or target_table.",
                recommendation="Declare the target table explicitly.",
                path="target.table",
            )
        )

    if not schema:
        findings.append(
            _finding(
                code="target.schema.missing",
                severity="high",
                title="Target schema is missing",
                detail="The contract does not declare target.schema or target_schema.",
                recommendation="Declare the target schema explicitly instead of relying on a default layer convention.",
                path="target.schema",
            )
        )

    if not catalog:
        findings.append(
            _finding(
                code="target.catalog.missing",
                severity="medium",
                title="Target catalog is missing",
                detail="The contract does not declare a catalog.",
                recommendation="Declare catalog to avoid runtime-dependent namespace resolution.",
                path="target.catalog",
            )
        )


def _check_write_mode(contract: dict[str, Any], findings: list[Finding]) -> None:
    declared_mode = str(contract.get("mode") or "").strip()
    mode = canonical_write_mode(declared_mode)
    merge_keys = _list(contract.get("merge_keys") or contract.get("keys"))
    quality = _mapping(contract.get("quality_rules"))
    not_null = set(_list(quality.get("not_null")))

    if mode in HIGH_RISK_MODES and not merge_keys:
        findings.append(
            _finding(
                code="write.keys.missing",
                severity="critical",
                title="Write mode requires keys",
                detail=f"Mode {declared_mode!r} requires stable keys, but no merge_keys/keys were declared.",
                recommendation="Declare merge_keys and add not_null quality rules for those keys.",
                path="merge_keys",
            )
        )

    missing_not_null = [key for key in merge_keys if key not in not_null]
    if merge_keys and missing_not_null:
        findings.append(
            _finding(
                code="write.keys.nullable",
                severity="high",
                title="Merge keys are not protected by quality rules",
                detail=f"The following merge keys do not have not_null checks: {', '.join(missing_not_null)}.",
                recommendation="Add all merge keys to quality_rules.not_null to prevent unsafe merges.",
                path="quality_rules.not_null",
            )
        )

    if mode == "snapshot_soft_delete" and (contract.get("watermark_columns") or contract.get("filter_expression")):
        findings.append(
            _finding(
                code="snapshot.incremental.conflict",
                severity="critical",
                title="Snapshot soft delete cannot be filtered incrementally",
                detail="snapshot_soft_delete must see the complete active source snapshot.",
                recommendation="Remove watermark/filter settings or use a different write mode.",
                path="mode",
            )
        )


def _check_quality(contract: dict[str, Any], findings: list[Finding]) -> None:
    quality = _mapping(contract.get("quality_rules"))
    declared_mode = str(contract.get("mode") or "").strip()
    mode = canonical_write_mode(declared_mode)

    if not quality:
        findings.append(
            _finding(
                code="quality.missing",
                severity="medium",
                title="No quality rules declared",
                detail="The contract has no quality_rules block.",
                recommendation="Add at least not_null checks for keys and critical business columns.",
                path="quality_rules",
            )
        )
        return

    if mode in HIGH_RISK_MODES and not quality.get("not_null"):
        findings.append(
            _finding(
                code="quality.keys.not_null.missing",
                severity="high",
                title="High-risk write mode has no not_null rules",
                detail=f"Mode {declared_mode!r} should protect merge/effective keys against nulls.",
                recommendation="Declare quality_rules.not_null for all key columns.",
                path="quality_rules.not_null",
            )
        )


def _check_file_schema(contract: dict[str, Any], findings: list[Finding]) -> None:
    source = _mapping(contract.get("source"))
    connector = str(source.get("connector") or source.get("type") or "").strip()
    fmt = str(source.get("format") or source.get("source_format") or "").lower().strip()
    read = _mapping(source.get("read"))
    shape = _mapping(contract.get("shape") or contract.get("transform"))

    if connector in FILE_CONNECTORS and fmt in JSON_FORMATS and not read.get("schema") and not shape.get("parse_json"):
        findings.append(
            _finding(
                code="source.json.schema.missing",
                severity="high",
                title="JSON source has no explicit schema",
                detail="JSON ingestion without explicit schema can produce unstable contracts and runtime-dependent inference.",
                recommendation="Declare source.read.schema or parse JSON explicitly with shape.parse_json.",
                path="source.read.schema",
            )
        )

    if connector == "autoloader":
        if not read.get("checkpoint_location"):
            findings.append(
                _finding(
                    code="autoloader.checkpoint.missing",
                    severity="critical",
                    title="Auto Loader checkpoint is missing",
                    detail="Auto Loader requires a durable checkpoint location.",
                    recommendation="Declare source.read.checkpoint_location.",
                    path="source.read.checkpoint_location",
                )
            )
        if not read.get("schema_location"):
            findings.append(
                _finding(
                    code="autoloader.schema_location.missing",
                    severity="high",
                    title="Auto Loader schema location is missing",
                    detail="Schema tracking should be durable and table-specific.",
                    recommendation="Declare source.read.schema_location.",
                    path="source.read.schema_location",
                )
            )


def _check_governance(
    contract: dict[str, Any],
    findings: list[Finding],
    bundle_context: BundleReviewContext,
) -> None:
    annotations = _mapping(contract.get("annotations"))
    operations = _mapping(contract.get("operations"))

    if not annotations and not contract.get("description"):
        if bundle_context.enabled:
            findings.append(
                _finding(
                    code="annotations.sibling.missing",
                    severity="low",
                    title="No annotations sibling metadata found",
                    detail=(
                        "Bundle-aware review did not find annotations in the ingestion contract or in the expected "
                        f"sibling file {str(bundle_context.annotations_path)!r}."
                    ),
                    recommendation="Add a sibling .annotations.yaml file or include annotations in the reviewed contract.",
                    path="annotations",
                )
            )
        else:
            findings.append(
                _finding(
                    code="annotations.missing",
                    severity="low",
                    title="No annotations metadata found",
                    detail="The contract does not include annotations or a table description.",
                    recommendation="Add annotations for table description, column descriptions, tags and PII when applicable.",
                    path="annotations",
                )
            )

    if not operations:
        if bundle_context.enabled:
            findings.append(
                _finding(
                    code="operations.sibling.missing",
                    severity="low",
                    title="No operations sibling metadata found",
                    detail=(
                        "Bundle-aware review did not find operations in the ingestion contract or in the expected "
                        f"sibling file {str(bundle_context.operations_path)!r}."
                    ),
                    recommendation="Add a sibling .operations.yaml file or include operations in the reviewed contract.",
                    path="operations",
                )
            )
        else:
            findings.append(
                _finding(
                    code="operations.missing",
                    severity="low",
                    title="No operations metadata found",
                    detail="The contract does not include operational ownership or SLA metadata.",
                    recommendation="Add operations metadata such as owner, support group, criticality and runbook URL.",
                    path="operations",
                )
            )


def _check_streaming(contract: dict[str, Any], findings: list[Finding]) -> None:
    source = _mapping(contract.get("source"))
    connector = str(source.get("connector") or "").strip()
    read = _mapping(source.get("read"))

    if connector in {"eventhubs", "kafka"} and read.get("available_now"):
        findings.append(
            _finding(
                code="streaming.available_now.unsupported_source",
                severity="medium",
                title="Available-now should be explicit by connector capability",
                detail=f"Connector {connector!r} is streaming-oriented and may not support available-now semantics like Auto Loader.",
                recommendation="Use bounded offsets or a finite batch strategy supported by the connector.",
                path="source.read.available_now",
            )
        )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _max_risk(severities: list[Severity]) -> Severity:
    order: dict[Severity, int] = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    if not severities:
        return "info"
    return max(severities, key=lambda severity: order[severity])


def _summary(status: str, findings: list[Finding]) -> str:
    if not findings:
        return "No deterministic issues were found."
    critical = sum(1 for finding in findings if finding.severity == "critical")
    high = sum(1 for finding in findings if finding.severity == "high")
    return f"{status}: {len(findings)} finding(s), including {critical} critical and {high} high severity item(s)."
