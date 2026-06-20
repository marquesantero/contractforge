"""Optional Dataplex lineage and aspect runtime helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_gcp.dataplex.lineage import render_dataplex_aspect_plan, render_dataplex_lineage_plan
from contractforge_gcp.dataplex.runtime import CommandRunner, HttpRunner, _access_token, _http_json, _run_command
from contractforge_gcp.environment import GCPEnvironment


def run_dataplex_lineage_aspects(
    contract: dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
    execute: bool = False,
    publish_lineage: bool = True,
    apply_aspects: bool = True,
    readback: bool = False,
    cleanup_aspect_type: bool = False,
    run_id: str | None = None,
    runner: CommandRunner | None = None,
    http_runner: HttpRunner | None = None,
) -> dict[str, Any]:
    """Render or execute Dataplex lineage/aspect promotion plans for a contract."""

    env = GCPEnvironment.from_contract(environment)
    semantic = semantic_contract_from_mapping(contract)
    lineage_body = render_dataplex_lineage_plan(semantic, env)
    aspect_body = render_dataplex_aspect_plan(semantic, env)
    lineage_plan = json.loads(lineage_body) if lineage_body else None
    aspect_plan = json.loads(aspect_body) if aspect_body else None
    payload: dict[str, Any] = {
        "type": "dataplex_lineage_aspects",
        "status": "PLANNED_NOT_EXECUTED",
        "execution_included": False,
        "plans": {
            "lineage": lineage_plan,
            "aspects": aspect_plan,
        },
        "review_boundaries": [
            "This command only publishes native lineage or aspects when --execute is set.",
            "Stable-final promotion still requires real-account readback evidence linked to a bronze-to-gold run.",
        ],
    }
    if not lineage_plan and not aspect_plan:
        payload["status"] = "SKIPPED"
        payload["reason"] = "contract_has_no_dataplex_lineage_or_aspect_plan"
        return payload
    if not execute:
        return payload

    command_runner = runner or _run_command
    requester = http_runner or _http_json
    try:
        token = _access_token(command_runner)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        execution_run_id = run_id or _default_run_id(semantic.target.name)
        payload["status"] = "RUNNING"
        payload["execution_included"] = True
        payload["run_id"] = execution_run_id
        if publish_lineage and lineage_plan:
            payload["lineage"] = _execute_lineage_plan(
                requester,
                headers,
                lineage_plan,
                run_id=execution_run_id,
                readback=readback,
            )
        if apply_aspects and aspect_plan:
            payload["aspects"] = _execute_aspect_plan(
                requester,
                headers,
                aspect_plan,
                readback=readback,
                cleanup_aspect_type=cleanup_aspect_type,
            )
        payload["status"] = _overall_status(payload)
    except RuntimeError as exc:
        payload["status"] = "BLOCKED"
        payload["error_message"] = str(exc)
    return payload


def _execute_lineage_plan(
    requester: HttpRunner,
    headers: dict[str, str],
    plan: dict[str, Any],
    *,
    run_id: str,
    readback: bool,
) -> dict[str, Any]:
    now = _timestamp()
    replacements = {
        "${event_time_utc}": now,
        "${started_at_utc}": now,
        "${finished_at_utc}": now,
        "${run_id}": run_id,
    }
    publish = plan["openlineage_publication"]
    publication = requester(
        publish["method"],
        publish["url"],
        headers,
        _replace_templates(publish["body_template"], replacements),
    )
    result: dict[str, Any] = {
        "status": "PUBLISHED",
        "publication": publication,
    }
    if readback:
        search_links = _call_plan_request(requester, headers, plan["readback"]["search_links"])
        link_names = [
            str(link["name"])
            for link in search_links.get("links", ())
            if isinstance(link, dict) and str(link.get("name") or "").strip()
        ]
        batch_processes = (
            requester(
                plan["readback"]["batch_search_link_processes"]["method"],
                plan["readback"]["batch_search_link_processes"]["url"],
                headers,
                {"links": link_names},
            )
            if link_names
            else {"status": "SKIPPED", "reason": "search_links_returned_no_link_names"}
        )
        run_name = str(publication.get("run") or "").strip()
        lineage_events = (
            requester("GET", f"https://datalineage.googleapis.com/v1/{run_name}/lineageEvents", headers, None)
            if run_name
            else {"status": "SKIPPED", "reason": "publication_response_did_not_include_run_name"}
        )
        result["readback"] = {
            "search_links": search_links,
            "batch_search_link_processes": batch_processes,
            "lineage_events": lineage_events,
        }
    return result


def _execute_aspect_plan(
    requester: HttpRunner,
    headers: dict[str, str],
    plan: dict[str, Any],
    *,
    readback: bool,
    cleanup_aspect_type: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "APPLIED"}
    create = plan["aspect_type"]["create"]
    try:
        result["aspect_type_create"] = requester(create["method"], create["url"], headers, create["body_template"])
    except RuntimeError as exc:
        if not _is_already_exists(str(exc)):
            raise
        result["aspect_type_create"] = {
            "status": "SKIPPED",
            "reason": "aspect_type_already_exists",
            "message": str(exc),
        }
    search_entry = _call_plan_request(requester, headers, plan["readback"]["search_entry"])
    entry_name = _entry_name_from_search(search_entry, expected_fqn=str(plan["target"].get("fully_qualified_name") or ""))
    lookup = _lookup_entry(requester, headers, plan, entry_name)
    entry_name = str(lookup.get("name") or "").strip()
    if not entry_name:
        raise RuntimeError("Dataplex lookupEntry did not return an entry name required for modifyEntry.")
    result["search_entry"] = search_entry
    result["lookup_entry_before_modify"] = lookup
    modify_body = _replace_templates(
        plan["modify_entry"]["body_template"],
        {"${entry_name_from_lookupEntry}": entry_name},
    )
    result["modify_entry"] = requester(
        plan["modify_entry"]["method"],
        plan["modify_entry"]["url"],
        headers,
        modify_body,
    )
    if readback:
        result["readback"] = {
            "aspect_type": _call_plan_request(requester, headers, plan["readback"]["get_aspect_type"]),
            "entry": _lookup_entry(requester, headers, plan, entry_name),
        }
    if cleanup_aspect_type:
        aspect_type = f"{plan['aspect_type']['parent']}/aspectTypes/{plan['aspect_type']['id']}"
        try:
            result["cleanup"] = requester("DELETE", f"https://dataplex.googleapis.com/v1/{aspect_type}", headers, None)
        except RuntimeError as exc:
            if not _is_not_found(str(exc)):
                raise
            result["cleanup"] = {"status": "SKIPPED", "reason": "aspect_type_not_found", "message": str(exc)}
    return result


def _call_plan_request(requester: HttpRunner, headers: dict[str, str], request: dict[str, Any]) -> dict[str, Any]:
    return requester(request["method"], request["url"], headers, request.get("body"))


def _lookup_entry(
    requester: HttpRunner,
    headers: dict[str, str],
    plan: dict[str, Any],
    entry_name: str,
) -> dict[str, Any]:
    request = plan["readback"]["lookup_entry"]
    url = str(request["url_template"]).replace("{entry_name}", quote(entry_name, safe=""))
    return requester(request["method"], url, headers, None)


def _entry_name_from_search(search_entry: dict[str, Any], *, expected_fqn: str) -> str:
    candidates = []
    for result in search_entry.get("results", ()):
        if not isinstance(result, dict):
            continue
        entry = result.get("dataplexEntry")
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        fqn = str(entry.get("fullyQualifiedName") or "").strip()
        if name:
            candidates.append((name, fqn))
    if expected_fqn:
        for name, fqn in candidates:
            if fqn == expected_fqn:
                return name
    if len(candidates) == 1:
        return candidates[0][0]
    if not candidates:
        raise RuntimeError("Dataplex searchEntries did not return a target entry for modifyEntry.")
    raise RuntimeError("Dataplex searchEntries returned multiple entries; expected fullyQualifiedName match was not found.")


def _replace_templates(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_templates(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_templates(item, replacements) for item in value]
    if isinstance(value, str):
        result = value
        for source, target in replacements.items():
            result = result.replace(source, target)
        return result
    return value


def _overall_status(payload: dict[str, Any]) -> str:
    for key in ("lineage", "aspects"):
        result = payload.get(key)
        if isinstance(result, dict) and result.get("status") in {"FAILED", "BLOCKED"}:
            return "FAILED"
    return "SUCCEEDED"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_run_id(table: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_table = "".join(ch if ch.isalnum() else "_" for ch in table).strip("_") or "contract"
    return f"cf_dataplex_{safe_table}_{stamp}"


def _is_already_exists(value: str) -> bool:
    normalized = value.lower()
    return "already_exists" in normalized or "already exists" in normalized or "http 409" in normalized


def _is_not_found(value: str) -> bool:
    normalized = value.lower()
    return "not_found" in normalized or "not found" in normalized or "http 404" in normalized
