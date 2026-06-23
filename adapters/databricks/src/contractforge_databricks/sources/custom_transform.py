"""Databricks artifacts for contract-managed custom treatment boundaries."""

from __future__ import annotations

import json
import re
from typing import Any

from contractforge_core.semantic import SemanticContract
from contractforge_databricks.bundles.assets import DatabricksNotebookTaskSpec
from contractforge_databricks.contract_extensions import databricks_extensions

_TASK_KEY_RE = re.compile(r"[^A-Za-z0-9_]+")


def is_custom_transform_source(source: dict[str, Any]) -> bool:
    return str(source.get("type") or "").strip().lower() == "custom_transform"


def render_custom_transform_review_plan(contract: SemanticContract) -> str:
    source = dict(contract.source.raw or {})
    transform = dict(contract.transform.raw or {}) if contract.transform else {}
    custom = dict(transform.get("custom") or {})
    extension = _custom_extension(contract)
    payload = {
        "kind": "databricks_custom_transform_review_plan",
        "source_type": "custom_transform",
        "inputs": source.get("inputs") or [],
        "custom_transform": custom,
        "target": {
            "namespace": contract.target.namespace,
            "table": contract.target.name,
            "layer": contract.target.layer,
        },
        "databricks": _redact_extension(extension),
        "guardrails": [
            "The contract declares named inputs before adapter execution.",
            "The notebook is an adapter binding; it does not change write mode, quality, access or evidence semantics.",
            "Downstream schema, quality and write-mode validation still run after the custom treatment output is produced.",
            "Review the notebook artifact hash/version in deployment evidence before production use.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_custom_transform_review_markdown(contract: SemanticContract) -> str:
    source = dict(contract.source.raw or {})
    transform = dict(contract.transform.raw or {}) if contract.transform else {}
    custom = dict(transform.get("custom") or {})
    extension = _custom_extension(contract)
    lines = [
        "# Databricks Custom Treatment Review",
        "",
        "This contract uses `source.type: custom_transform` to declare a reviewed custom treatment boundary.",
        "",
        "## Inputs",
        "",
    ]
    for item in source.get("inputs") or []:
        alias = item.get("alias")
        reference = item.get("ref") or item.get("table") or item.get("table_ref") or item.get("path") or "<query>"
        lines.append(f"- `{alias}`: `{reference}`")
    if not source.get("inputs"):
        lines.append("- No inputs declared.")
    lines.extend(
        [
            "",
            "## Contract Output",
            "",
            f"- Output: `{custom.get('output') or contract.target.name}`",
            f"- Expected columns: `{', '.join(custom.get('expected_columns') or []) or 'not declared'}`",
            "",
            "## Databricks Binding",
            "",
            f"- Notebook path: `{extension.get('notebook_path') or 'not declared'}`",
            f"- Task key: `{extension.get('task_key') or 'adapter-generated'}`",
            "",
            "## Guardrails",
            "",
            "- The notebook is a native runtime binding, not a semantic shortcut.",
            "- ContractForge still applies schema, quality, write-mode and evidence controls after execution.",
            "- Production deployment should record the notebook version or artifact hash.",
            "",
        ]
    )
    return "\n".join(lines)


def custom_transform_notebook_task(
    contract: SemanticContract,
    *,
    artifact_prefix: str,
) -> DatabricksNotebookTaskSpec | None:
    source = dict(contract.source.raw or {})
    if not is_custom_transform_source(source):
        return None
    extension = _custom_extension(contract)
    notebook_path = str(extension.get("notebook_path") or "").strip()
    if not notebook_path:
        return None
    parameters = extension.get("base_parameters") if isinstance(extension.get("base_parameters"), dict) else {}
    task_key = str(extension.get("task_key") or f"{artifact_prefix}_custom_transform").strip()
    return DatabricksNotebookTaskSpec(
        task_key=_safe_task_key(task_key),
        notebook_path=notebook_path,
        base_parameters={str(key): str(value) for key, value in parameters.items()},
    )


def _custom_extension(contract: SemanticContract) -> dict[str, Any]:
    value = databricks_extensions(contract).get("custom_transform")
    return dict(value) if isinstance(value, dict) else {}


def _redact_extension(extension: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(extension)
    for key in list(redacted):
        if any(token in key.lower() for token in ("password", "secret", "token", "key")):
            redacted[key] = "***REDACTED***"
    return redacted


def _safe_task_key(value: str) -> str:
    sanitized = _TASK_KEY_RE.sub("_", value).strip("_")
    return sanitized or "custom_transform"
