"""Bundle Databricks adapter artifacts."""

from __future__ import annotations

import json
from datetime import datetime

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.planner import PlanningResult
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.annotations import render_annotations_audit_insert_sql, render_annotations_sql
from contractforge_databricks.bundles import DatabricksJobSpec, render_databricks_asset_bundle
from contractforge_databricks.capabilities.models import DatabricksCapabilities
from contractforge_databricks.cost import render_operational_cost_query
from contractforge_databricks.diagnostics import render_create_explain_table_sql
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.evidence import render_create_evidence_tables_sql, render_evidence_table_notes
from contractforge_databricks.governance import render_access_audit_insert_sql, render_governance_sql
from contractforge_databricks.lakeflow import evaluate_lakeflow_compatibility, render_lakeflow_review
from contractforge_databricks.lineage import render_openlineage_insert_sql
from contractforge_databricks.operations import render_operations_insert_sql, render_operations_json
from contractforge_databricks.quality import render_quality_check_sql
from contractforge_databricks.rendering.markdown import render_review_markdown
from contractforge_databricks.rendering.names import artifact_prefix, bundle_name, job_name, task_key
from contractforge_databricks.schema import plan_schema_policy
from contractforge_databricks.shapes import render_shape_sql
from contractforge_databricks.sources import (
    custom_transform_notebook_task,
    render_source_artifacts,
    render_source_metadata_json,
)
from contractforge_databricks.state import render_control_table_migrations_sql, render_create_state_tables_sql
from contractforge_databricks.transforms import render_transform_sql
from contractforge_databricks.write_modes import choose_write_strategy, render_write_mode_sql_notes


def render_databricks_artifacts(
    contract: SemanticContract,
    planning: PlanningResult,
    capabilities: DatabricksCapabilities,
    *,
    environment: DatabricksEnvironment | None = None,
) -> RenderedArtifacts:
    env = environment or DatabricksEnvironment()
    prefix = artifact_prefix(contract)
    artifacts = {
        f"{prefix}.review.md": render_review_markdown(contract, planning, capabilities),
        f"{prefix}.capabilities.json": json.dumps(capabilities.as_dict(), indent=2, sort_keys=True),
        f"{prefix}.write_mode.sql": render_write_mode_sql_notes(contract),
        f"{prefix}.shape.sql": render_shape_sql(contract),
        f"{prefix}.transform.sql": render_transform_sql(contract),
        f"{prefix}.annotations.sql": render_annotations_sql(contract),
        f"{prefix}.annotations_audit.sql": render_annotations_audit_insert_sql(contract, catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.governance.sql": render_governance_sql(contract),
        f"{prefix}.access_audit.sql": render_access_audit_insert_sql(contract, catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.quality.sql": render_quality_check_sql(contract),
        f"{prefix}.schema_policy.json": json.dumps(plan_schema_policy(contract).as_dict(), indent=2, sort_keys=True),
        f"{prefix}.source_metadata.json": render_source_metadata_json(contract),
        f"{prefix}.evidence.sql": render_evidence_table_notes(catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.evidence_ddl.sql": render_create_evidence_tables_sql(catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.state_ddl.sql": render_create_state_tables_sql(catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.control_table_migrations.sql": render_control_table_migrations_sql(catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.openlineage.sql": _render_openlineage_template(contract, env),
        f"{prefix}.operations.json": render_operations_json(contract),
        f"{prefix}.operations.sql": render_operations_insert_sql(contract, catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.diagnostics_ddl.sql": render_create_explain_table_sql(catalog=env.evidence_catalog, schema=env.evidence_schema),
        f"{prefix}.cost.sql": render_operational_cost_query(catalog=env.evidence_catalog, schema=env.evidence_schema),
    }
    strategy = choose_write_strategy(contract, capabilities)
    artifacts[f"{prefix}.strategy.json"] = json.dumps(strategy.as_dict(), indent=2, sort_keys=True)
    if capabilities.status("lakeflow_auto_cdc") != "unsupported":
        compatibility = evaluate_lakeflow_compatibility(contract)
        artifacts[f"{prefix}.lakeflow.md"] = render_lakeflow_review(compatibility)
    artifacts.update(render_source_artifacts(contract, environment=env))
    pre_tasks = tuple(
        task
        for task in (custom_transform_notebook_task(contract, artifact_prefix=prefix),)
        if task is not None
    )
    artifacts[f"{prefix}.databricks.yml"] = render_databricks_asset_bundle(
        DatabricksJobSpec(
            bundle_name=bundle_name(contract),
            job_name=job_name(contract),
            task_key=task_key(contract),
            notebook_path=f"{env.workspace_path}/{prefix}/run",
            target=env.bundle_target,
            pre_tasks=pre_tasks,
        )
    )
    return RenderedArtifacts(artifacts=artifacts)


def _render_openlineage_template(contract: SemanticContract, env: DatabricksEnvironment) -> str:
    return render_openlineage_insert_sql(
        contract,
        run_id="${run_id}",
        source_name=contract.source.name,
        status="SUCCESS",
        started_at_utc=datetime(1970, 1, 1, 0, 0, 0),
        finished_at_utc=datetime(1970, 1, 1, 0, 0, 0),
        catalog=env.evidence_catalog,
        schema=env.evidence_schema,
    )
