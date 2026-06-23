"""Databricks governance review commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractforge_core.cli_io import yaml_load
from contractforge_core.contracts import load_contract_bundle, semantic_contract_from_mapping
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.annotations import render_annotations_sql
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.governance import render_access_sql, render_governance_sql
from contractforge_databricks.operations import render_operations_insert_sql, render_operations_json


def add_governance_parser(subparsers: Any) -> None:
    preview = subparsers.add_parser("governance-preview", help="Render Databricks governance review artifacts")
    preview.add_argument("paths", nargs="+", type=Path)
    preview.add_argument("--output-dir", type=Path)
    preview.add_argument("--indent", type=int, default=2)

    apply_plan = subparsers.add_parser("governance-apply-plan", help="Render Databricks SQL that a runtime executor can apply")
    apply_plan.add_argument("paths", nargs="+", type=Path)
    apply_plan.add_argument("--output-dir", type=Path)
    apply_plan.add_argument("--indent", type=int, default=2)


def governance_command(args: Any) -> int | None:
    if args.command == "governance-preview":
        return _governance_preview(args)
    if args.command == "governance-apply-plan":
        return _governance_apply_plan(args)
    return None


def _governance_preview(args: Any) -> int:
    artifacts = {}
    for path in args.paths:
        contract, environment = _load_contract(path)
        prefix = _artifact_prefix(path)
        env = DatabricksEnvironment.from_contract(environment)
        artifacts[f"{prefix}.governance.sql"] = render_governance_sql(contract)
        artifacts[f"{prefix}.annotations.sql"] = render_annotations_sql(contract)
        artifacts[f"{prefix}.access.sql"] = render_access_sql(contract)
        artifacts[f"{prefix}.operations.json"] = render_operations_json(contract)
        artifacts[f"{prefix}.operations_evidence.sql"] = render_operations_insert_sql(
            contract,
            catalog=env.evidence_catalog,
            schema=env.evidence_schema,
        )
    return _emit(artifacts, args.output_dir, args.indent)


def _governance_apply_plan(args: Any) -> int:
    artifacts = {}
    for path in args.paths:
        contract, environment = _load_contract(path)
        prefix = _artifact_prefix(path)
        env = DatabricksEnvironment.from_contract(environment)
        sections = [
            "-- ContractForge Databricks governance apply plan",
            "-- Execute with a Databricks SQL/Spark runner owned by the adapter runtime.",
            "",
            render_governance_sql(contract),
            render_operations_insert_sql(contract, catalog=env.evidence_catalog, schema=env.evidence_schema) + ";",
        ]
        artifacts[f"{prefix}.governance_apply_plan.sql"] = "\n".join(sections)
    return _emit(artifacts, args.output_dir, args.indent)


def _load_contract(path: Path) -> tuple[SemanticContract, dict[str, Any] | None]:
    if path.is_dir() or _is_split_ingestion(path) or _has_project_context(path):
        bundle = load_contract_bundle(_bundle_base(path))
        return bundle.semantic, bundle.environment
    payload = _load_mapping(path)
    environment = payload.get("environment") if isinstance(payload.get("environment"), dict) else None
    return semantic_contract_from_mapping(payload), environment


def _emit(artifacts: dict[str, str], output_dir: Path | None, indent: int) -> int:
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for name, body in artifacts.items():
            path = output_dir / name
            path.write_text(body, encoding="utf-8")
            written.append(str(path))
        return _print({"status": "SUCCESS", "written": written}, indent)
    return _print(artifacts, indent)


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text) if path.suffix.lower() == ".json" else yaml_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _artifact_prefix(path: Path) -> str:
    name = _bundle_base(path).name
    return name.replace(".", "_")


def _bundle_base(path: Path) -> Path:
    if _is_split_ingestion(path):
        name = path.name
        for suffix in (".ingestion.yaml", ".ingestion.yml", ".ingestion.json"):
            if name.endswith(suffix):
                return path.with_name(name[: -len(suffix)])
    return path


def _is_split_ingestion(path: Path) -> bool:
    return path.is_file() and ".ingestion." in path.name


def _has_project_context(path: Path) -> bool:
    base = path if path.is_dir() else path.parent
    return any((candidate / "project.yaml").exists() or (candidate / "project.yml").exists() for candidate in (base, *base.parents))


def _print(payload: object, indent: int) -> int:
    print(json.dumps(payload, indent=indent, sort_keys=True, default=str))
    return 0
