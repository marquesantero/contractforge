"""Shared AWS CLI helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from contractforge_core.contracts import load_contract_bundle


def load_mapping(path: Path, *, label: str) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{label} file must contain a YAML or JSON object")
    return loaded


def load_contract_input(path: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if path.is_dir() or looks_like_split_contract(path):
        bundle = load_contract_bundle(bundle_base(path))
        environment = bundle.environment if isinstance(bundle.environment, dict) else None
        return bundle.contract, environment
    return load_mapping(path, label="contract"), None


def load_environment_input(path: Path | None, fallback: dict[str, Any] | None) -> dict[str, Any] | None:
    return load_mapping(path, label="environment") if path is not None else fallback


def contract_bundle_artifacts(path: Path, *, environment: dict[str, Any] | None) -> dict[str, str]:
    artifacts = environment_artifact_options(environment)
    if not artifacts.get("include_contract_bundle"):
        return {}
    if not (path.is_dir() or looks_like_split_contract(path)):
        return {}
    bundle = load_contract_bundle(bundle_base(path))
    paths = (bundle.metadata or {}).get("paths")
    if not isinstance(paths, dict):
        return {}
    bundle_name = bundle_base(path).name
    result: dict[str, str] = {}
    for section, raw_path in sorted(paths.items()):
        source = Path(str(raw_path))
        if source.exists():
            result[f"original/{bundle_name}/{section}{source.suffix}"] = source.read_text(encoding="utf-8")
    return result


def environment_artifact_options(environment: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(environment, dict):
        return {}
    value = environment.get("artifacts")
    return dict(value) if isinstance(value, dict) else {}


def load_payload(path: Path) -> dict[str, Any] | str:
    text = path.read_text(encoding="utf-8")
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        loaded = yaml.safe_load(text)
    if isinstance(loaded, dict):
        return loaded
    if str(text or "").strip():
        return text
    raise ValueError("payload file must contain a JSON or YAML object")


def public_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    if isinstance(value, dict):
        return value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def print_payload(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def parse_key_values(values: list[str], *, flag: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"{flag} must use key=value format")
        key, value = item.split("=", 1)
        if not key.strip():
            raise ValueError(f"{flag} key must not be empty")
        parsed[key.strip()] = value
    return parsed


def looks_like_split_contract(path: Path) -> bool:
    return any(marker in path.name for marker in (".ingestion.", ".annotations.", ".operations.", ".access.", ".environment."))


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
