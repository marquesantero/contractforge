"""Draft ContractForge contract generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from contractforge_ai.generators.metadata import suggest_metadata
from contractforge_ai.models import Assumption, ContractDraftResult, EvidenceItem, RequiredDecision, Traceability
from contractforge_ai.validation import validate_generated_contract
from contractforge_ai.write_modes import canonical_write_mode

_FORMAT_REQUIRED_CONNECTORS = {
    "adls",
    "azure_blob",
    "blob",
    "gcs",
    "incremental_files",
    "object_storage",
    "s3",
}


def generate_contract_draft(
    schema_path: str | Path,
    *,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
) -> ContractDraftResult:
    """Generate a conservative ContractForge contract draft from schema/profile metadata."""

    schema_file = Path(schema_path)
    metadata = suggest_metadata(schema_file)
    selected_mode = mode or _default_mode(layer)
    assumptions = [
        "Generated contract is a draft and must be reviewed before execution.",
        f"Write mode defaulted to {selected_mode!r} based on layer {layer!r}." if mode is None else f"Write mode set to {mode!r}.",
        "Quality rules and annotations were generated from schema/profile metadata only.",
    ]
    decisions_required = [
        "Confirm source connector options and credentials.",
        "Confirm target catalog/schema/table naming.",
        "Confirm write mode and merge keys before using merge-based modes.",
        "Review generated annotations, PII candidates and quality rules with data owners.",
    ]
    warnings: list[str] = [
        "The generated contract does not execute dry-run validation.",
        "Generated PII and quality suggestions are evidence-based drafts, not policy decisions.",
    ]

    source: dict[str, Any] = {
        "type": "connector",
        "connector": connector,
        "path": source_path,
    }
    source_format = _default_source_format(connector, source_path)
    if source_format:
        source["format"] = source_format
    elif connector.lower() in _FORMAT_REQUIRED_CONNECTORS:
        source["format"] = "REVIEW_REQUIRED"
        decisions_required.append("Confirm source file format before adapter rendering.")

    schema = _ddl_from_metadata(metadata.annotations, metadata.quality_rules, schema_file)
    if schema:
        source["read"] = {"schema": schema}

    contract: dict[str, Any] = {
        "_metadata": {
            "generated_by": "contractforge-ai",
            "draft": True,
            "review_required": True,
        },
        "source": source,
        "target": {
            "catalog": target_catalog,
            "schema": target_schema,
            "table": target_table,
        },
        "layer": layer,
        "mode": selected_mode,
        "quality_rules": metadata.quality_rules,
        "annotations": metadata.annotations,
        "operations": {
            "technical_owner": owner or "REVIEW_REQUIRED",
            "criticality": "medium",
            "expected_frequency": "daily",
            "runbook_url": "REVIEW_REQUIRED",
        },
    }

    canonical_mode = canonical_write_mode(selected_mode)
    if canonical_mode in {"scd1_upsert", "scd1_hash_diff", "scd2_historical", "snapshot_soft_delete"}:
        key_candidates = metadata.quality_rules.get("not_null", [])
        if key_candidates:
            contract["merge_keys"] = [key_candidates[0]]
            assumptions.append(f"Merge key candidate selected from not_null rules: {key_candidates[0]!r}.")
        decisions_required.append("Validate merge_keys. The first not_null candidate may not be the business key.")

    if metadata.warnings:
        warnings.extend(metadata.warnings)

    validation = validate_generated_contract(contract)

    return ContractDraftResult(
        source_path=str(schema_file),
        contract=contract,
        assumptions=assumptions,
        decisions_required=decisions_required,
        warnings=warnings,
        traceability=Traceability(
            confidence=0.66 if decisions_required else 0.80,
            evidence=[
                EvidenceItem(
                    source="schema",
                    path=str(schema_file),
                    reason="Generated contract draft from schema/profile metadata.",
                    value=str(schema_file),
                    confidence=0.90,
                ),
                EvidenceItem(
                    source="metadata_suggestions",
                    path="quality_rules",
                    reason="Reused deterministic metadata and quality suggestions.",
                    value={
                        "suggestions": len(metadata.suggestions),
                        "warnings": len(metadata.warnings),
                    },
                    confidence=metadata.traceability.confidence,
                ),
            ],
            assumptions=[
                Assumption(
                    statement=assumption,
                    confidence=0.60,
                    review_required=True,
                )
                for assumption in assumptions
            ],
            decisions_required=[
                RequiredDecision(
                    question=decision,
                    reason="Generated contract drafts require explicit review before execution.",
                )
                for decision in decisions_required
            ],
            review_required=True,
        ),
        validation=validation,
    )


def _default_mode(layer: str) -> str:
    normalized = layer.lower()
    if normalized == "bronze":
        return "append"
    if normalized == "silver":
        return "hash_diff_upsert"
    if normalized == "gold":
        return "overwrite"
    return "append"


def _default_source_format(connector: str, source_path: str) -> str | None:
    normalized = connector.lower()
    if normalized in {"http_csv"}:
        return "csv"
    if normalized in {"http_json", "rest_api"}:
        return "json"
    if normalized in {"http_text"}:
        return "text"
    if normalized == "http_file":
        suffix = Path(urlparse(source_path).path).suffix.lower().lstrip(".")
        if suffix in {"csv", "json", "jsonl", "ndjson", "text", "txt"}:
            return "text" if suffix == "txt" else suffix
        return "json"
    return None


def _ddl_from_metadata(
    annotations: dict[str, Any],
    quality_rules: dict[str, Any],
    schema_file: Path,
) -> str | None:
    del annotations, quality_rules
    try:
        import json
        import yaml

        raw = schema_file.read_text(encoding="utf-8")
        payload = yaml.safe_load(raw) if schema_file.suffix.lower() in {".yaml", ".yml"} else json.loads(raw)
        columns = payload.get("columns") if isinstance(payload, dict) else None
        if isinstance(columns, dict):
            pairs = [(name, value.get("type")) for name, value in columns.items() if isinstance(value, dict)]
        elif isinstance(columns, list):
            pairs = [(item.get("name"), item.get("type") or item.get("data_type")) for item in columns if isinstance(item, dict)]
        else:
            return None
    except Exception:
        return None

    ddl_parts = [f"{name} {_spark_type(dtype)}" for name, dtype in pairs if name and dtype]
    return ", ".join(ddl_parts) if ddl_parts else None


def _spark_type(dtype: Any) -> str:
    normalized = str(dtype).upper()
    mapping = {
        "STRING": "STRING",
        "STR": "STRING",
        "TEXT": "STRING",
        "INT": "INT",
        "INTEGER": "INT",
        "LONG": "BIGINT",
        "BIGINT": "BIGINT",
        "DOUBLE": "DOUBLE",
        "FLOAT": "FLOAT",
        "DECIMAL": "DECIMAL(38,18)",
        "BOOLEAN": "BOOLEAN",
        "BOOL": "BOOLEAN",
        "DATE": "DATE",
        "TIMESTAMP": "TIMESTAMP",
    }
    return mapping.get(normalized, normalized)
