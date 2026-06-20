"""BigQuery governance reconciliation planning artifacts."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_gcp.environment import GCPEnvironment
from contractforge_gcp.governance.ledger import governance_ledger_plan, has_governance_ledger_plan
from contractforge_gcp.rendering.names import evidence_dataset, table_prefix, target_dataset, target_project, target_table_id


def has_governance_reconciliation_plan(contract: SemanticContract) -> bool:
    return has_governance_ledger_plan(contract)


def render_bigquery_governance_reconciliation_plan(contract: SemanticContract, environment: GCPEnvironment) -> str:
    if not has_governance_reconciliation_plan(contract):
        return ""
    payload = governance_reconciliation_plan(contract, environment)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def run_bigquery_governance_reconciliation(
    contract: SemanticContract | dict[str, Any],
    *,
    environment: GCPEnvironment | dict[str, Any] | None = None,
    execute: bool = False,
    runner: Any | None = None,
) -> dict[str, Any]:
    semantic = contract if isinstance(contract, SemanticContract) else semantic_contract_from_mapping(contract)
    env = _coerce_environment(environment)
    if not has_governance_reconciliation_plan(semantic):
        return {
            "kind": "contractforge.gcp.bigquery_governance_reconciliation_result.v1",
            "adapter": "contractforge-gcp",
            "subtarget": "gcp_bigquery",
            "status": "SKIPPED",
            "reason": "No governance intent declared for this contract.",
        }

    plan = governance_reconciliation_plan(semantic, env)
    result: dict[str, Any] = {
        "kind": "contractforge.gcp.bigquery_governance_reconciliation_result.v1",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "maturity_gate": "GCP-BQ-17B",
        "target": plan["target"],
        "status": "PLANNED_NOT_EXECUTED",
        "execute": execute,
        "plan": plan,
        "operations": [],
    }
    if not execute:
        return result

    project, dataset, table = _target_parts(semantic, env)
    location = env.location or "US"
    actual_state: dict[str, Any] = {}
    operations = result["operations"]

    table_show = _run_command(
        [
            _bq_executable(),
            f"--project_id={project}",
            f"--location={location}",
            "--format=json",
            "show",
            f"{project}:{dataset}.{table}",
        ],
        runner=runner,
    )
    operations.append({"name": "read_table_metadata", **table_show})
    if table_show["status"] == "SUCCEEDED":
        actual_state["table_metadata"] = _json_object(table_show.get("stdout") or "")
    else:
        result["status"] = "FAILED"
        return result

    row_policies = _run_command(
        [
            _bq_executable(),
            f"--project_id={project}",
            f"--location={location}",
            "--format=json",
            "ls",
            "--row_access_policies",
            f"{project}:{dataset}.{table}",
        ],
        runner=runner,
    )
    operations.append({"name": "read_row_access_policies", **row_policies})
    if row_policies["status"] == "SUCCEEDED":
        actual_state["row_access_policies"] = _json_list_or_empty(row_policies.get("stdout") or "")
    else:
        result["status"] = "FAILED"
        return result

    for name, query in _readback_queries(project=project, dataset=dataset, table=table).items():
        readback = _run_command(
            [
                _bq_executable(),
                f"--project_id={project}",
                f"--location={location}",
                "--format=json",
                "query",
                "--use_legacy_sql=false",
                query,
            ],
            runner=runner,
        )
        operations.append({"name": f"read_{name}", **readback})
        if readback["status"] == "SUCCEEDED":
            actual_state[name] = _json_list_or_empty(readback.get("stdout") or "")
        else:
            result["status"] = "FAILED"
            return result

    evidence_query = _evidence_query(plan)
    evidence = _run_command(
        [
            _bq_executable(),
            f"--project_id={env.project_id or project}",
            f"--location={location}",
            "--format=json",
            "query",
            "--use_legacy_sql=false",
            evidence_query,
        ],
        runner=runner,
    )
    operations.append({"name": "read_governance_evidence", **evidence})
    if evidence["status"] == "SUCCEEDED":
        actual_state["governance_evidence"] = _json_list_or_empty(evidence.get("stdout") or "")
    else:
        result["status"] = "FAILED"
        return result

    comparisons = _compare_expected_to_actual(governance_ledger_plan(semantic, env)["actions"], actual_state)
    result["actual_state"] = _redact(actual_state)
    result["comparisons"] = comparisons
    result["summary"] = _summary(comparisons)
    result["status"] = "SUCCEEDED" if not any(item["state"] in {"missing_intent", "mismatch"} for item in comparisons) else "FAILED"
    result["review_boundary"] = (
        "This command performs non-mutating BigQuery governance reconciliation. "
        "It reads native state and ContractForge governance evidence, but does not auto-repair or delete policies."
    )
    return result


def governance_reconciliation_plan(contract: SemanticContract, environment: GCPEnvironment) -> dict[str, Any]:
    project = target_project(contract, environment) or environment.project_id or "${project_id}"
    dataset = target_dataset(contract, environment)
    table = contract.target.name
    ledger = governance_ledger_plan(contract, environment)
    expected_actions = [_redact(action) for action in ledger["actions"]]
    return {
        "kind": "contractforge.gcp.bigquery_governance_reconciliation_plan.v1",
        "adapter": "contractforge-gcp",
        "subtarget": "gcp_bigquery",
        "maturity_gate": "GCP-BQ-17B2",
        "target": target_table_id(contract, environment),
        "status": "PLANNED_REVIEW_REQUIRED",
        "execution_included": True,
        "evidence": {
            "dataset": evidence_dataset(contract, environment),
            "table": "contractforge_governance_evidence",
            "table_ref": f"{table_prefix(environment.project_id, evidence_dataset(contract, environment))}.contractforge_governance_evidence",
        },
        "expected_state": {
            "source": "contract_governance_ledger_plan",
            "action_count": len(expected_actions),
            "actions": expected_actions,
        },
        "actual_state_readback": _readback_plan(project=project, dataset=dataset, table=table),
        "reconciliation_rules": [
            {
                "state": "in_sync",
                "meaning": "Declared contract intent matches native BigQuery readback for the same surface and subject.",
            },
            {
                "state": "missing_intent",
                "meaning": "A required row policy, description, policy tag, data policy or grant is absent from native readback.",
            },
            {
                "state": "unmanaged_actual",
                "meaning": "Native BigQuery contains a governance object that is not declared by the contract.",
            },
            {
                "state": "mismatch",
                "meaning": "Native BigQuery contains the declared subject but the expression, tag, description or grantee differs.",
            },
            {
                "state": "retained_on_overwrite",
                "meaning": "A replace/overwrite operation preserved governance state and must be accepted or explicitly reapplied.",
            },
            {
                "state": "requires_review",
                "meaning": "The surface depends on IAM, regional policy-tag taxonomy, tag-based masking or platform behavior not yet certified.",
            },
        ],
        "matching_keys": {
            "bigquery_row_access_policy": ["policy_name", "filter_expression", "grantee_list"],
            "bigquery_data_policy": ["column_name", "data_policy_name", "masking_expression", "grantee_list"],
            "data_catalog_policy_tag": ["column_name", "policy_tag_resource"],
            "bigquery_description": ["scope", "column_name", "description"],
            "bigquery_iam": ["principal", "role_or_privilege"],
            "knowledge_catalog_or_dataplex_aspect": ["entry", "aspect_type", "aspect_payload_hash"],
        },
        "review_boundaries": [
            "This artifact and command path are non-mutating and only read native state plus ContractForge evidence.",
            "They do not auto-apply, repair or delete policies, grants, descriptions, tags or aspects.",
            "Security-object apply/enforcement remains validated by the dedicated governance smokes.",
        ],
        "sources": [
            "https://docs.cloud.google.com/bigquery/docs/tables",
            "https://docs.cloud.google.com/bigquery/docs/information-schema-column-field-paths",
            "https://docs.cloud.google.com/bigquery/docs/row-level-security-intro",
            "https://docs.cloud.google.com/bigquery/docs/column-level-security-intro",
            "https://docs.cloud.google.com/bigquery/docs/access-control",
        ],
    }


def _readback_plan(*, project: str, dataset: str, table: str) -> dict[str, Any]:
    table_filter = _sql_string(table)
    table_ref = f"{project}.{dataset}.{table}"
    return {
        "mode": "non_mutating_readback",
        "queries": {
            "row_access_policies": (
                f"SELECT * FROM `{project}.{dataset}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES` "
                f"WHERE table_name = {table_filter};"
            ),
            "table_descriptions": (
                f"SELECT option_name, option_value FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLE_OPTIONS` "
                f"WHERE table_name = {table_filter} AND option_name = 'description';"
            ),
            "column_descriptions_and_policy_tags": (
                f"SELECT column_name, field_path, data_type, description, policy_tags "
                f"FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` "
                f"WHERE table_name = {table_filter};"
            ),
            "column_policy_tags": (
                f"SELECT column_name, data_type, policy_tags FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMNS` "
                f"WHERE table_name = {table_filter};"
            ),
        },
        "api_readbacks": {
            "table_iam_policy": {
                "method": "tables.getIamPolicy",
                "resource": f"projects/{project}/datasets/{dataset}/tables/{table}",
                "purpose": "Read table-level grants for comparison with contract access grants.",
            },
            "row_access_policies": {
                "method": "rowAccessPolicies.list",
                "resource": f"projects/{project}/datasets/{dataset}/tables/{table}/rowAccessPolicies",
                "purpose": "Read policy grantees and filters when INFORMATION_SCHEMA is insufficient for IAM details.",
            },
            "data_policies": {
                "method": "dataPolicies.list",
                "parent": f"projects/{project}",
                "purpose": f"Read BigQuery data policies before matching column masking policies to {table_ref}.",
            },
        },
        "bq_command_templates": {
            name: f"bq --project_id={project} --format=json query --use_legacy_sql=false {json.dumps(query)}"
            for name, query in {
                "row_access_policies": (
                    f"SELECT * FROM `{project}.{dataset}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES` "
                    f"WHERE table_name = {table_filter};"
                ),
                "column_descriptions_and_policy_tags": (
                    f"SELECT column_name, field_path, data_type, description, policy_tags "
                    f"FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` "
                    f"WHERE table_name = {table_filter};"
                ),
            }.items()
        },
        "target_table": table_ref,
    }


def _coerce_environment(environment: GCPEnvironment | dict[str, Any] | None) -> GCPEnvironment:
    if isinstance(environment, GCPEnvironment):
        return environment
    if isinstance(environment, dict):
        return GCPEnvironment.from_contract(environment)
    return GCPEnvironment()


def _target_parts(contract: SemanticContract, environment: GCPEnvironment) -> tuple[str, str, str]:
    project = target_project(contract, environment) or environment.project_id
    dataset = target_dataset(contract, environment)
    table = contract.target.name
    if not project or not dataset or not table:
        raise ValueError("Governance reconciliation requires project, dataset and table target binding.")
    return project, dataset, table


def _readback_queries(*, project: str, dataset: str, table: str) -> dict[str, str]:
    table_filter = _sql_string(table)
    return {
        "table_descriptions": (
            f"SELECT table_name, option_name, option_value FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLE_OPTIONS` "
            f"WHERE table_name = {table_filter} AND option_name = 'description'"
        ),
        "column_descriptions_and_policy_tags": (
            f"SELECT column_name, field_path, data_type, description, policy_tags "
            f"FROM `{project}.{dataset}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` "
            f"WHERE table_name = {table_filter}"
        ),
    }


def _evidence_query(plan: dict[str, Any]) -> str:
    table_ref = str(plan["evidence"]["table_ref"])
    target = _sql_string(str(plan["target"]))
    return (
        "SELECT governance_surface, operation, subject, status, COUNT(*) AS row_count "
        f"FROM `{table_ref}` WHERE target_table = {target} "
        "GROUP BY governance_surface, operation, subject, status "
        "ORDER BY governance_surface, operation, subject, status"
    )


def _compare_expected_to_actual(expected_actions: list[dict[str, Any]], actual_state: dict[str, Any]) -> list[dict[str, Any]]:
    comparisons = []
    for action in expected_actions:
        surface = action["surface"]
        if surface == "bigquery_row_access_policy":
            comparisons.append(_compare_row_access(action, actual_state))
        elif surface == "bigquery_data_policy":
            comparisons.append(_compare_data_policy(action, actual_state))
        elif surface == "data_catalog_policy_tag":
            comparisons.append(_compare_policy_tag(action, actual_state))
        elif surface == "bigquery_description":
            comparisons.append(_compare_description(action, actual_state))
        elif surface == "bigquery_iam":
            comparisons.append(_requires_review(action, "IAM grant reconciliation needs table IAM policy readback and least-privilege role mapping."))
        elif surface == "knowledge_catalog_or_dataplex_aspect":
            comparisons.append(_requires_review(action, "Dataplex/Knowledge Catalog aspect reconciliation remains explicit-command scoped."))
        else:
            comparisons.append(_requires_review(action, "Unknown governance surface."))
    return [_with_evidence_count(item, actual_state) for item in comparisons]


def _compare_row_access(action: dict[str, Any], actual_state: dict[str, Any]) -> dict[str, Any]:
    expected_name = str(action.get("name") or "")
    policies = actual_state.get("row_access_policies") or []
    actual = next(
        (
            item
            for item in policies
            if str(item.get("rowAccessPolicyReference", {}).get("policyId") or item.get("policyId") or "") == expected_name
        ),
        None,
    )
    if not actual:
        return _comparison(action, "missing_intent", actual=None)
    expected_filter = _normalize_expression(str(action.get("filter_expression") or ""))
    actual_filter = _normalize_expression(str(actual.get("filterPredicate") or actual.get("filter_predicate") or ""))
    expected_principals = set(action.get("principals") or [])
    actual_principals = set(actual.get("grantees") or [])
    state = "in_sync"
    if expected_filter and expected_filter != actual_filter:
        state = "mismatch"
    elif expected_principals and not expected_principals.issubset(actual_principals):
        state = "mismatch"
    return _comparison(action, state, actual=actual)


def _compare_data_policy(action: dict[str, Any], actual_state: dict[str, Any]) -> dict[str, Any]:
    column = str(action.get("column") or "")
    metadata = actual_state.get("table_metadata") or {}
    field = _schema_field(metadata, column)
    policies = field.get("dataPolicies") if isinstance(field, dict) else None
    if not policies:
        return _comparison(action, "missing_intent", actual=field)
    expected_function = str(action.get("function") or "")
    if expected_function.startswith("projects/") and not any(item.get("name") == expected_function for item in policies):
        return _comparison(action, "mismatch", actual=field)
    return _comparison(action, "in_sync", actual=field)


def _compare_policy_tag(action: dict[str, Any], actual_state: dict[str, Any]) -> dict[str, Any]:
    column = str(action.get("column") or action.get("column_name") or "")
    expected = str(action.get("policy_tag") or "").removeprefix("policy_tag:")
    metadata = actual_state.get("table_metadata") or {}
    field = _schema_field(metadata, column)
    names = []
    if isinstance(field, dict):
        names = list((field.get("policyTags") or {}).get("names") or [])
    if not names:
        for row in actual_state.get("column_descriptions_and_policy_tags") or []:
            if row.get("column_name") == column:
                names = list(row.get("policy_tags") or [])
                break
    if not any(_policy_tag_matches(expected, name) for name in names):
        return _comparison(action, "missing_intent" if not names else "mismatch", actual={"policy_tags": names})
    return _comparison(action, "in_sync", actual={"policy_tags": names})


def _compare_description(action: dict[str, Any], actual_state: dict[str, Any]) -> dict[str, Any]:
    scope = str(action.get("scope") or "")
    expected = str(action.get("value") or "")
    if scope == "table":
        rows = actual_state.get("table_descriptions") or []
        actual_value = _unquote_bigquery_option(str(rows[0].get("option_value") or "")) if rows else ""
        return _comparison(action, "in_sync" if actual_value == expected else "missing_intent", actual={"description": actual_value})
    column = str(action.get("column") or "")
    for row in actual_state.get("column_descriptions_and_policy_tags") or []:
        if row.get("column_name") == column:
            actual_value = str(row.get("description") or "")
            return _comparison(action, "in_sync" if actual_value == expected else "missing_intent", actual=row)
    return _comparison(action, "missing_intent", actual=None)


def _requires_review(action: dict[str, Any], reason: str) -> dict[str, Any]:
    item = _comparison(action, "requires_review", actual=None)
    item["reason"] = reason
    return item


def _comparison(action: dict[str, Any], state: str, *, actual: Any) -> dict[str, Any]:
    return {
        "surface": action.get("surface"),
        "operation": action.get("operation"),
        "subject": action.get("name") or action.get("column") or action.get("scope") or action.get("principal"),
        "state": state,
        "expected": _redact(action),
        "actual": _redact(actual),
    }


def _with_evidence_count(item: dict[str, Any], actual_state: dict[str, Any]) -> dict[str, Any]:
    surface = item.get("surface")
    count = 0
    for row in actual_state.get("governance_evidence") or []:
        if row.get("governance_surface") == surface:
            try:
                count += int(row.get("row_count") or 0)
            except ValueError:
                pass
    item["governance_evidence_rows"] = count
    if item["state"] == "in_sync" and count == 0:
        item["state"] = "missing_evidence"
    return item


def _summary(comparisons: list[dict[str, Any]]) -> dict[str, int]:
    states: dict[str, int] = {}
    for item in comparisons:
        states[item["state"]] = states.get(item["state"], 0) + 1
    states["total"] = len(comparisons)
    return states


def _schema_field(metadata: dict[str, Any], column: str) -> dict[str, Any]:
    for field in (metadata.get("schema") or {}).get("fields") or []:
        if field.get("name") == column:
            return dict(field)
    return {}


def _normalize_expression(value: str) -> str:
    return " ".join(value.replace('"', "'").split()).lower()


def _policy_tag_matches(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    return expected.split("/policyTags/")[-1] == actual.split("/policyTags/")[-1]


def _unquote_bigquery_option(value: str) -> str:
    try:
        loaded = json.loads(value)
        return str(loaded)
    except json.JSONDecodeError:
        return value


def _json_object(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_list_or_empty(value: str) -> list[dict[str, Any]]:
    text = value.strip()
    if not text or text.startswith("No row access policies found"):
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _bq_executable() -> str:
    return shutil.which("bq") or shutil.which("bq.cmd") or "bq"


def _run_command(command: list[str], *, runner: Any | None = None) -> dict[str, Any]:
    completed = runner(command, text=True, capture_output=True) if runner else subprocess.run(command, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "SUCCEEDED" if completed.returncode == 0 else "FAILED",
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _redact(value: Any) -> Any:
    redacted = redact_value(value)
    if isinstance(redacted, dict):
        return {key: _redact(item) for key, item in redacted.items()}
    if isinstance(redacted, list):
        return [_redact(item) for item in redacted]
    if isinstance(redacted, tuple):
        return tuple(_redact(item) for item in redacted)
    if isinstance(redacted, str):
        return re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "REDACTED_EMAIL", redacted)
    return redacted


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
