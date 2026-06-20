"""Starter contract generation for the core ContractForge CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractforge_core.cli_io import yaml_dump
from contractforge_core.config import canonical_write_mode


def init_contract(args: Any) -> int:
    output = _base_output(args.output)
    files = {
        output.with_suffix(".ingestion.yaml"): _init_ingestion(args),
        output.with_suffix(".annotations.yaml"): _init_annotations(args),
        output.with_suffix(".operations.yaml"): _init_operations(args),
        output.with_suffix(".access.yaml"): _init_access(args),
        output.with_suffix(".environment.yaml"): _init_environment(args),
    }
    written = []
    for path, payload in files.items():
        _write_mapping(path, payload, force=args.force)
        written.append(str(path))
    return _print({"status": "SUCCESS", "written": written}, args.indent)


def _init_ingestion(args: Any) -> dict[str, Any]:
    merge_keys = _csv(args.merge_keys)
    hash_keys = _csv(args.hash_keys) or merge_keys
    canonical_mode = canonical_write_mode(args.mode)
    if canonical_mode in {"scd1_upsert", "scd2_historical", "snapshot_soft_delete"} and not merge_keys:
        raise ValueError(f"--merge-keys is required for mode={args.mode}")
    if canonical_mode == "scd1_hash_diff" and not hash_keys:
        raise ValueError("--hash-keys or --merge-keys is required for mode=hash_diff_upsert")
    contract: dict[str, Any] = {
        "source": {"type": "table", "table": args.source},
        "target": {"catalog": args.catalog, "schema": args.target_schema or args.layer, "table": args.target_table},
        "layer": args.layer,
        "mode": args.mode,
        "schema_policy": args.schema_policy,
    }
    if merge_keys:
        contract["merge_keys"] = merge_keys
        contract["quality_rules"] = {"not_null": merge_keys}
    if canonical_mode == "scd1_hash_diff" and hash_keys:
        contract["hash_keys"] = hash_keys
    watermarks = _csv(args.watermark_columns)
    if watermarks:
        contract["watermark_columns"] = watermarks
    return contract


def _init_annotations(args: Any) -> dict[str, Any]:
    return {
        "target": _target(args),
        "table": {"description": args.description or f"TODO: describe {args.target_table}", "tags": {"domain": args.domain or "TODO"}},
        "columns": {},
    }


def _init_operations(args: Any) -> dict[str, Any]:
    return {
        "target": _target(args),
        "ownership": {
            "business_owner": args.owner or "TODO",
            "technical_owner": args.technical_owner or "data-platform",
            "support_group": args.support_group or "data-platform",
        },
        "operations": {
            "criticality": args.criticality,
            "expected_frequency": args.expected_frequency,
            "freshness_sla_minutes": args.freshness_sla_minutes,
            "alert_on_failure": True,
            "alert_on_quality_fail": True,
            "runbook_url": args.runbook_url or "TODO",
        },
    }


def _init_access(args: Any) -> dict[str, Any]:
    return {
        "target": _target(args),
        "access_policy": {"mode": "validate_only", "on_drift": "warn", "revoke_unmanaged": False},
        "grants": [{"principal": args.access_principal or "data-engineers", "privileges": ["SELECT"]}],
    }


def _init_environment(args: Any) -> dict[str, Any]:
    return {"name": "dev", "adapter": args.adapter, "evidence": {"catalog": args.catalog, "schema": "ops"}}


def _target(args: Any) -> dict[str, str]:
    return {"catalog": args.catalog, "schema": args.target_schema or args.layer, "table": args.target_table}


def _write_mapping(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; use --force to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_dump(payload), encoding="utf-8")


def _print(payload: object, indent: int) -> int:
    print(json.dumps(payload, indent=indent, sort_keys=True, default=str))
    return 0


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _base_output(path: Path) -> Path:
    name = path.name
    for suffix in (".ingestion.yaml", ".ingestion.yml", ".ingestion.json"):
        if name.endswith(suffix):
            return path.with_name(name[: -len(suffix)])
    return path
