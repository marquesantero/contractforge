"""Contract-oriented core CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractforge_core.cli_init import init_contract
from contractforge_core.cli_io import yaml_load
from contractforge_core.contracts import (
    contract_model_schemas,
    load_contract_bundle,
    semantic_contract_from_mapping,
    validate_source_semantics,
)
from contractforge_core.config import public_write_mode

CONTRACT_SUFFIXES = {".json", ".yaml", ".yml"}
SPLIT_MARKERS = (".annotations.", ".operations.", ".access.", ".environment.")


def handle_contract_command(args: Any) -> int | None:
    if args.command == "validate":
        return validate_contracts(args.paths, indent=args.indent)
    if args.command == "validate-bundle":
        return validate_bundles(args.paths, indent=args.indent)
    if args.command == "validate-project":
        return validate_project(args.paths, indent=args.indent)
    if args.command == "schema":
        return _print(contract_model_schemas(), args.indent)
    if args.command == "init":
        return init_contract(args)
    return None


def validate_contracts(paths: list[Path], *, indent: int) -> int:
    items = []
    for path in paths:
        try:
            contract = _load_mapping(path)
            semantic = semantic_contract_from_mapping(contract)
            _validate_source_if_mapping(contract.get("source"))
            items.append({"path": str(path), "kind": "contract", "status": "SUCCESS", "target": semantic.target.name, "mode": public_write_mode(semantic.write.mode)})
        except Exception as exc:
            items.append({"path": str(path), "kind": "contract", "status": "FAILED", "error": str(exc)})
    return _report(items, indent)


def validate_bundles(paths: list[Path], *, indent: int) -> int:
    items = []
    for path in paths:
        try:
            bundle = _load_bundle(path)
            _validate_source_if_mapping(bundle.contract.get("source"))
            items.append(
                {
                    "path": str(path),
                    "kind": "bundle",
                    "status": "SUCCESS",
                    "target": bundle.semantic.target.name,
                    "mode": public_write_mode(bundle.semantic.write.mode),
                    "split_files": dict(bundle.metadata.get("paths", {})),
                }
            )
        except Exception as exc:
            items.append({"path": str(path), "kind": "bundle", "status": "FAILED", "error": str(exc)})
    return _report(items, indent)


def validate_project(paths: list[Path], *, indent: int) -> int:
    items = []
    for root in paths:
        discovered = _discover_contracts(root)
        if not discovered:
            items.append({"path": str(root), "kind": "project", "status": "FAILED", "error": "no contracts found"})
            continue
        for kind, path in discovered:
            items.extend(_validate_bundle_for_project(path) if kind == "bundle" else _validate_single_for_project(path))
    return _report(items, indent)


def _validate_bundle_for_project(path: Path) -> list[dict[str, Any]]:
    try:
        bundle = _load_bundle(path)
        _validate_source_if_mapping(bundle.contract.get("source"))
        return [{"path": str(path), "kind": "bundle", "status": "SUCCESS", "target": bundle.semantic.target.name, "mode": public_write_mode(bundle.semantic.write.mode)}]
    except Exception as exc:
        return [{"path": str(path), "kind": "bundle", "status": "FAILED", "error": str(exc)}]


def _validate_single_for_project(path: Path) -> list[dict[str, Any]]:
    try:
        contract = _load_mapping(path)
        semantic = semantic_contract_from_mapping(contract)
        _validate_source_if_mapping(contract.get("source"))
        return [{"path": str(path), "kind": "contract", "status": "SUCCESS", "target": semantic.target.name}]
    except Exception as exc:
        return [{"path": str(path), "kind": "contract", "status": "FAILED", "error": str(exc)}]


def _load_bundle(path: Path):
    return load_contract_bundle(_bundle_base(path))


def _discover_contracts(root: Path) -> list[tuple[str, Path]]:
    if root.is_file():
        if _is_split_ingestion(root):
            return [("bundle", root)]
        return [("contract", root)] if _is_standalone_contract(root) else []
    found = []
    for path in sorted(root.rglob("*")):
        if _is_discovery_ignored(path):
            continue
        if _is_split_ingestion(path):
            found.append(("bundle", path))
        elif _is_standalone_contract(path):
            found.append(("contract", path))
    return found


def _report(items: list[dict[str, Any]], indent: int) -> int:
    failed = [item for item in items if item["status"] == "FAILED"]
    payload = {"status": "FAILED" if failed else "SUCCESS", "total": len(items), "succeeded": len(items) - len(failed), "failed": len(failed), "items": items}
    _print(payload, indent)
    return 1 if failed else 0


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text) if path.suffix.lower() == ".json" else yaml_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _validate_source_if_mapping(source: object) -> None:
    if isinstance(source, dict):
        validate_source_semantics(source)


def _print(payload: object, indent: int) -> int:
    print(json.dumps(payload, indent=indent, sort_keys=True, default=str))
    return 0


def _base_output(path: Path) -> Path:
    name = path.name
    for suffix in (".ingestion.yaml", ".ingestion.yml", ".ingestion.json"):
        if name.endswith(suffix):
            return path.with_name(name[: -len(suffix)])
    return path


def _bundle_base(path: Path) -> Path:
    return _base_output(path) if _is_split_ingestion(path) else path


def _is_contract_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in CONTRACT_SUFFIXES


def _is_split_ingestion(path: Path) -> bool:
    return _is_contract_file(path) and ".ingestion." in path.name


def _is_standalone_contract(path: Path) -> bool:
    if not _is_contract_file(path) or ".ingestion." in path.name or any(marker in path.name for marker in SPLIT_MARKERS):
        return False
    try:
        payload = _load_mapping(path)
    except Exception:
        return False
    return isinstance(payload.get("source"), dict) and isinstance(payload.get("target"), dict)


def _is_discovery_ignored(path: Path) -> bool:
    ignored_dirs = {".databricks", ".git", ".venv", "__pycache__", "node_modules", "build", "dist"}
    return any(part in ignored_dirs for part in path.parts)
