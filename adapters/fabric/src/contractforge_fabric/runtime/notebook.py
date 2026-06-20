"""Notebook item deployment helpers for Fabric."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.rendering.definition import render_notebook_item_definition
from contractforge_fabric.runtime.factory import fabric_rest_client_from_environment
from contractforge_fabric.runtime.rest import FabricOperation, FabricRestClient, FabricRestError


@dataclass(frozen=True)
class FabricNotebookDeployment:
    action: str
    display_name: str
    notebook_id: str | None
    operation: FabricOperation | None = None
    response: dict[str, Any] | None = None
    definition_hash: str | None = None
    previous_definition_hash: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class FabricNotebookRunOutcome:
    status: str
    code: str
    message: str
    raw: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"


def classify_fabric_notebook_run_result(result: dict[str, Any]) -> FabricNotebookRunOutcome:
    """Normalize Fabric notebook job instance results."""

    status = str(result.get("status") or "").upper()
    if status in {"SUCCEEDED", "COMPLETED"}:
        return FabricNotebookRunOutcome(
            status="SUCCEEDED",
            code="FABRIC_NOTEBOOK_RUN_SUCCEEDED",
            message="Fabric notebook run succeeded.",
            raw=result,
        )
    if status in {"NOTSTARTED", "RUNNING", "INPROGRESS", "IN_PROGRESS", "QUEUED"}:
        return FabricNotebookRunOutcome(
            status="RUNNING",
            code="FABRIC_NOTEBOOK_RUN_IN_PROGRESS",
            message=f"Fabric notebook run is `{status}`.",
            raw=result,
        )
    failure = result.get("failureReason") if isinstance(result.get("failureReason"), dict) else {}
    message = str(failure.get("message") or result.get("message") or "")
    if "TooManyRequestsForCapacity" in message or "HTTP Response code 430" in message:
        return FabricNotebookRunOutcome(
            status="BLOCKED",
            code="FABRIC_SPARK_CAPACITY_THROTTLED",
            message=message,
            raw=result,
        )
    return FabricNotebookRunOutcome(
        status="FAILED",
        code="FABRIC_NOTEBOOK_RUN_FAILED",
        message=message or f"Fabric notebook run ended with status `{status or 'UNKNOWN'}`.",
        raw=result,
    )


def fabric_notebook_default_lakehouse_execution_data(
    *,
    workspace_id: str,
    lakehouse_id: str,
    compute: str = "Spark",
) -> dict[str, Any]:
    return {
        "compute": compute,
        "computeConfiguration": {
            "defaultLakehouse": {
                "referenceType": "ById",
                "itemId": lakehouse_id,
                "workspaceId": workspace_id,
            }
        },
    }


def run_fabric_notebook_from_environment(
    environment: FabricEnvironment | dict[str, Any],
    *,
    client: FabricRestClient | None = None,
) -> FabricOperation:
    """Submit a Fabric Notebook run using configured Notebook and Lakehouse IDs."""

    env = environment if isinstance(environment, FabricEnvironment) else FabricEnvironment.from_contract(environment)
    if not env.workspace_id:
        raise ValueError("Fabric notebook run requires workspace_id")
    if not env.notebook_id:
        raise ValueError("Fabric notebook run requires notebook_id")
    if not env.lakehouse_id:
        raise ValueError("Fabric notebook run requires lakehouse_id")
    client = client or fabric_rest_client_from_environment(env)
    return client.run_notebook(
        notebook_id=env.notebook_id,
        execution_data=fabric_notebook_default_lakehouse_execution_data(
            workspace_id=env.workspace_id,
            lakehouse_id=env.lakehouse_id,
        ),
    )


def deploy_fabric_notebook_contract(
    contract: dict[str, Any],
    environment: FabricEnvironment | dict[str, Any],
    *,
    client: FabricRestClient | None = None,
    update_existing: bool = False,
) -> FabricNotebookDeployment:
    """Create or update a Fabric Notebook item from a renderable contract."""

    env = environment if isinstance(environment, FabricEnvironment) else FabricEnvironment.from_contract(environment)
    semantic = semantic_contract_from_mapping(contract)
    rendered = json.loads(render_notebook_item_definition(semantic, env))
    create_request = rendered["create_notebook_request"]
    definition = create_request["definition"]
    display_name = env.notebook_name or create_request["displayName"]
    description = create_request.get("description")
    client = client or fabric_rest_client_from_environment(env)

    if env.notebook_id:
        previous_hash = _current_definition_hash(client, env.notebook_id)
        definition_hash = definition_fingerprint(definition)
        if previous_hash == definition_hash:
            return FabricNotebookDeployment(
                action="unchanged",
                display_name=display_name,
                notebook_id=env.notebook_id,
                definition_hash=definition_hash,
                previous_definition_hash=previous_hash,
            )
        if not update_existing:
            return FabricNotebookDeployment(
                action="update_blocked",
                display_name=display_name,
                notebook_id=env.notebook_id,
                definition_hash=definition_hash,
                previous_definition_hash=previous_hash,
                message="Existing Fabric Notebook definition differs; pass update_existing=True to update it.",
            )
        if previous_hash is None:
            return FabricNotebookDeployment(
                action="update_blocked",
                display_name=display_name,
                notebook_id=env.notebook_id,
                definition_hash=definition_hash,
                previous_definition_hash=previous_hash,
                message="Existing Fabric Notebook definition could not be read; update was blocked.",
            )
        result = client.update_notebook_definition(notebook_id=env.notebook_id, definition=definition)
        return _deployment_result(
            action="updated",
            display_name=display_name,
            notebook_id=env.notebook_id,
            result=result,
            definition_hash=definition_hash,
            previous_definition_hash=previous_hash,
        )

    existing_id = _find_notebook_id(client, display_name)
    if existing_id:
        if not update_existing:
            return FabricNotebookDeployment(
                action="exists",
                display_name=display_name,
                notebook_id=existing_id,
                definition_hash=definition_fingerprint(definition),
            )
        previous_hash = _current_definition_hash(client, existing_id)
        definition_hash = definition_fingerprint(definition)
        if previous_hash == definition_hash:
            return FabricNotebookDeployment(
                action="unchanged",
                display_name=display_name,
                notebook_id=existing_id,
                definition_hash=definition_hash,
                previous_definition_hash=previous_hash,
            )
        if previous_hash is None:
            return FabricNotebookDeployment(
                action="update_blocked",
                display_name=display_name,
                notebook_id=existing_id,
                definition_hash=definition_hash,
                previous_definition_hash=previous_hash,
                message="Existing Fabric Notebook definition could not be read; update was blocked.",
            )
        result = client.update_notebook_definition(notebook_id=existing_id, definition=definition)
        return _deployment_result(
            action="updated",
            display_name=display_name,
            notebook_id=existing_id,
            result=result,
            definition_hash=definition_hash,
            previous_definition_hash=previous_hash,
        )

    result = client.create_notebook(
        display_name=display_name,
        description=description,
        definition=definition,
    )
    return _deployment_result(
        action="created",
        display_name=display_name,
        notebook_id=None,
        result=result,
        definition_hash=definition_fingerprint(definition),
    )


def _find_notebook_id(client: FabricRestClient, display_name: str) -> str | None:
    try:
        return client.resolve_item_id(item_type="Notebook", display_name=display_name)
    except FabricRestError as exc:
        if "was not found" in str(exc):
            return None
        raise


def _deployment_result(
    *,
    action: str,
    display_name: str,
    notebook_id: str | None,
    result: FabricOperation | dict[str, Any],
    definition_hash: str | None = None,
    previous_definition_hash: str | None = None,
) -> FabricNotebookDeployment:
    if isinstance(result, FabricOperation):
        return FabricNotebookDeployment(
            action=action,
            display_name=display_name,
            notebook_id=notebook_id,
            operation=result,
            definition_hash=definition_hash,
            previous_definition_hash=previous_definition_hash,
        )
    response_id = result.get("id")
    return FabricNotebookDeployment(
        action=action,
        display_name=display_name,
        notebook_id=response_id if isinstance(response_id, str) else notebook_id,
        response=result,
        definition_hash=definition_hash,
        previous_definition_hash=previous_definition_hash,
    )


def _current_definition_hash(client: FabricRestClient, notebook_id: str) -> str | None:
    try:
        payload = client.get_notebook_definition(notebook_id=notebook_id)
    except FabricRestError as exc:
        if exc.status_code in {404, 409}:
            return None
        raise
    definition = payload.get("definition") if isinstance(payload.get("definition"), dict) else payload
    return definition_fingerprint(definition)


def definition_fingerprint(definition: Mapping[str, Any]) -> str:
    """Return a stable hash for Fabric item definitions."""

    normalized = _normalize_definition(definition)
    body = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _normalize_definition(definition: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(definition)
    normalized.setdefault("format", "fabricGitSource")
    parts = normalized.get("parts")
    if isinstance(parts, list):
        normalized["parts"] = sorted(
            (dict(part) for part in parts if isinstance(part, dict)),
            key=lambda part: (
                str(part.get("path") or ""),
                str(part.get("payloadType") or ""),
                str(part.get("payload") or ""),
            ),
        )
    return normalized
