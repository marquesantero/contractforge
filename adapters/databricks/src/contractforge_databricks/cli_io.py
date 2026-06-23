"""Databricks CLI file IO helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractforge_core.contracts import load_contract_bundle


def load_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        payload = yaml_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def load_contract_input(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if path.is_dir() or looks_like_split_contract(path) or has_project_context(path):
        bundle = load_contract_bundle(bundle_base(path))
        environment = bundle.environment if isinstance(bundle.environment, dict) else None
        return bundle.contract, environment
    return load_mapping(path), None


def write_mapping(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; use --force to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_dump(payload), encoding="utf-8")


def write_artifacts(output_dir: Path, artifacts: dict[str, str]) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, body in artifacts.items():
        path = output_dir / name
        path.write_text(body, encoding="utf-8")
        written.append(str(path))
    return written


def yaml_load(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("YAML support requires PyYAML; use JSON files or install PyYAML") from exc
    return yaml.safe_load(text)


def yaml_dump(payload: dict[str, Any]) -> str:
    try:
        import yaml  # type: ignore
    except Exception:  # pragma: no cover
        return json.dumps(payload, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def looks_like_split_contract(path: Path) -> bool:
    return any(marker in path.name for marker in (".ingestion.", ".annotations.", ".operations.", ".access.", ".environment."))


def has_project_context(path: Path) -> bool:
    base = path if path.is_dir() else path.parent
    return any((candidate / "project.yaml").exists() or (candidate / "project.yml").exists() for candidate in (base, *base.parents))


def bundle_base(path: Path) -> Path:
    name = path.name
    for suffix in (
        ".ingestion.yaml",
        ".ingestion.yml",
        ".ingestion.json",
        ".annotations.yaml",
        ".annotations.yml",
        ".annotations.json",
        ".operations.yaml",
        ".operations.yml",
        ".operations.json",
        ".access.yaml",
        ".access.yml",
        ".access.json",
        ".environment.yaml",
        ".environment.yml",
        ".environment.json",
    ):
        if name.endswith(suffix):
            return path.with_name(name[: -len(suffix)])
    return path
