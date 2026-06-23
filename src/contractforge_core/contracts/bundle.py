"""Composition helpers for responsibility-separated ContractForge contracts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any

from contractforge_core.contracts.defaults import resolve_contract_defaults
from contractforge_core.contracts.environment import validate_environment_contract
from contractforge_core.contracts.normalize import semantic_contract_from_mapping
from contractforge_core.semantic.models import SemanticContract


@dataclass(frozen=True)
class ContractBundle:
    semantic: SemanticContract
    contract: dict[str, Any]
    environment: dict[str, Any] | None = None
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)


def compose_contract_sections(
    *,
    ingestion: dict[str, Any],
    annotations: dict[str, Any] | None = None,
    operations: dict[str, Any] | None = None,
    access: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
    metadata: dict[str, dict[str, Any]] | None = None,
) -> ContractBundle:
    """Compose split contracts into one semantic bundle.

    The environment contract is validated and retained separately. It is not
    merged into ingestion semantics.
    """
    if not isinstance(ingestion, dict):
        raise ValueError("ingestion contract must be an object")
    contract = dict(ingestion)
    _attach_section(contract, "annotations", annotations)
    _attach_section(contract, "operations", operations)
    _attach_section(contract, "access", access)
    env = validate_environment_contract(environment) if environment is not None else None
    return ContractBundle(
        semantic=semantic_contract_from_mapping(contract),
        contract=contract,
        environment=env,
        metadata=dict(metadata or {}),
    )


def load_contract_bundle(path: str | Path) -> ContractBundle:
    """Load a split ContractForge bundle from an ingestion file or base path."""
    base = Path(path)
    ingestion_path = _ingestion_path(base)
    ingestion, ingestion_meta = _strip_metadata(_load_mapping(ingestion_path))
    ingestion = _resolve_connection_source(ingestion, base_dir=ingestion_path.parent)
    sections: dict[str, dict[str, Any] | None] = {}
    metadata: dict[str, dict[str, Any]] = {"ingestion": ingestion_meta}
    paths = {"ingestion": str(ingestion_path)}
    for name in ("annotations", "operations", "access", "environment"):
        section_path = _first_existing(ingestion_path, name)
        if section_path is None:
            sections[name] = None
            continue
        payload, section_meta = _strip_metadata(_load_mapping(section_path))
        sections[name] = payload
        metadata[name] = section_meta
        paths[name] = str(section_path)
    metadata["paths"] = paths
    warnings = contract_metadata_warnings(metadata)
    if warnings:
        metadata["warnings"] = {"items": warnings}
    bundle = compose_contract_sections(
        ingestion=ingestion,
        annotations=sections["annotations"],
        operations=sections["operations"],
        access=sections["access"],
        environment=sections["environment"],
        metadata=metadata,
    )
    project = _project_mapping(ingestion_path.parent)
    resolved = resolve_contract_defaults(bundle.contract, project=project)
    if resolved.decisions:
        metadata["defaults"] = {"decisions": resolved.decisions_json()}
    return ContractBundle(
        semantic=semantic_contract_from_mapping(resolved.contract),
        contract=resolved.contract,
        environment=bundle.environment,
        metadata=metadata,
    )


def _resolve_connection_source(ingestion: dict[str, Any], *, base_dir: Path) -> dict[str, Any]:
    source = ingestion.get("source")
    if not isinstance(source, dict) or source.get("type") != "connection":
        return ingestion
    connection_ref = source.get("connection_path")
    if not isinstance(connection_ref, str) or not connection_ref.strip():
        raise ValueError("source.type='connection' requires source.connection_path")
    connection_path = _safe_connection_path(connection_ref.strip(), base_dir=base_dir)
    connection_payload = _connection_source_payload(_load_mapping(connection_path), connection_path)
    overrides = {key: value for key, value in source.items() if key not in {"type", "connection_path"}}
    resolved = _deep_merge(connection_payload, overrides)
    if "type" not in resolved and resolved.get("connector"):
        resolved["type"] = "connector"
    if resolved.get("type") == "connection":
        raise ValueError(f"{connection_path} must declare a concrete source type, not type='connection'")
    if "connection" not in resolved:
        resolved["connection"] = str(connection_ref.strip())
    updated = dict(ingestion)
    updated["source"] = resolved
    return updated


def _safe_connection_path(connection_ref: str, *, base_dir: Path) -> Path:
    """Resolve a connection_path reference, refusing traversal out of base_dir.

    A connection_path is read at bundle-load time, so an absolute path or a
    ``..`` component would let a contract reach arbitrary files reachable
    by the loader process (AWS credentials, other tenants' bundles, etc.).
    The reference must therefore be relative, free of parent traversal,
    and resolve inside the directory holding the ingestion file.
    """

    if connection_ref.startswith("project://"):
        project_ref = connection_ref.removeprefix("project://").strip("/\\")
        project_root = _find_project_root(base_dir)
        if project_root is None:
            raise ValueError(
                f"source.connection_path uses project:// but no project.yaml was found above {base_dir}"
            )
        return _safe_relative_path(project_ref, root_dir=project_root, original_ref=connection_ref)
    candidate = Path(connection_ref)
    return _safe_relative_path(connection_ref, root_dir=base_dir, original_ref=connection_ref, candidate=candidate)


def _safe_relative_path(
    connection_ref: str,
    *,
    root_dir: Path,
    original_ref: str,
    candidate: Path | None = None,
) -> Path:
    candidate = candidate or Path(connection_ref)
    if candidate.is_absolute() or candidate.drive or PureWindowsPath(connection_ref).drive or connection_ref.startswith(("/", "\\")):
        raise ValueError(
            f"source.connection_path must be a relative path inside the bundle directory or project root; got {original_ref!r}"
        )
    if any(part == ".." for part in candidate.parts):
        raise ValueError(
            f"source.connection_path must not contain '..' components; got {original_ref!r}"
        )
    resolved_base = root_dir.resolve()
    resolved = (resolved_base / candidate).resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(
            f"source.connection_path resolves outside the bundle directory or project root; got {original_ref!r}"
        ) from exc
    return resolved


def _find_project_root(base_dir: Path) -> Path | None:
    for candidate in (base_dir, *base_dir.parents):
        if (candidate / "project.yaml").exists() or (candidate / "project.yml").exists():
            return candidate
    return None


def _project_mapping(base_dir: Path) -> dict[str, Any] | None:
    root = _find_project_root(base_dir)
    if root is None:
        return None
    project_path = root / "project.yaml"
    if not project_path.exists():
        project_path = root / "project.yml"
    payload = _load_mapping(project_path)
    return payload if isinstance(payload, dict) else None


def _connection_source_payload(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    if "source" in payload:
        nested = payload["source"]
        if not isinstance(nested, dict):
            raise ValueError(f"{path}.source must be an object")
        return dict(nested)
    return dict(payload)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def contract_metadata_warnings(metadata: dict[str, dict[str, Any]]) -> list[str]:
    warnings = []
    versions = {
        name: str(content["contract_version"])
        for name, content in metadata.items()
        if isinstance(content, dict) and content.get("contract_version")
    }
    for name, version in versions.items():
        if not re.match(r"^\d+\.\d+\.\d+$", version):
            warnings.append(f"{name}._metadata.contract_version is not MAJOR.MINOR.PATCH: {version}")
    valid_majors = {name: version.split(".", 1)[0] for name, version in versions.items() if re.match(r"^\d+\.\d+\.\d+$", version)}
    if len(set(valid_majors.values())) > 1:
        warnings.append(f"major version differs between bundle files: {valid_majors}")
    if len(set(versions.values())) > 1:
        warnings.append(f"contract_version differs between bundle files: {versions}")
    return warnings


def _attach_section(contract: dict[str, Any], name: str, section: dict[str, Any] | None) -> None:
    if section is None:
        return
    if not isinstance(section, dict):
        raise ValueError(f"{name} contract must be an object")
    _reject_self_wrapper(name, section)
    _validate_target_compatibility(name, contract, section)
    payload = _section_payload(name, section)
    payload.pop("target", None)
    payload.pop("_metadata", None)
    contract[name] = payload


def _reject_self_wrapper(name: str, section: dict[str, Any]) -> None:
    """Reject `<section>: { ... }` envelope at the top of split-bundle files.

    Each section file (annotations.yaml, operations.yaml, access.yaml,
    environment.yaml) declares its fields at the document root. Wrapping
    the contents inside a key named after the section is a redundancy that
    masks typos and creates asymmetry between sections, so it is refused
    with a guiding error.
    """

    if name not in section:
        return
    nested = section[name]
    if not isinstance(nested, dict):
        return
    structural = {name, "target", "_metadata"}
    if set(section) <= structural:
        raise ValueError(
            f"{name}.yaml must declare fields at the document root, not under '{name}:'. "
            f"Remove the wrapping '{name}:' key and outdent its contents."
        )


def _section_payload(name: str, section: dict[str, Any]) -> dict[str, Any]:
    payload = dict(section)
    if name == "operations":
        return _normalize_operations_payload(payload)
    return payload


def _normalize_operations_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ownership_fields = {"business_owner", "technical_owner", "steward", "support_group", "escalation_group"}
    flat_ownership = {field: payload.pop(field) for field in list(payload) if field in ownership_fields}
    if flat_ownership:
        ownership = dict(payload.get("ownership") or {})
        ownership.update(flat_ownership)
        payload["ownership"] = ownership
    return payload


def _strip_metadata(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    clean = dict(payload)
    metadata = clean.pop("_metadata", {}) or {}
    if not isinstance(metadata, dict):
        raise ValueError("_metadata must be an object")
    return clean, metadata


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("YAML support requires PyYAML; use JSON files or install PyYAML") from exc
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _ingestion_path(path: Path) -> Path:
    if path.is_file():
        return path
    existing = _first_existing(path, "ingestion")
    if existing is None:
        raise FileNotFoundError(f"ingestion contract not found for {path}")
    return existing


def _first_existing(base: Path, suffix: str) -> Path | None:
    for candidate in _candidate_paths(base, suffix):
        if candidate.exists():
            return candidate
    return None


def _candidate_paths(base: Path, suffix: str) -> tuple[Path, ...]:
    if base.is_file():
        for marker in (".ingestion.", ".annotations.", ".operations.", ".access.", ".environment."):
            if marker in base.name:
                stem = base.name.split(marker, 1)[0]
                return tuple(base.with_name(f"{stem}.{suffix}{extension}") for extension in (".yaml", ".yml", ".json"))
        return tuple()
    return (base.with_suffix(f".{suffix}.yaml"), base.with_suffix(f".{suffix}.yml"), base.with_suffix(f".{suffix}.json"))


def _validate_target_compatibility(name: str, ingestion: dict[str, Any], section: dict[str, Any]) -> None:
    declared = _target_tuple(section)
    if declared is None:
        return
    expected = _target_tuple(ingestion)
    if expected is None:
        raise ValueError(f"{name}.target requires ingestion.target for split-bundle target validation")
    for field_name, declared_value, expected_value in zip(("catalog", "schema", "table"), declared, expected):
        if declared_value and expected_value and declared_value != expected_value:
            raise ValueError(
                f"{name}.target.{field_name}={declared_value!r} diverges from ingestion target {expected_value!r}"
            )


def _target_tuple(payload: dict[str, Any]) -> tuple[str | None, str | None, str] | None:
    target = payload.get("target")
    if not isinstance(target, dict):
        return None
    table = target.get("table")
    if not table:
        raise ValueError("target.table is required when target is declared")
    return (
        str(target["catalog"]).strip() if target.get("catalog") else None,
        str(target["schema"]).strip() if target.get("schema") else None,
        str(table).strip(),
    )
