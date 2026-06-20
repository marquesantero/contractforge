"""Deterministic validation for ContractForge project folder structure."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from contractforge_ai.adapter_validation import known_adapter_names, validate_contract_with_adapter
from contractforge_ai.models import EvidenceItem, Finding
from contractforge_ai.project_structure.findings import evidence, finding
from contractforge_ai.project_structure.io import first_existing, iter_ingestion_files, load_mapping
from contractforge_ai.project_structure.models import ProjectStructureFile, ProjectStructureReport, ProjectStructureStatus

_PROJECT_FILES = ("project.yaml", "project.yml", "project.json")
_FORBIDDEN_PROJECT_FIELDS = {
    "access",
    "annotations",
    "merge_keys",
    "mode",
    "operations",
    "quality_rules",
    "schema_policy",
    "source",
    "target",
    "target_schema",
    "target_table",
    "transform",
}
_LEGACY_INGESTION_FIELDS = {
    "catalog": "Use target.catalog.",
    "cluster_columns": "Use extensions.<adapter>.cluster_columns.",
    "ctrl_schema": "Move control/evidence placement to the environment contract.",
    "delta_properties": "Use extensions.databricks.delta_properties.",
    "partition_columns": "Use extensions.<adapter>.partition_columns.",
    "source_system": "Use source.system in ingestion contracts; project source_system is metadata only.",
    "target_schema": "Use target.schema.",
    "target_table": "Use target.table.",
}
_SECRET_KEYS = {"password", "passwd", "secret", "token", "api_key", "access_key", "secret_key", "private_key"}
_SECRET_TEMPLATE = re.compile(r"\{\{\s*secret:[^}]+\}\}", re.IGNORECASE)


def validate_project_structure(root: str | Path, *, adapters: tuple[str, ...] = ()) -> ProjectStructureReport:
    """Validate a ContractForge project directory before AI output is trusted."""

    project_root = Path(root)
    requested_adapters = _requested_adapters(adapters)
    findings: list[Finding] = []
    files: list[ProjectStructureFile] = []
    evidence_items: list[EvidenceItem] = []

    if not project_root.exists() or not project_root.is_dir():
        findings.append(
            finding(
                code="project_structure.root.invalid",
                severity="critical",
                title="Project root is not a directory",
                detail=f"{project_root} does not exist or is not a directory.",
                recommendation="Point validation at the ContractForge project root.",
                path=project_root,
            )
        )
        return _report(project_root, files, findings, evidence_items)

    project_path, project_payload = _load_project(project_root, findings, files)
    if project_payload is not None:
        _validate_project_payload(project_payload, project_path, project_root, findings, files)

    environments = _environment_payloads(project_payload or {}, project_root) if requested_adapters else {}
    _validate_ingestion_bundles(
        project_root,
        findings,
        files,
        evidence_items,
        adapters=requested_adapters,
        environments=environments,
    )
    evidence_items.append(
        evidence(
            "project_structure",
            "Validated project.yaml, environment files, connection files and split ingestion bundles deterministically.",
            path=project_root,
        )
    )
    return _report(project_root, files, findings, evidence_items)


def _load_project(
    root: Path,
    findings: list[Finding],
    files: list[ProjectStructureFile],
) -> tuple[Path | None, dict[str, Any] | None]:
    project_path = first_existing(root, _PROJECT_FILES)
    if project_path is None:
        findings.append(
            finding(
                code="project_structure.project_yaml.missing",
                severity="high",
                title="project.yaml is missing",
                detail="A real ContractForge project should declare project-level environments, connections, schedule and execution order.",
                recommendation="Create project.yaml at the project root.",
                path=root,
            )
        )
        return None, None
    files.append(ProjectStructureFile(kind="project", path=project_path))
    try:
        return project_path, load_mapping(project_path)
    except Exception as exc:
        findings.append(
            finding(
                code="project_structure.project_yaml.invalid",
                severity="critical",
                title="project.yaml could not be loaded",
                detail=f"{type(exc).__name__}: {exc}",
                recommendation="Fix project.yaml syntax before using this project.",
                path=project_path,
            )
        )
        return project_path, None


def _validate_project_payload(
    project: Mapping[str, Any],
    project_path: Path,
    root: Path,
    findings: list[Finding],
    files: list[ProjectStructureFile],
) -> None:
    _reject_project_semantics(project, project_path, findings)
    _validate_schedule(project, project_path, findings)
    _validate_environment_references(project, root, findings, files)
    _validate_connection_references(project, root, findings, files)
    _validate_execution_order(project, root, findings)


def _reject_project_semantics(project: Mapping[str, Any], path: Path, findings: list[Finding]) -> None:
    for key in sorted(_FORBIDDEN_PROJECT_FIELDS & set(project)):
        findings.append(
            finding(
                code="project_structure.project_yaml.semantic_field",
                severity="high",
                title="project.yaml contains ingestion semantics",
                detail=f"project.yaml contains {key!r}, which belongs in ingestion/access/annotations/operations contracts.",
                recommendation="Move dataset semantics out of project.yaml and keep project.yaml for environments, deployment, schedule and execution order.",
                path=f"{path}:{key}",
            )
        )


def _validate_schedule(project: Mapping[str, Any], path: Path, findings: list[Finding]) -> None:
    try:
        from contractforge_core.project import parse_standard_cron, project_schedule_intent

        schedule = project_schedule_intent(project)
        if schedule is not None:
            parse_standard_cron(schedule.cron)
    except Exception as exc:
        findings.append(
            finding(
                code="project_structure.schedule.invalid",
                severity="high",
                title="Project schedule is invalid",
                detail=f"{type(exc).__name__}: {exc}",
                recommendation="Use core schedule.cron as a standard five-field cron and schedule.timezone as an IANA timezone name.",
                path=f"{path}:schedule",
            )
        )


def _validate_environment_references(
    project: Mapping[str, Any],
    root: Path,
    findings: list[Finding],
    files: list[ProjectStructureFile],
) -> None:
    for adapter, ref in _mapping(project.get("environments")).items():
        path = _project_relative(root, ref)
        files.append(ProjectStructureFile(kind="environment", path=path, adapter=str(adapter)))
        if not path.exists():
            findings.append(
                finding(
                    code="project_structure.environment.missing",
                    severity="high",
                    title="Referenced environment file is missing",
                    detail=f"Environment {adapter!r} points to {ref!r}, but that file does not exist.",
                    recommendation="Create the environment YAML or update project.environments.",
                    path=path,
                )
            )
            continue
        try:
            from contractforge_core.contracts.environment import validate_environment_contract

            validate_environment_contract(load_mapping(path))
        except Exception as exc:
            findings.append(
                finding(
                    code="project_structure.environment.invalid",
                    severity="critical",
                    title="Environment contract is invalid",
                    detail=f"{type(exc).__name__}: {exc}",
                    recommendation="Fix the environment contract. It must contain execution context, not ingestion semantics.",
                    path=path,
                )
            )


def _validate_connection_references(
    project: Mapping[str, Any],
    root: Path,
    findings: list[Finding],
    files: list[ProjectStructureFile],
) -> None:
    for name, ref in _mapping(project.get("connections")).items():
        path = _project_relative(root, ref)
        files.append(ProjectStructureFile(kind="connection", path=path, name=str(name)))
        if not path.exists():
            findings.append(
                finding(
                    code="project_structure.connection.missing",
                    severity="high",
                    title="Referenced connection file is missing",
                    detail=f"Connection {name!r} points to {ref!r}, but that file does not exist.",
                    recommendation="Create the connection YAML or update project.connections.",
                    path=path,
                )
            )
            continue
        _validate_connection_file(path, findings)


def _validate_connection_file(path: Path, findings: list[Finding]) -> None:
    try:
        payload = load_mapping(path)
    except Exception as exc:
        findings.append(
            finding(
                code="project_structure.connection.invalid_yaml",
                severity="critical",
                title="Connection file could not be loaded",
                detail=f"{type(exc).__name__}: {exc}",
                recommendation="Fix the connection YAML before referencing it from ingestion contracts.",
                path=path,
            )
        )
        return
    source = _mapping(payload.get("source")) or payload
    if source.get("type") == "connection":
        findings.append(
            finding(
                code="project_structure.connection.recursive",
                severity="critical",
                title="Connection file points to another connection",
                detail="Reusable connection YAMLs must declare a concrete source type.",
                recommendation="Declare the concrete connector/source in the connection YAML.",
                path=path,
            )
        )
    for key in sorted({"target", "mode", "merge_keys", "quality_rules", "operations", "access"} & set(payload)):
        findings.append(
            finding(
                code="project_structure.connection.semantic_field",
                severity="high",
                title="Connection file contains dataset semantics",
                detail=f"Connection file contains {key!r}, which belongs in ingestion or section contracts.",
                recommendation="Keep connection YAMLs limited to reusable source endpoint, auth and read defaults.",
                path=f"{path}:{key}",
            )
        )
    _check_inline_secrets(payload, path, findings)


def _validate_execution_order(project: Mapping[str, Any], root: Path, findings: list[Finding]) -> None:
    steps = project.get("execution_order")
    if steps is None:
        return
    if not isinstance(steps, list):
        findings.append(
            finding(
                code="project_structure.execution_order.invalid",
                severity="high",
                title="execution_order must be a list",
                detail="project.execution_order should list named contract steps.",
                recommendation="Declare execution_order as a list of step mappings.",
                path=root / "project.yaml",
            )
        )
        return
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            findings.append(
                finding(
                    code="project_structure.execution_order.step_invalid",
                    severity="high",
                    title="Execution step is not a mapping",
                    detail=f"execution_order[{index}] is not an object.",
                    recommendation="Use step objects with name, depends_on and contracts.",
                    path=f"execution_order[{index}]",
                )
            )
            continue
        _validate_step_contract_refs(step, index, root, findings)


def _validate_step_contract_refs(step: Mapping[str, Any], index: int, root: Path, findings: list[Finding]) -> None:
    if not step.get("name"):
        findings.append(
            finding(
                code="project_structure.execution_order.name_missing",
                severity="medium",
                title="Execution step has no name",
                detail=f"execution_order[{index}] does not declare name.",
                recommendation="Set a stable step name for dependency mapping.",
                path=f"execution_order[{index}].name",
            )
        )
    contracts = _mapping(step.get("contracts"))
    if not contracts:
        findings.append(
            finding(
                code="project_structure.execution_order.contracts_missing",
                severity="high",
                title="Execution step has no contracts",
                detail=f"execution_order[{index}] does not map adapters to ingestion contracts.",
                recommendation="Declare contracts.<adapter> for each supported adapter.",
                path=f"execution_order[{index}].contracts",
            )
        )
        return
    for adapter, ref in contracts.items():
        contract_path = _project_relative(root, ref)
        if not contract_path.exists():
            findings.append(
                finding(
                    code="project_structure.execution_order.contract_missing",
                    severity="high",
                    title="Execution step references a missing contract",
                    detail=f"Step {step.get('name') or index!r} for adapter {adapter!r} points to {ref!r}, but it does not exist.",
                    recommendation="Create the ingestion contract or update execution_order.",
                    path=contract_path,
                )
            )


def _validate_ingestion_bundles(
    root: Path,
    findings: list[Finding],
    files: list[ProjectStructureFile],
    evidence_items: list[EvidenceItem],
    *,
    adapters: tuple[str, ...],
    environments: Mapping[str, dict[str, Any]],
) -> None:
    ingestion_files = iter_ingestion_files(root)
    if not ingestion_files:
        findings.append(
            finding(
                code="project_structure.ingestion.missing",
                severity="high",
                title="No ingestion contracts found",
                detail="The project folder does not contain any *.ingestion.yaml, *.ingestion.yml or *.ingestion.json files.",
                recommendation="Add at least one split ingestion contract.",
                path=root,
            )
        )
        return
    for path in ingestion_files:
        inferred_adapter = _adapter_from_path(root, path)
        files.append(ProjectStructureFile(kind="ingestion_bundle", path=path, adapter=inferred_adapter))
        _validate_legacy_ingestion_fields(path, findings)
        try:
            from contractforge_core.contracts import load_contract_bundle

            bundle = load_contract_bundle(path)
        except Exception as exc:
            findings.append(
                finding(
                    code="project_structure.ingestion_bundle.invalid",
                    severity="critical",
                    title="Ingestion bundle is invalid",
                    detail=f"{type(exc).__name__}: {exc}",
                    recommendation="Fix the ingestion contract and sibling section files. The core bundle loader must accept the bundle.",
                    path=path,
                )
            )
            continue
        _validate_adapter_planning(
            path,
            bundle.contract,
            findings,
            evidence_items,
            requested=adapters,
            inferred_adapter=inferred_adapter,
            environments=environments,
            bundle_environment=bundle.environment,
        )


def _validate_adapter_planning(
    path: Path,
    contract: dict[str, Any],
    findings: list[Finding],
    evidence_items: list[EvidenceItem],
    *,
    requested: tuple[str, ...],
    inferred_adapter: str | None,
    environments: Mapping[str, dict[str, Any]],
    bundle_environment: dict[str, Any] | None,
) -> None:
    for adapter in _adapters_for_path(inferred_adapter, requested=requested):
        outcome = validate_contract_with_adapter(
            contract,
            adapter=adapter,
            environment=environments.get(adapter) or bundle_environment,
        )
        evidence_items.extend(
            replace(item, path=str(path)) if item.path is None else item
            for item in outcome.evidence
        )
        findings.extend(_finding_with_path(item, path) for item in outcome.findings)


def _validate_legacy_ingestion_fields(path: Path, findings: list[Finding]) -> None:
    try:
        payload = load_mapping(path)
    except Exception:
        return
    for key, recommendation in sorted(_LEGACY_INGESTION_FIELDS.items()):
        if key in payload:
            findings.append(
                finding(
                    code="project_structure.ingestion.legacy_field",
                    severity="high",
                    title="Ingestion contract uses a legacy flat field",
                    detail=f"{path.name} declares top-level {key!r}.",
                    recommendation=recommendation,
                    path=f"{path}:{key}",
                )
            )
    _validate_connection_source_reference(path, payload, findings)


def _validate_connection_source_reference(path: Path, payload: Mapping[str, Any], findings: list[Finding]) -> None:
    source = _mapping(payload.get("source"))
    if source.get("type") != "connection":
        return
    if not source.get("connection_path"):
        findings.append(
            finding(
                code="project_structure.ingestion.connection_path_missing",
                severity="critical",
                title="Connection source is missing connection_path",
                detail="source.type: connection requires source.connection_path.",
                recommendation="Set source.connection_path, preferably project://connections/<name>.yaml.",
                path=f"{path}:source.connection_path",
            )
        )


def _check_inline_secrets(value: Any, path: Path, findings: list[Finding], *, prefix: str = "") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if _looks_secret_key(str(key)) and isinstance(item, str) and item.strip() and not _SECRET_TEMPLATE.search(item):
                findings.append(
                    finding(
                        code="project_structure.connection.inline_secret",
                        severity="critical",
                        title="Connection file contains an inline secret",
                        detail=f"{child} contains a secret-like value instead of a secret reference.",
                        recommendation="Use {{ secret:scope/key }} or an adapter-supported secret reference.",
                        path=f"{path}:{child}",
                    )
                )
            _check_inline_secrets(item, path, findings, prefix=child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_inline_secrets(item, path, findings, prefix=f"{prefix}[{index}]")


def _report(
    root: Path,
    files: list[ProjectStructureFile],
    findings: list[Finding],
    evidence_items: list[EvidenceItem],
) -> ProjectStructureReport:
    status = _status(findings)
    return ProjectStructureReport(
        root=root,
        status=status,
        summary=_summary(status, files, findings),
        files=files,
        findings=findings,
        evidence=evidence_items,
    )


def _status(findings: list[Finding]) -> ProjectStructureStatus:
    severities = {item.severity for item in findings}
    if "critical" in severities:
        return "UNSAFE" if any(item.code.endswith("inline_secret") for item in findings) else "INVALID"
    if "high" in severities:
        return "INVALID"
    if findings:
        return "READY_WITH_WARNINGS"
    return "READY"


def _summary(status: ProjectStructureStatus, files: list[ProjectStructureFile], findings: list[Finding]) -> str:
    if not findings:
        return f"{status}: {len(files)} project file(s) validated successfully."
    counts = {
        severity: sum(1 for item in findings if item.severity == severity)
        for severity in ("critical", "high", "medium", "low", "info")
    }
    return (
        f"{status}: {len(files)} project file(s), {len(findings)} finding(s), "
        f"{counts['critical']} critical, {counts['high']} high, {counts['medium']} medium."
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _project_relative(root: Path, ref: Any) -> Path:
    text = str(ref)
    if text.startswith("project://"):
        text = text.removeprefix("project://").strip("/\\")
    return root / text


def _adapter_from_path(root: Path, path: Path) -> str | None:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return None
    if "contracts" in parts:
        index = parts.index("contracts")
        if len(parts) > index + 1:
            candidate = parts[index + 1].strip().lower()
            return candidate if candidate in known_adapter_names() else None
    return None


def _requested_adapters(adapters: tuple[str, ...]) -> tuple[str, ...]:
    normalized = []
    for adapter in adapters:
        value = adapter.strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _adapters_for_path(inferred_adapter: str | None, *, requested: tuple[str, ...]) -> tuple[str, ...]:
    if not requested:
        return ()
    normalized_inferred = (inferred_adapter or "").strip().lower()
    if normalized_inferred and normalized_inferred in requested:
        return (normalized_inferred,)
    if normalized_inferred and normalized_inferred not in requested:
        return ()
    return requested


def _environment_payloads(project: Mapping[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for adapter, ref in _mapping(project.get("environments")).items():
        try:
            payloads[str(adapter).strip().lower()] = load_mapping(_project_relative(root, ref))
        except Exception:
            continue
    return payloads


def _finding_with_path(item: Finding, path: Path) -> Finding:
    return replace(item, path=item.path or str(path))


def _looks_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SECRET_KEYS or normalized.endswith(("_password", "_token", "_secret", "_api_key"))
