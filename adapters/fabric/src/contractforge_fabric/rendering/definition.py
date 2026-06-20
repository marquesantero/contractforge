"""Render Fabric item definition drafts."""

from __future__ import annotations

import base64
import json
import re

from contractforge_core.semantic import SemanticContract
from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.rendering.notebook import render_lakehouse_notebook


def render_notebook_item_definition(
    contract: SemanticContract,
    environment: FabricEnvironment,
    *,
    notebook_source: str | None = None,
) -> str:
    """Render a review-only Fabric Notebook REST definition draft."""

    source = notebook_source or render_lakehouse_notebook(contract, environment)
    fabric_source = render_fabric_git_notebook_source(source)
    display_name = _display_name(contract)
    description = "ContractForge generated Fabric notebook draft. Review before execution."
    platform = _platform_payload(display_name=display_name, description=description)
    definition = {
        "format": "fabricGitSource",
        "parts": [
            {
                "path": "notebook-content.py",
                "payload": _base64(fabric_source),
                "payloadType": "InlineBase64",
            },
            {
                "path": ".platform",
                "payload": _base64(
                    json.dumps(platform, separators=(",", ":"), sort_keys=True),
                ),
                "payloadType": "InlineBase64",
            },
        ],
    }
    payload = {
        "adapter": "fabric",
        "kind": "fabric_notebook_item_definition",
        "runtime_status": "render_only",
        "deployable": False,
        "workspace": {
            "id": environment.workspace_id,
            "name": environment.workspace_name,
        },
        "lakehouse": {
            "id": environment.lakehouse_id,
            "name": environment.lakehouse_name,
        },
        "rest_shape": {
            "format": "fabricGitSource",
            "payload_type": "InlineBase64",
            "content_part": "notebook-content.py",
            "metadata_part": ".platform",
        },
        "create_notebook_request": {
            "displayName": display_name,
            "description": description,
            "definition": definition,
        },
        "update_definition_request": {
            "definition": definition,
        },
        "warnings": [
            "This is a deterministic review artifact, not a Fabric submission.",
            (
                "A future runtime must resolve workspace/item IDs, preflight permissions/capacity "
                "and poll LRO responses."
            ),
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_fabric_git_notebook_source(source: str) -> str:
    """Wrap Python code in Fabric's fabricGitSource notebook format."""

    lines = [
        "# Fabric notebook source",
        "# METADATA ********************",
        "# META {",
        '# META   "kernel_info": {',
        '# META     "name": "synapse_pyspark"',
        "# META   },",
        '# META   "dependencies": {}',
        "# META }",
        "# CELL ********************",
        source.rstrip(),
        "# METADATA ********************",
        "# META {",
        '# META   "language": "python",',
        '# META   "language_group": "synapse_pyspark"',
        "# META }",
        "",
    ]
    return "\r\n".join(lines)


def _display_name(contract: SemanticContract) -> str:
    namespace = contract.target.namespace or "default"
    raw = f"cf_{namespace}_{contract.target.name}"
    return re.sub(r"[^A-Za-z0-9 _.-]+", "_", raw).replace(".", "_")[:128]


def _platform_payload(*, display_name: str, description: str) -> dict[str, object]:
    schema = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    return {
        "$schema": schema,
        "metadata": {
            "type": "Notebook",
            "displayName": display_name,
            "description": description,
        },
        "config": {
            "version": "2.0",
        },
    }


def _base64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")
