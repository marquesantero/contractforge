"""Review-only AWS native passthrough apply candidate shapes."""

from __future__ import annotations

from typing import Any


def apply_candidates(targets: tuple[str, ...], descriptor: dict[str, Any]) -> list[dict[str, Any]]:
    """Return non-executable AWS API request skeletons for reviewed handoff paths."""

    return [_candidate(target, descriptor) for target in targets]


def _candidate(target: str, descriptor: dict[str, Any]) -> dict[str, Any]:
    renderer = _CANDIDATE_RENDERERS.get(target, _glue_connection_candidate)
    return renderer(target, descriptor)


def _appflow_candidate(target: str, descriptor: dict[str, Any]) -> dict[str, Any]:
    system = _slug(descriptor["system"])
    obj = _slug(descriptor["object"])
    return {
        "target": target,
        "aws_api": "appflow:CreateFlow",
        "status": "REVIEW_REQUIRED",
        "draft_request": {
            "flowName": f"cf-{system}-{obj}",
            "triggerConfig": {"triggerType": "OnDemand"},
            "sourceFlowConfig": {
                "connectorType": str(descriptor["system"]),
                "sourceConnectorProperties": {"object": descriptor["object"]},
            },
            "destinationFlowConfigList": [
                {
                    "connectorType": "S3",
                    "destinationConnectorProperties": {
                        "S3": {"bucketName": "<landing-bucket>", "bucketPrefix": f"contractforge/{system}/{obj}/"}
                    },
                }
            ],
            "tasks": [{"sourceFields": ["<review-required>"], "taskType": "Map"}],
        },
        "review_notes": [
            "Confirm the application/object is supported by AppFlow in the target region.",
            "Replace placeholder landing bucket/prefix and field mappings.",
            "Record the AppFlow execution id in ContractForge source metadata evidence.",
        ],
    }


def _dms_candidate(target: str, descriptor: dict[str, Any]) -> dict[str, Any]:
    system = _slug(descriptor["system"])
    obj = str(descriptor["object"])
    return {
        "target": target,
        "aws_api": "dms:CreateReplicationConfig",
        "status": "REVIEW_REQUIRED",
        "draft_request": {
            "ReplicationConfigIdentifier": f"cf-{system}-{_slug(obj)}",
            "SourceEndpointArn": "<source-endpoint-arn>",
            "TargetEndpointArn": "<target-endpoint-arn>",
            "ReplicationType": "full-load-and-cdc",
            "TableMappings": {
                "rules": [
                    {
                        "rule-type": "selection",
                        "rule-id": "1",
                        "rule-name": "include-contract-object",
                        "object-locator": _dms_object_locator(obj),
                        "rule-action": "include",
                    }
                ]
            },
        },
        "review_notes": [
            "Confirm CDC/delete semantics and source completeness before downstream ContractForge writes.",
            "Replace endpoint ARNs and table mappings after network/security review.",
            "Record DMS replication config/task identifiers in ContractForge source metadata evidence.",
        ],
    }


def _glue_connection_candidate(target: str, descriptor: dict[str, Any]) -> dict[str, Any]:
    system = _slug(descriptor["system"])
    return {
        "target": target,
        "aws_api": "glue:CreateConnection",
        "status": "REVIEW_REQUIRED",
        "draft_request": {
            "ConnectionInput": {
                "Name": f"cf-{system}-connection",
                "ConnectionType": "CUSTOM",
                "ConnectionProperties": {
                    "CONNECTOR_TYPE": str(descriptor["system"]),
                    "CONNECTOR_OBJECT": str(descriptor["object"]),
                    "SECRET_ID": "<secrets-manager-secret-id>",
                },
            }
        },
        "review_notes": [
            "Confirm connector type, Marketplace/native connector availability and licensing.",
            "Replace connection properties with the connector-owned option names.",
            "Keep connector runtime behavior outside the ContractForge core package.",
        ],
    }


def _dms_object_locator(object_name: str) -> dict[str, str]:
    parts = object_name.split(".", 1)
    schema, table = (parts[0], parts[1]) if len(parts) == 2 else ("%", object_name)
    return {"schema-name": schema, "table-name": table}


def _slug(value: object) -> str:
    text = str(value).strip().lower()
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in text)
    return "-".join(part for part in cleaned.split("-") if part) or "source"


_CANDIDATE_RENDERERS = {
    "appflow": _appflow_candidate,
    "appflow_if_supported": _appflow_candidate,
    "dms": _dms_candidate,
    "dms_if_database_replication": _dms_candidate,
}
