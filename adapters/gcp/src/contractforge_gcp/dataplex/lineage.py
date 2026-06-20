"""Render Dataplex lineage and aspect planning artifacts.

These artifacts describe the native Google Cloud calls needed for Dataplex
lineage and governance aspects. They are deterministic review plans; this
module does not publish lineage events or mutate catalog entries.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.governance.annotations import unsupported_annotation_steps
from contractforge_gcp.rendering.names import target_dataset, target_project, target_table_id


def has_dataplex_lineage_plan(contract: SemanticContract) -> bool:
    """Return true when a native Dataplex lineage plan can be rendered."""

    return bool(contract.target.name)


def has_dataplex_aspect_plan(contract: SemanticContract) -> bool:
    """Return true when annotations or operations need a Dataplex aspect plan."""

    return bool(_aspect_data(contract)["table"] or _aspect_data(contract)["columns"] or _aspect_data(contract)["operations"])


def render_dataplex_lineage_plan(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render the native Dataplex Data Lineage publication/readback plan."""

    if not has_dataplex_lineage_plan(contract):
        return ""
    project = target_project(contract, env) or env.project_id or "UNSPECIFIED_PROJECT"
    location = _dataplex_location(env)
    target_resource = _bigquery_resource(project, target_dataset(contract, env), contract.target.name)
    source_resource = _source_resource(contract, env)
    parent = f"projects/{project}/locations/{location}"
    process_id = _slug(f"cf-{target_dataset(contract, env)}-{contract.target.name}-{contract.write.mode}")
    payload = {
        "kind": "contractforge.gcp.dataplex_lineage_plan.v1",
        "status": "PLANNED_REVIEW_REQUIRED",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "execution": {
            "included": False,
            "reason": (
                "This artifact plans native Dataplex Data Lineage publication and readback. "
                "It does not call Data Lineage APIs or claim live native lineage parity."
            ),
        },
        "target": {
            "project_id": project,
            "location": location,
            "table": target_table_id(contract, env),
            "bigquery_resource": target_resource,
        },
        "source": {
            "type": contract.source.kind,
            "name": contract.source.name,
            "resource": source_resource,
        },
        "openlineage_publication": {
            "method": "POST",
            "url": f"https://datalineage.googleapis.com/v1/{parent}:processOpenLineageRunEvent",
            "body_template": {
                "eventType": "COMPLETE",
                "eventTime": "${event_time_utc}",
                "producer": "contractforge-gcp",
                "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
                "run": {"runId": "${run_id}"},
                "job": {
                    "namespace": f"bigquery://{project}",
                    "name": f"{contract.target.layer}.{contract.target.name}.{contract.write.mode}",
                },
                "inputs": [{"namespace": _lineage_namespace(source_resource), "name": source_resource}],
                "outputs": [{"namespace": _lineage_namespace(target_resource), "name": target_resource}],
            },
        },
        "native_resource_publication": {
            "process": {
                "method": "POST",
                "url": f"https://datalineage.googleapis.com/v1/{parent}/processes",
                "body_template": {
                    "displayName": f"ContractForge {contract.target.layer}.{contract.target.name}",
                    "attributes": {
                        "adapter": "contractforge-gcp",
                        "target": target_table_id(contract, env),
                        "write_mode": contract.write.mode,
                    },
                },
                "processId": process_id,
            },
            "run": {
                "method": "POST",
                "url_template": f"https://datalineage.googleapis.com/v1/{parent}/processes/{{process_id}}/runs",
                "body_template": {"displayName": "${run_id}"},
            },
            "lineage_event": {
                "method": "POST",
                "url_template": (
                    f"https://datalineage.googleapis.com/v1/{parent}/processes/"
                    "{process_id}/runs/{run_id}/lineageEvents"
                ),
                "body_template": {
                    "startTime": "${started_at_utc}",
                    "endTime": "${finished_at_utc}",
                    "links": [{"source": source_resource, "target": target_resource}],
                },
            },
        },
        "readback": {
            "search_links": {
                "method": "POST",
                "url": f"https://datalineage.googleapis.com/v1/{parent}:searchLinks",
                "body": {"target": {"fullyQualifiedName": target_resource}},
            },
            "batch_search_link_processes": {
                "method": "POST",
                "url": f"https://datalineage.googleapis.com/v1/{parent}:batchSearchLinkProcesses",
                "body_template": {"links": ["${link_name_from_searchLinks}"]},
            },
            "list_lineage_events": {
                "method": "GET",
                "url_template": (
                    f"https://datalineage.googleapis.com/v1/{parent}/processes/"
                    "{process_id}/runs/{run_id}/lineageEvents"
                ),
            },
        },
        "evidence_required": [
            "The publication response records process, run and lineage event identifiers for the same ContractForge run id.",
            "searchLinks or batchSearchLinkProcesses returns an edge from the planned source resource to the target resource.",
            "The native Dataplex event and BigQuery control-table OpenLineage event reconcile on run id and target table.",
        ],
        "review_boundaries": [
            "This artifact does not publish native Dataplex lineage events.",
            "Promotion requires a bronze-to-gold real-account run with native lineage readback.",
        ],
        "sources": [
            "https://cloud.google.com/data-catalog/docs/reference/data-lineage/rest",
            "https://docs.cloud.google.com/dataplex/docs/lineage-views",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_dataplex_aspect_plan(contract: SemanticContract, env: GCPEnvironment) -> str:
    """Render the Dataplex Universal Catalog aspect create/apply/readback plan."""

    aspect_data = _aspect_data(contract)
    if not (aspect_data["table"] or aspect_data["columns"] or aspect_data["operations"]):
        return ""
    project = target_project(contract, env) or env.project_id or "UNSPECIFIED_PROJECT"
    location = _dataplex_location(env)
    parent = f"projects/{project}/locations/{location}"
    aspect_type_id = "contractforge-governance"
    aspect_type_ref = f"{project}.{location}.{aspect_type_id}"
    target_resource = _bigquery_resource(project, target_dataset(contract, env), contract.target.name)
    target_fqn = _bigquery_fqn(project, target_dataset(contract, env), contract.target.name)
    payload = {
        "kind": "contractforge.gcp.dataplex_aspect_plan.v1",
        "status": "PLANNED_REVIEW_REQUIRED",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "execution": {
            "included": False,
            "reason": (
                "This artifact plans Dataplex Universal Catalog aspect taxonomy, apply and readback. "
                "It does not create AspectTypes or modify catalog entries."
            ),
        },
        "target": {
            "project_id": project,
            "location": location,
            "table": target_table_id(contract, env),
            "bigquery_resource": target_resource,
            "fully_qualified_name": target_fqn,
        },
        "aspect_type": {
            "parent": parent,
            "id": aspect_type_id,
            "reference": aspect_type_ref,
            "create": {
                "method": "POST",
                "url": f"https://dataplex.googleapis.com/v1/{parent}/aspectTypes?aspectTypeId={aspect_type_id}",
                "body_template": {
                    "displayName": "ContractForge governance",
                    "description": "ContractForge annotations and operations metadata for governed table review.",
                    "metadataTemplate": _aspect_metadata_template(),
                },
            },
        },
        "modify_entry": {
            "method": "POST",
            "url": f"https://dataplex.googleapis.com/v1/{parent}:modifyEntry",
            "body_template": {
                "entry": {
                    "name": "${entry_name_from_lookupEntry}",
                    "aspects": {
                        aspect_type_ref: {
                            "aspectType": aspect_type_ref,
                            "path": "",
                            "data": _aspect_schema_data(aspect_data),
                        }
                    },
                },
                "updateMask": "aspects",
                "deleteMissingAspects": False,
                "aspectKeys": [aspect_type_ref],
            },
        },
        "readback": {
            "search_entry": {
                "method": "POST",
                "url": (
                    f"https://dataplex.googleapis.com/v1/{parent}:searchEntries"
                    f"?query={quote(target_fqn, safe='')}&pageSize=10&scope=projects/{project}"
                ),
            },
            "lookup_entry": {
                "method": "GET",
                "url_template": f"https://dataplex.googleapis.com/v1/{parent}:lookupEntry?entry={{entry_name}}&view=ALL",
            },
            "get_aspect_type": {
                "method": "GET",
                "url": f"https://dataplex.googleapis.com/v1/{parent}/aspectTypes/{aspect_type_id}",
            },
            "assertions": [
                f"entry.aspects['{aspect_type_ref}'].data.contractforge_payload_json matches the rendered table, column and operations metadata.",
                "No secret-looking values appear in the rendered aspect payload.",
            ],
        },
        "evidence_required": [
            "AspectType exists with the approved ContractForge governance schema.",
            "modifyEntry response/readback contains the expected aspect key on the target BigQuery table entry.",
            "Readback data matches redacted ContractForge annotations and operations metadata.",
        ],
        "review_boundaries": [
            "This artifact does not create Dataplex AspectTypes or modify entries.",
            "Promotion requires an approved aspect taxonomy and real-account modifyEntry/readback evidence.",
        ],
        "sources": [
            "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/Aspect",
            "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations/modifyEntry",
            "https://docs.cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.aspectTypes",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _aspect_metadata_template() -> dict[str, Any]:
    return {
        "name": "contractforge_governance",
        "type": "record",
        "recordFields": [
            {"name": "contractforge_payload_json", "type": "string", "index": 1},
            {
                "name": "table_aliases",
                "type": "array",
                "index": 2,
                "arrayItems": {"name": "item", "type": "string"},
            },
            {"name": "table_tags_json", "type": "string", "index": 3},
            {"name": "table_deprecated", "type": "bool", "index": 4},
            {"name": "table_pii_json", "type": "string", "index": 5},
            {"name": "columns_json", "type": "string", "index": 6},
            {"name": "operations_json", "type": "string", "index": 7},
        ],
    }


def _aspect_schema_data(aspect_data: dict[str, Any]) -> dict[str, Any]:
    table = _mapping(aspect_data.get("table"))
    columns = _mapping(aspect_data.get("columns"))
    operations = _mapping(aspect_data.get("operations"))
    payload: dict[str, Any] = {
        "contractforge_payload_json": _stable_json(aspect_data),
    }
    if isinstance(table.get("aliases"), list):
        payload["table_aliases"] = [str(item) for item in table["aliases"]]
    if table.get("tags") not in (None, "", [], {}):
        payload["table_tags_json"] = _stable_json(table["tags"])
    if isinstance(table.get("deprecated"), bool):
        payload["table_deprecated"] = table["deprecated"]
    if table.get("pii") not in (None, "", [], {}):
        payload["table_pii_json"] = _stable_json(table["pii"])
    if columns:
        payload["columns_json"] = _stable_json(columns)
    if operations:
        payload["operations_json"] = _stable_json(operations)
    return payload


def _aspect_data(contract: SemanticContract) -> dict[str, Any]:
    annotations = contract.governance.annotations if contract.governance else None
    table_annotations = _mapping(annotations.get("table")) if isinstance(annotations, dict) else {}
    column_annotations = _mapping(annotations.get("columns")) if isinstance(annotations, dict) else {}
    table_payload = _annotation_subset(table_annotations)
    column_payload = {
        str(column): _annotation_subset(_mapping(config))
        for column, config in column_annotations.items()
        if _annotation_subset(_mapping(config))
    }
    operations = (
        redact_value(contract.operations.metadata)
        if contract.operations and isinstance(contract.operations.metadata, dict)
        else {}
    )
    if not unsupported_annotation_steps(contract) and not operations:
        return {"table": {}, "columns": {}, "operations": {}}
    return {
        "table": table_payload,
        "columns": column_payload,
        "operations": operations,
    }


def _annotation_subset(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: redact_value(data[key])
        for key in ("aliases", "tags", "deprecated", "pii")
        if data.get(key) not in (None, "", [], {})
    }


def _dataplex_location(env: GCPEnvironment) -> str:
    return (env.location or "us").strip().lower()


def _bigquery_resource(project: str, dataset: str, table: str) -> str:
    return f"//bigquery.googleapis.com/projects/{project}/datasets/{dataset}/tables/{table}"


def _bigquery_fqn(project: str, dataset: str, table: str) -> str:
    return f"bigquery:{project}.{dataset}.{table}"


def _source_resource(contract: SemanticContract, env: GCPEnvironment) -> str:
    if contract.source.kind in {"table", "view"} and contract.source.location:
        parts = contract.source.location.split(".")
        if len(parts) == 3:
            project, dataset, table = parts
            return _bigquery_resource(project, dataset, table)
        if len(parts) == 2 and env.project_id:
            dataset, table = parts
            return _bigquery_resource(env.project_id, dataset, table)
    return f"contractforge://source/{contract.source.kind}/{_slug(contract.source.name)}"


def _lineage_namespace(resource: str) -> str:
    if resource.startswith("//bigquery.googleapis.com/projects/"):
        parts = resource.split("/")
        return f"bigquery://{parts[4]}"
    return "contractforge://source"


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _slug(value: str) -> str:
    lowered = str(value).lower().replace("_", "-").replace(".", "-")
    cleaned = re.sub(r"[^a-z0-9-]+", "-", lowered)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"cf-{cleaned}"
    return cleaned[:63].rstrip("-") or "contractforge"
