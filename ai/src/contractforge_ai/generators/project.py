"""Project scaffold generation."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable, Mapping
from typing import Any

import yaml
from contractforge_ai.integrations.contractforge_naming import (
    derive_names,
    normalize_identifier,
    normalize_naming_config,
)

from contractforge_ai.generators.contract import generate_contract_draft
from contractforge_ai.generators.environments import (
    aws_glue_iceberg_environment_payload,
    databricks_environment_payload,
    fabric_lakehouse_environment_payload,
    gcp_bigquery_environment_payload,
    snowflake_sql_warehouse_environment_payload,
)
from contractforge_ai.generators.targets import supported_project_targets
from contractforge_ai.models import Assumption, EvidenceItem, RequiredDecision, Traceability, ValidationResult
from contractforge_ai.projects import DecisionReport, ProjectArtifact, ProjectPlan
from contractforge_ai.validation import validate_with_contractforge

ProjectGenerator = Callable[..., ProjectPlan]


def generate_contractforge_yaml_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    include_project_artifacts: bool = True,
    connection_name: str = "source",
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a reviewable ContractForge YAML project scaffold."""

    draft = generate_contract_draft(
        schema_path,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
    )
    contract = dict(draft.contract)
    names = _derive_project_names(
        project_name=project_name,
        target_table=target_table,
        layer=layer,
        naming=naming,
    )
    if naming is not None:
        contract["naming"] = _naming_payload(naming)
    annotations = contract.pop("annotations", {"table": {}, "columns": {}})
    operations = contract.pop("operations", {})
    connection_path = f"connections/{normalize_identifier(connection_name)}.yaml"
    contract, connection = _contract_with_connection_reference(
        contract,
        connector=connector,
        connection_path=connection_path,
    )

    base = names.logical_name
    contract_name = names.contract_basename
    project_contract_path = f"contracts/{layer}/{contract_name}.ingestion.yaml"
    project_artifacts = [
        ProjectArtifact(
            path="project.yaml",
            kind="config",
            description="ContractForge project metadata with environments, reusable connection and execution order.",
            content=_project_yaml(
                project_name=base,
                environment_path="environments/review.environment.yaml",
                connection_path=connection_path,
                contract_path=project_contract_path,
                step_name=f"{layer}_{contract_name}",
                schedule_cron=schedule_cron,
                schedule_timezone=schedule_timezone,
                schedule_enabled=schedule_enabled,
            ),
        ),
        ProjectArtifact(
            path="environments/review.environment.yaml",
            kind="config",
            description="Review environment contract. Choose the real adapter before deployment.",
            content=_yaml(_review_environment_payload()),
        ),
    ] if include_project_artifacts else []
    artifacts = [
        *project_artifacts,
        ProjectArtifact(
            path=connection_path,
            kind="config",
            description="Reusable source connection draft inherited by ingestion contracts.",
            content=_yaml(connection),
        ),
        ProjectArtifact(
            path=project_contract_path,
            kind="contract",
            description="ContractForge ingestion contract draft.",
            content=_yaml(contract),
        ),
        ProjectArtifact(
            path=f"contracts/{layer}/{contract_name}.annotations.yaml",
            kind="annotation",
            description="ContractForge annotations draft.",
            content=_yaml(_contract_file("annotations", annotations)),
        ),
        ProjectArtifact(
            path=f"contracts/{layer}/{contract_name}.operations.yaml",
            kind="operation",
            description="ContractForge operations draft.",
            content=_yaml(_contract_file("operations", operations)),
        ),
        ProjectArtifact(
            path="DECISIONS.md",
            kind="markdown",
            description="Review checklist and required decisions.",
            content=_decisions_markdown(project_name, draft.assumptions, draft.decisions_required, draft.warnings),
        ),
        ProjectArtifact(
            path="RUNBOOK.md",
            kind="markdown",
            description="Operational runbook for the generated ContractForge project.",
            content=_runbook_markdown(
                project_name=project_name,
                target="ContractForge YAML",
                purpose="Execute a reviewed ContractForge ingestion contract.",
                entrypoints=[f"`contracts/{layer}/{contract_name}.ingestion.yaml`"],
                validation_commands=["contractforge validate contracts"],
                review_notes=[
                    "Confirm connector options and runtime dependencies.",
                    "Confirm quality rules, annotations and operations metadata with data owners.",
                    "Use ContractForge dry-run or validation before scheduling production execution.",
                ],
            ),
        ),
        ProjectArtifact(
            path="VALIDATION.md",
            kind="markdown",
            description="Generated contract validation report.",
            content=_validation_markdown(
                project_name=project_name,
                contract_path=project_contract_path,
                deterministic=draft.validation,
                contractforge=validate_with_contractforge(_resolved_contract_from_connection(contract, connection)),
            ),
        ),
        ProjectArtifact(
            path="README.md",
            kind="markdown",
            description="Generated project overview.",
            content=_readme_markdown(
                project_name=project_name,
                layer=layer,
                target_catalog=target_catalog,
                target_schema=target_schema,
                target_table=target_table,
                artifacts_base=f"contracts/{layer}/{contract_name}",
                project_yaml=True,
            ),
        ),
    ]

    return ProjectPlan(
        name=base,
        target="contractforge-yaml",
        artifacts=artifacts,
        report=DecisionReport(
            title=f"{project_name} ContractForge YAML Project",
            summary="Generated ContractForge YAML scaffold. Review decisions and placeholders before execution.",
            assumptions=[
                Assumption(statement=assumption, confidence=0.60, review_required=True)
                for assumption in draft.assumptions
            ],
            decisions_required=[
                RequiredDecision(
                    question=decision,
                    reason="Generated ContractForge projects require human review before execution.",
                )
                for decision in draft.decisions_required
            ],
            warnings=draft.warnings,
        ),
        traceability=Traceability(
            confidence=draft.traceability.confidence,
            evidence=[
                EvidenceItem(
                    source="contract_draft",
                    reason="Generated project from deterministic ContractForge contract draft.",
                    value={"source_schema": draft.source_path, "artifacts": len(artifacts)},
                    confidence=draft.traceability.confidence,
                )
            ],
            assumptions=draft.traceability.assumptions,
            decisions_required=draft.traceability.decisions_required,
            review_required=True,
        ),
    )


def generate_databricks_dab_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    compute: dict[str, Any] | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a reviewable Databricks Asset Bundle scaffold for ContractForge."""

    contract_plan = generate_contractforge_yaml_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
    )
    names = _derive_project_names(
        project_name=project_name,
        target_table=target_table,
        layer=layer,
        naming=naming,
    )
    bundle_name = names.bundle_name
    table_name = names.contract_basename
    job_resource_key = normalize_identifier(names.job_name)
    contract_path = f"contracts/{layer}/{table_name}.ingestion.yaml"
    notebook_path = f"notebooks/run_{layer}_{table_name}.py"

    contract_artifacts = [
        artifact
        for artifact in contract_plan.artifacts
        if _is_contractforge_project_artifact(artifact)
    ]
    contract_artifacts = _with_adapter_project_environment(
        contract_artifacts,
        adapter="databricks",
        environment_path="environments/databricks.environment.yaml",
        environment_payload=databricks_environment_payload(catalog=target_catalog),
    )
    artifacts = [
        ProjectArtifact(
            path="databricks.yml",
            kind="config",
            description="Databricks Asset Bundle root configuration.",
            content=_databricks_yml(bundle_name, compute=compute),
        ),
        ProjectArtifact(
            path="resources/jobs.yml",
            kind="resource",
            description="Databricks job resource for ContractForge execution.",
            content=_dab_jobs_yml(job_resource_key, names.job_name, names.task_key, notebook_path, compute=compute),
        ),
        ProjectArtifact(
            path=notebook_path,
            kind="notebook",
            description="Notebook task that loads and executes the generated ContractForge contract.",
            content=_dab_notebook(contract_path),
        ),
        *contract_artifacts,
        ProjectArtifact(
            path="DECISIONS.md",
            kind="markdown",
            description="Databricks Asset Bundle review checklist and required decisions.",
            content=_dab_decisions_markdown(project_name, contract_plan.report, compute=compute),
        ),
        ProjectArtifact(
            path="RUNBOOK.md",
            kind="markdown",
            description="Operational runbook for the generated Databricks Asset Bundle.",
            content=_runbook_markdown(
                project_name=project_name,
                target="Databricks Asset Bundle",
                purpose="Deploy and run a ContractForge ingestion job through Databricks Asset Bundles.",
                entrypoints=["`databricks.yml`", "`resources/jobs.yml`", f"`{notebook_path}`", f"`{contract_path}`"],
                validation_commands=["databricks bundle validate", "databricks bundle deploy -t dev", "databricks bundle run <job-name> -t dev"],
                review_notes=[
                    _dab_compute_review_note(compute),
                    "Confirm ContractForge and connector dependencies on the selected Databricks runtime.",
                    "Review run output and ContractForge control tables after the first execution.",
                ],
            ),
        ),
        ProjectArtifact(
            path="VALIDATION.md",
            kind="markdown",
            description="Generated contract validation report.",
            content=_validation_markdown(
                project_name=project_name,
                contract_path=contract_path,
                deterministic=_validation_from_contract_artifacts(contract_artifacts),
                contractforge=validate_with_contractforge(_contract_from_contract_artifacts(contract_artifacts)),
            ),
        ),
        ProjectArtifact(
            path="README.md",
            kind="markdown",
            description="Generated Databricks Asset Bundle overview.",
            content=_dab_readme_markdown(
                project_name=project_name,
                bundle_name=bundle_name,
                notebook_path=notebook_path,
                contract_path=contract_path,
            ),
        ),
    ]

    decisions = [
        *contract_plan.report.decisions_required,
        RequiredDecision(
            question="Confirm bundle workspace root path",
            reason="Workspace paths are environment-specific.",
            path="workspace.root_path",
        ),
    ]
    if not _compute_is_explicit(compute):
        decisions.append(
            RequiredDecision(
                question="Choose Databricks job compute",
                reason="The generated bundle uses an existing_cluster_id placeholder because no compute preference was explicit.",
                path="variables.existing_cluster_id",
                options=["existing_cluster_id", "job_clusters", "serverless job compute"],
            )
        )

    return ProjectPlan(
        name=bundle_name,
        target="databricks-dab",
        artifacts=artifacts,
        report=DecisionReport(
            title=f"{project_name} Databricks Asset Bundle",
            summary="Generated Databricks Asset Bundle scaffold for ContractForge ingestion. Review placeholders before deployment.",
            assumptions=contract_plan.report.assumptions,
            decisions_required=decisions,
            warnings=[
                *contract_plan.report.warnings,
                _dab_compute_warning(compute),
            ],
        ),
        traceability=Traceability(
            confidence=contract_plan.traceability.confidence,
            evidence=[
                EvidenceItem(
                    source="contractforge_yaml_project",
                    reason="Generated DAB scaffold from deterministic ContractForge YAML project plan.",
                    value={"artifacts": len(artifacts), "contract_path": contract_path},
                    confidence=contract_plan.traceability.confidence,
                )
            ],
            assumptions=contract_plan.traceability.assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def generate_aws_glue_iceberg_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a reviewable AWS Glue Spark + Iceberg scaffold for ContractForge."""

    contract_plan = generate_contractforge_yaml_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        include_project_artifacts=False,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
    )
    names = _derive_project_names(
        project_name=project_name,
        target_table=target_table,
        layer=layer,
        naming=naming,
    )
    project_slug = names.logical_name
    contract_name = names.contract_basename
    step_name = f"{layer}_{contract_name}"
    contract_path = f"contracts/aws/{layer}/{contract_name}/{contract_name}.ingestion.yaml"
    contract_artifacts = _relocate_split_contract_artifacts(
        contract_plan.artifacts,
        layer=layer,
        contract_name=contract_name,
        adapter="aws",
    )

    artifacts = [
        ProjectArtifact(
            path="project.yaml",
            kind="config",
            description="ContractForge project metadata for AWS adapter deployment.",
            content=_adapter_project_yaml(
                project_name=project_slug,
                adapter="aws",
                environment_path="environments/aws.environment.yaml",
                connection_path="connections/source.yaml",
                contract_path=contract_path,
                step_name=step_name,
                schedule_cron=schedule_cron,
                schedule_timezone=schedule_timezone,
                schedule_enabled=schedule_enabled,
            ),
        ),
        ProjectArtifact(
            path="environments/aws.environment.yaml",
            kind="config",
            description="AWS environment contract scaffold. Fill S3, Glue and IAM values before deploy.",
            content=_yaml(aws_glue_iceberg_environment_payload(project_slug)),
        ),
        *contract_artifacts,
        ProjectArtifact(
            path="DECISIONS.md",
            kind="markdown",
            description="AWS Glue Iceberg review checklist and required decisions.",
            content=_aws_decisions_markdown(project_name, contract_plan.report),
        ),
        ProjectArtifact(
            path="RUNBOOK.md",
            kind="markdown",
            description="Operational runbook for the generated AWS Glue Iceberg project.",
            content=_runbook_markdown(
                project_name=project_name,
                target="AWS Glue Spark + Iceberg",
                purpose="Deploy and run a ContractForge ingestion job through the AWS adapter runtime.",
                entrypoints=["`project.yaml`", "`environments/aws.environment.yaml`", f"`{contract_path}`"],
                validation_commands=[
                    "contractforge-ai validate-project-structure . --adapter aws",
                    f"contractforge-aws plan {contract_path} --environment environments/aws.environment.yaml",
                    f"contractforge-aws deploy {contract_path} --environment environments/aws.environment.yaml --dry-run",
                ],
                review_notes=[
                    "Fill `environment.artifacts.uri` with the S3 prefix where ContractForge should publish runtime artifacts.",
                    "Fill AWS Glue IAM role, Iceberg warehouse and package dependency locations before deployment.",
                    "Use the adapter deploy command so contracts are published and the stable AWS runtime runner is registered without generated per-contract logic.",
                    "Review AWS planner warnings before allowing any REVIEW_REQUIRED semantics into production.",
                ],
            ),
        ),
        ProjectArtifact(
            path="VALIDATION.md",
            kind="markdown",
            description="Generated contract validation report.",
            content=_validation_markdown(
                project_name=project_name,
                contract_path=contract_path,
                deterministic=_validation_from_contract_artifacts(contract_artifacts),
                contractforge=validate_with_contractforge(_contract_from_contract_artifacts(contract_artifacts)),
            ),
        ),
        ProjectArtifact(
            path="README.md",
            kind="markdown",
            description="Generated AWS Glue Iceberg project overview.",
            content=_aws_readme_markdown(
                project_name=project_name,
                project_slug=project_slug,
                contract_path=contract_path,
            ),
        ),
    ]

    decisions = [
        *contract_plan.report.decisions_required,
        RequiredDecision(
            question="Choose the AWS artifact S3 prefix.",
            reason="The AWS adapter publishes contracts, normalized runtime inputs and the stable Glue runner to this prefix.",
            path="environments/aws.environment.yaml.artifacts.uri",
        ),
        RequiredDecision(
            question="Choose the AWS Glue execution role.",
            reason="The generated environment cannot infer IAM role ARN safely.",
            path="environments/aws.environment.yaml.parameters.aws.glue_job.role_arn",
        ),
        RequiredDecision(
            question="Choose the Iceberg warehouse S3 prefix.",
            reason="Iceberg table data and metadata storage is environment-specific.",
            path="environments/aws.environment.yaml.parameters.aws.iceberg.warehouse",
        ),
    ]

    return ProjectPlan(
        name=project_slug,
        target="aws-glue-iceberg",
        artifacts=artifacts,
        report=DecisionReport(
            title=f"{project_name} AWS Glue Iceberg Project",
            summary="Generated AWS Glue Spark and Iceberg scaffold for ContractForge ingestion. Review AWS environment placeholders before deployment.",
            assumptions=contract_plan.report.assumptions,
            decisions_required=decisions,
            warnings=[
                *contract_plan.report.warnings,
                "AWS deployment uses the adapter runtime library path; generated Glue scripts remain review artifacts.",
            ],
        ),
        traceability=Traceability(
            confidence=contract_plan.traceability.confidence,
            evidence=[
                EvidenceItem(
                    source="contractforge_yaml_project",
                    reason="Generated AWS scaffold from deterministic ContractForge YAML project plan.",
                    value={"artifacts": len(artifacts), "contract_path": contract_path},
                    confidence=contract_plan.traceability.confidence,
                )
            ],
            assumptions=contract_plan.traceability.assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def generate_snowflake_sql_warehouse_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a reviewable Snowflake SQL warehouse scaffold for ContractForge."""

    return _generate_adapter_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
        adapter="snowflake",
        target="snowflake-sql-warehouse",
        display_name="Snowflake SQL Warehouse",
        environment_payload_factory=snowflake_sql_warehouse_environment_payload,
        validation_commands=[
            "contractforge-ai validate-project-structure . --adapter snowflake",
            "contractforge-snowflake plan <contract-path> --environment environments/snowflake.environment.yaml",
            "contractforge-snowflake render <contract-path> --environment environments/snowflake.environment.yaml --output-dir rendered",
        ],
        review_notes=[
            "Fill Snowflake warehouse, role, database, schema and artifact stage values before deployment.",
            "Run the Snowflake adapter planner and review any REVIEW_REQUIRED write-mode, source or governance findings.",
            "Use the adapter project deployment path so contracts and runtime artifacts stay tied to deterministic evidence.",
        ],
        extra_decisions=[
            RequiredDecision(
                question="Choose the Snowflake artifact stage.",
                reason="The Snowflake adapter publishes contract and runtime artifacts to a reviewed stage location.",
                path="environments/snowflake.environment.yaml.artifacts.stage",
            ),
            RequiredDecision(
                question="Confirm Snowflake warehouse, role, database and schema.",
                reason="These values control runtime execution and cannot be inferred safely.",
                path="environments/snowflake.environment.yaml.parameters.snowflake",
            ),
        ],
    )


def generate_fabric_lakehouse_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a reviewable Microsoft Fabric Lakehouse scaffold for ContractForge."""

    return _generate_adapter_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
        adapter="fabric",
        target="fabric-lakehouse",
        display_name="Microsoft Fabric Lakehouse",
        environment_payload_factory=fabric_lakehouse_environment_payload,
        validation_commands=[
            "contractforge-ai validate-project-structure . --adapter fabric",
            "contractforge-fabric plan <contract-path> --environment environments/fabric.environment.yaml",
            "contractforge-fabric render <contract-path> --environment environments/fabric.environment.yaml",
        ],
        review_notes=[
            "Fill Fabric workspace and Lakehouse identifiers before execution.",
            "Run the Fabric adapter planner and review notebook/runtime limitations before deployment.",
            "Keep Lakehouse, shortcut, Kafka and governance decisions in environment or adapter review artifacts, not hidden in generated contracts.",
        ],
        extra_decisions=[
            RequiredDecision(
                question="Choose the Fabric workspace and Lakehouse.",
                reason="The generated environment cannot infer tenant workspace or Lakehouse IDs safely.",
                path="environments/fabric.environment.yaml.parameters.fabric",
            ),
            RequiredDecision(
                question="Confirm Fabric capacity and execution queue availability.",
                reason="Fabric runtime behavior depends on capacity state and queueing limits.",
                path="environments/fabric.environment.yaml.runtime",
            ),
        ],
    )


def generate_gcp_bigquery_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a reviewable GCP BigQuery scaffold for ContractForge."""

    return _generate_adapter_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
        adapter="gcp",
        target="gcp-bigquery",
        display_name="GCP BigQuery",
        environment_payload_factory=gcp_bigquery_environment_payload,
        validation_commands=[
            "contractforge-ai validate-project-structure . --adapter gcp",
            "contractforge-gcp plan <contract-path> --environment environments/gcp.environment.yaml",
            "contractforge-gcp render <contract-path> --environment environments/gcp.environment.yaml --output-dir rendered",
        ],
        review_notes=[
            "Fill GCP project, location and staging bucket values before deployment.",
            "Run the GCP adapter planner and review BigQuery governance, policy tag and row-policy findings.",
            "Keep GCS staging and BigQuery dataset decisions in environment or adapter review artifacts.",
        ],
        extra_decisions=[
            RequiredDecision(
                question="Choose the GCP project, location and staging bucket.",
                reason="The generated environment cannot infer cloud project or staging storage safely.",
                path="environments/gcp.environment.yaml.parameters.gcp",
            ),
            RequiredDecision(
                question="Confirm BigQuery governance resources.",
                reason="Policy tags, row access policies and masks require environment-specific IAM/governance setup.",
                path="environments/gcp.environment.yaml.governance",
            ),
        ],
    )


def _generate_adapter_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str,
    mode: str | None,
    owner: str | None,
    naming: Any | None,
    schedule_cron: str,
    schedule_timezone: str,
    schedule_enabled: bool,
    adapter: str,
    target: str,
    display_name: str,
    environment_payload_factory: Callable[[str], dict[str, Any]],
    validation_commands: list[str],
    review_notes: list[str],
    extra_decisions: list[RequiredDecision],
) -> ProjectPlan:
    contract_plan = generate_contractforge_yaml_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        include_project_artifacts=False,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
    )
    names = _derive_project_names(
        project_name=project_name,
        target_table=target_table,
        layer=layer,
        naming=naming,
    )
    project_slug = names.logical_name
    contract_name = names.contract_basename
    step_name = f"{layer}_{contract_name}"
    contract_path = f"contracts/{adapter}/{layer}/{contract_name}/{contract_name}.ingestion.yaml"
    contract_artifacts = _relocate_split_contract_artifacts(
        contract_plan.artifacts,
        layer=layer,
        contract_name=contract_name,
        adapter=adapter,
    )
    validation_commands = [
        command.replace("<contract-path>", contract_path)
        for command in validation_commands
    ]

    artifacts = [
        ProjectArtifact(
            path="project.yaml",
            kind="config",
            description=f"ContractForge project metadata for {display_name} adapter deployment.",
            content=_adapter_project_yaml(
                project_name=project_slug,
                adapter=adapter,
                environment_path=f"environments/{adapter}.environment.yaml",
                connection_path="connections/source.yaml",
                contract_path=contract_path,
                step_name=step_name,
                schedule_cron=schedule_cron,
                schedule_timezone=schedule_timezone,
                schedule_enabled=schedule_enabled,
            ),
        ),
        ProjectArtifact(
            path=f"environments/{adapter}.environment.yaml",
            kind="config",
            description=f"{display_name} environment scaffold. Fill runtime/deployment values before deploy.",
            content=_yaml(environment_payload_factory(project_slug)),
        ),
        *contract_artifacts,
        ProjectArtifact(
            path="DECISIONS.md",
            kind="markdown",
            description=f"{display_name} review checklist and required decisions.",
            content=_adapter_decisions_markdown(project_name, display_name, contract_plan.report, extra_decisions),
        ),
        ProjectArtifact(
            path="RUNBOOK.md",
            kind="markdown",
            description=f"Operational runbook for the generated {display_name} project.",
            content=_runbook_markdown(
                project_name=project_name,
                target=display_name,
                purpose=f"Deploy and run a ContractForge ingestion job through the {display_name} adapter runtime.",
                entrypoints=["`project.yaml`", f"`environments/{adapter}.environment.yaml`", f"`{contract_path}`"],
                validation_commands=validation_commands,
                review_notes=review_notes,
            ),
        ),
        ProjectArtifact(
            path="VALIDATION.md",
            kind="markdown",
            description="Generated contract validation report.",
            content=_validation_markdown(
                project_name=project_name,
                contract_path=contract_path,
                deterministic=_validation_from_contract_artifacts(contract_artifacts),
                contractforge=validate_with_contractforge(_contract_from_contract_artifacts(contract_artifacts)),
            ),
        ),
        ProjectArtifact(
            path="README.md",
            kind="markdown",
            description=f"Generated {display_name} project overview.",
            content=_adapter_readme_markdown(
                project_name=project_name,
                display_name=display_name,
                project_slug=project_slug,
                contract_path=contract_path,
                validation_commands=validation_commands,
            ),
        ),
    ]

    decisions = [
        *contract_plan.report.decisions_required,
        *extra_decisions,
    ]

    return ProjectPlan(
        name=project_slug,
        target=target,
        artifacts=artifacts,
        report=DecisionReport(
            title=f"{project_name} {display_name} Project",
            summary=f"Generated {display_name} scaffold for ContractForge ingestion. Review environment placeholders before deployment.",
            assumptions=contract_plan.report.assumptions,
            decisions_required=decisions,
            warnings=[
                *contract_plan.report.warnings,
                f"{display_name} deployment must pass deterministic adapter planning before execution.",
            ],
        ),
        traceability=Traceability(
            confidence=contract_plan.traceability.confidence,
            evidence=[
                EvidenceItem(
                    source="contractforge_yaml_project",
                    reason=f"Generated {display_name} scaffold from deterministic ContractForge YAML project plan.",
                    value={"artifacts": len(artifacts), "contract_path": contract_path},
                    confidence=contract_plan.traceability.confidence,
                )
            ],
            assumptions=contract_plan.traceability.assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def generate_dbt_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate reviewable dbt source, model and test starter artifacts."""

    draft = generate_contract_draft(
        schema_path,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
    )
    names = _derive_project_names(
        project_name=project_name,
        target_table=target_table,
        layer=layer,
        naming=naming,
    )
    project_slug = names.logical_name
    source_name = normalize_identifier(f"{target_schema}_{layer}")
    table_name = names.contract_basename
    model_name = f"stg_{table_name}"
    columns = _schema_columns(schema_path)
    quality_rules = draft.contract.get("quality_rules", {})
    annotations = draft.contract.get("annotations", {})

    artifacts = [
        ProjectArtifact(
            path="dbt_project.yml",
            kind="config",
            description="dbt project configuration draft.",
            content=_dbt_project_yml(project_slug),
        ),
        ProjectArtifact(
            path="models/sources.yml",
            kind="yaml",
            description="dbt source definition for the ContractForge-managed table.",
            content=_dbt_sources_yml(
                source_name=source_name,
                target_catalog=target_catalog,
                target_schema=target_schema,
                target_table=target_table,
                columns=columns,
                annotations=annotations,
            ),
        ),
        ProjectArtifact(
            path=f"models/staging/{model_name}.sql",
            kind="sql",
            description="dbt staging model draft.",
            content=_dbt_staging_sql(source_name, target_table, columns),
        ),
        ProjectArtifact(
            path=f"models/staging/{model_name}.yml",
            kind="yaml",
            description="dbt model properties and tests draft.",
            content=_dbt_model_yml(model_name=model_name, columns=columns, quality_rules=quality_rules, annotations=annotations),
        ),
        ProjectArtifact(
            path="DECISIONS.md",
            kind="markdown",
            description="dbt review checklist and required decisions.",
            content=_dbt_decisions_markdown(project_name, draft.decisions_required, draft.warnings),
        ),
        ProjectArtifact(
            path="RUNBOOK.md",
            kind="markdown",
            description="Operational runbook for the generated dbt project.",
            content=_runbook_markdown(
                project_name=project_name,
                target="dbt",
                purpose="Build downstream dbt transformations over ContractForge-managed data.",
                entrypoints=["`dbt_project.yml`", "`models/sources.yml`", f"`models/staging/{model_name}.sql`"],
                validation_commands=["dbt parse", "dbt build --select staging"],
                review_notes=[
                    "Replace the dbt profile placeholder before running dbt.",
                    "Confirm adapter-specific database and schema naming.",
                    "Review generated dbt tests before enforcing them in CI.",
                ],
            ),
        ),
        ProjectArtifact(
            path="VALIDATION.md",
            kind="markdown",
            description="Generated contract validation report.",
            content=_validation_markdown(
                project_name=project_name,
                contract_path="ContractForge draft used to derive dbt scaffold",
                deterministic=draft.validation,
                contractforge=validate_with_contractforge(draft.contract),
            ),
        ),
        ProjectArtifact(
            path="README.md",
            kind="markdown",
            description="Generated dbt project overview.",
            content=_dbt_readme_markdown(
                project_name=project_name,
                source_name=source_name,
                target_catalog=target_catalog,
                target_schema=target_schema,
                target_table=target_table,
                model_name=model_name,
            ),
        ),
    ]

    decisions = [
        RequiredDecision(
            question="Confirm dbt profile and target warehouse connection.",
            reason="The generated dbt_project.yml uses a REVIEW_REQUIRED profile placeholder.",
            path="dbt_project.yml.profile",
        ),
        RequiredDecision(
            question="Confirm whether dbt should read the ContractForge target table or a downstream curated table.",
            reason="The scaffold treats the ContractForge target as the dbt source by default.",
            path="models/sources.yml.sources",
        ),
        RequiredDecision(
            question="Review mapped dbt tests before enabling them in CI.",
            reason="ContractForge quality suggestions are evidence-based drafts and may not fully represent business rules.",
            path="models/staging",
        ),
    ]

    return ProjectPlan(
        name=project_slug,
        target="dbt",
        artifacts=artifacts,
        report=DecisionReport(
            title=f"{project_name} dbt Project",
            summary="Generated dbt source, model and test scaffold from ContractForge/schema evidence.",
            assumptions=[
                Assumption(
                    statement="dbt is modeled as a downstream transformation and testing layer over ContractForge-managed tables.",
                    confidence=0.72,
                    review_required=True,
                ),
                *draft.traceability.assumptions,
            ],
            decisions_required=decisions,
            warnings=[
                *draft.warnings,
                "The generated dbt project does not include a profiles.yml file or credentials.",
            ],
        ),
        traceability=Traceability(
            confidence=draft.traceability.confidence,
            evidence=[
                EvidenceItem(
                    source="contract_draft",
                    reason="Generated dbt artifacts from deterministic ContractForge contract draft.",
                    value={"source_name": source_name, "model_name": model_name, "artifacts": len(artifacts)},
                    confidence=draft.traceability.confidence,
                )
            ],
            assumptions=draft.traceability.assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def generate_contractforge_python_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a Python-first ContractForge project scaffold."""

    contract_plan = generate_contractforge_yaml_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
    )
    names = _derive_project_names(
        project_name=project_name,
        target_table=target_table,
        layer=layer,
        naming=naming,
    )
    project_slug = names.slug
    package_name = names.logical_name
    table_name = names.contract_basename
    contract_path = f"contracts/{layer}/{table_name}.ingestion.yaml"
    operations_path = f"contracts/{layer}/{table_name}.operations.yaml"
    annotations_path = f"contracts/{layer}/{table_name}.annotations.yaml"
    notebook_path = f"notebooks/run_{layer}_{table_name}.py"
    contract_artifacts = [artifact for artifact in contract_plan.artifacts if _is_contractforge_project_artifact(artifact)]

    artifacts = [
        ProjectArtifact(
            path="pyproject.toml",
            kind="config",
            description="Python project configuration draft.",
            content=_python_pyproject_toml(project_slug, package_name),
        ),
        ProjectArtifact(
            path=f"src/{package_name}/__init__.py",
            kind="python",
            description="Generated Python package marker.",
            content='"""Generated ContractForge ingestion project."""\n',
        ),
        ProjectArtifact(
            path=f"src/{package_name}/config.py",
            kind="python",
            description="Generated project path configuration.",
            content=_python_config_py(contract_path, annotations_path, operations_path),
        ),
        ProjectArtifact(
            path=f"src/{package_name}/run_ingestion.py",
            kind="python",
            description="Python entry point that executes the generated ContractForge contract.",
            content=_python_run_ingestion_py(package_name),
        ),
        ProjectArtifact(
            path=notebook_path,
            kind="notebook",
            description="Databricks notebook-style Python runner.",
            content=_python_notebook_runner(package_name),
        ),
        *contract_artifacts,
        ProjectArtifact(
            path="DECISIONS.md",
            kind="markdown",
            description="Python project review checklist and required decisions.",
            content=_python_decisions_markdown(project_name, contract_plan.report),
        ),
        ProjectArtifact(
            path="RUNBOOK.md",
            kind="markdown",
            description="Operational runbook for the generated ContractForge Python project.",
            content=_runbook_markdown(
                project_name=project_name,
                target="ContractForge Python",
                purpose="Run ContractForge ingestion through an explicit Python entry point.",
                entrypoints=[f"`src/{package_name}/run_ingestion.py`", f"`{notebook_path}`", f"`{contract_path}`"],
                validation_commands=["pip install -e .", f"{project_slug}-ingest --contract {contract_path}"],
                review_notes=[
                    "Keep the Python wrapper thin; ingestion behavior belongs in contracts.",
                    "Use plan actions before platform execution: plan-databricks or plan-aws.",
                    "Confirm runtime dependency installation for ContractForge and source connectors.",
                    "Review result status and control-table evidence after execution.",
                ],
            ),
        ),
        ProjectArtifact(
            path="VALIDATION.md",
            kind="markdown",
            description="Generated contract validation report.",
            content=_validation_markdown(
                project_name=project_name,
                contract_path=contract_path,
                deterministic=_validation_from_contract_artifacts(contract_artifacts),
                contractforge=validate_with_contractforge(_contract_from_contract_artifacts(contract_artifacts)),
            ),
        ),
        ProjectArtifact(
            path="README.md",
            kind="markdown",
            description="Generated Python project overview.",
            content=_python_readme_markdown(
                project_name=project_name,
                project_slug=project_slug,
                package_name=package_name,
                contract_path=contract_path,
                notebook_path=notebook_path,
            ),
        ),
    ]

    decisions = [
        *contract_plan.report.decisions_required,
        RequiredDecision(
            question="Confirm Python runtime and dependency installation strategy.",
            reason="The scaffold declares ContractForge as a dependency but does not pin an internal package registry.",
            path="pyproject.toml.project.dependencies",
        ),
        RequiredDecision(
            question="Confirm whether execution should use CLI, notebook, job task or orchestration framework.",
            reason="The scaffold provides both a Python entry point and a notebook-style runner.",
            path="src",
            options=["python module", "Databricks notebook", "workflow/job task", "external orchestrator"],
        ),
    ]

    return ProjectPlan(
        name=project_slug,
        target="contractforge-python",
        artifacts=artifacts,
        report=DecisionReport(
            title=f"{project_name} ContractForge Python Project",
            summary="Generated Python-first ContractForge project scaffold with separate reviewable contracts.",
            assumptions=contract_plan.report.assumptions,
            decisions_required=decisions,
            warnings=[
                *contract_plan.report.warnings,
                "Generated Python code is an execution wrapper. Ingestion behavior remains in reviewable contract files.",
            ],
        ),
        traceability=Traceability(
            confidence=contract_plan.traceability.confidence,
            evidence=[
                EvidenceItem(
                    source="contractforge_yaml_project",
                    reason="Generated Python scaffold from deterministic ContractForge YAML project plan.",
                    value={"artifacts": len(artifacts), "contract_path": contract_path, "package": package_name},
                    confidence=contract_plan.traceability.confidence,
                )
            ],
            assumptions=contract_plan.traceability.assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def generate_classic_pyspark_project(
    schema_path: str | Path,
    *,
    project_name: str,
    connector: str,
    source_path: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    layer: str = "bronze",
    mode: str | None = None,
    owner: str | None = None,
    naming: Any | None = None,
    schedule_cron: str = "0 6 * * *",
    schedule_timezone: str = "UTC",
    schedule_enabled: bool = False,
) -> ProjectPlan:
    """Generate a classic PySpark comparison scaffold next to ContractForge contracts."""

    contract_plan = generate_contractforge_yaml_project(
        schema_path,
        project_name=project_name,
        connector=connector,
        source_path=source_path,
        target_catalog=target_catalog,
        target_schema=target_schema,
        target_table=target_table,
        layer=layer,
        mode=mode,
        owner=owner,
        naming=naming,
        schedule_cron=schedule_cron,
        schedule_timezone=schedule_timezone,
        schedule_enabled=schedule_enabled,
    )
    names = _derive_project_names(
        project_name=project_name,
        target_table=target_table,
        layer=layer,
        naming=naming,
    )
    project_slug = names.logical_name
    table_name = names.contract_basename
    target_fqn = f"{target_catalog}.{target_schema}.{target_table}"
    contract_path = f"contracts/{layer}/{table_name}.ingestion.yaml"
    script_path = f"classic_pyspark/run_{layer}_{table_name}.py"
    notebook_path = f"notebooks/classic_run_{layer}_{table_name}.py"
    contract_artifacts = [artifact for artifact in contract_plan.artifacts if _is_contractforge_project_artifact(artifact)]

    artifacts = [
        ProjectArtifact(
            path=script_path,
            kind="python",
            description="Classic PySpark comparison script.",
            content=_classic_pyspark_script(
                connector=connector,
                source_path=source_path,
                target_fqn=target_fqn,
                mode=mode or _mode_from_contract_artifacts(contract_artifacts),
            ),
        ),
        ProjectArtifact(
            path=notebook_path,
            kind="notebook",
            description="Databricks notebook-style classic PySpark comparison runner.",
            content=_classic_pyspark_notebook(
                connector=connector,
                source_path=source_path,
                target_fqn=target_fqn,
                mode=mode or _mode_from_contract_artifacts(contract_artifacts),
            ),
        ),
        *contract_artifacts,
        ProjectArtifact(
            path="MIGRATION.md",
            kind="markdown",
            description="Migration notes from classic PySpark to ContractForge.",
            content=_classic_migration_markdown(project_name, contract_path, script_path, notebook_path),
        ),
        ProjectArtifact(
            path="DECISIONS.md",
            kind="markdown",
            description="Classic PySpark review checklist and required decisions.",
            content=_classic_decisions_markdown(project_name, contract_plan.report),
        ),
        ProjectArtifact(
            path="RUNBOOK.md",
            kind="markdown",
            description="Operational runbook for the generated classic PySpark comparison project.",
            content=_runbook_markdown(
                project_name=project_name,
                target="Classic PySpark comparison",
                purpose="Compare manual PySpark ingestion with the recommended ContractForge contract.",
                entrypoints=[f"`{script_path}`", f"`{notebook_path}`", f"`{contract_path}`"],
                validation_commands=["Review MIGRATION.md", f"Review {script_path}", f"Review {contract_path}"],
                review_notes=[
                    "Use classic PySpark artifacts for migration review, not as the preferred governed path.",
                    "Replace Spark reader placeholders only if a temporary manual execution path is required.",
                    "Prefer ContractForge for quality, schema, lineage, governance and control-table behavior.",
                ],
            ),
        ),
        ProjectArtifact(
            path="VALIDATION.md",
            kind="markdown",
            description="Generated contract validation report.",
            content=_validation_markdown(
                project_name=project_name,
                contract_path=contract_path,
                deterministic=_validation_from_contract_artifacts(contract_artifacts),
                contractforge=validate_with_contractforge(_contract_from_contract_artifacts(contract_artifacts)),
            ),
        ),
        ProjectArtifact(
            path="README.md",
            kind="markdown",
            description="Generated classic PySpark comparison project overview.",
            content=_classic_readme_markdown(
                project_name=project_name,
                contract_path=contract_path,
                script_path=script_path,
                notebook_path=notebook_path,
                target_fqn=target_fqn,
            ),
        ),
    ]

    decisions = [
        *contract_plan.report.decisions_required,
        RequiredDecision(
            question="Confirm whether the classic PySpark script is for comparison only or temporary migration execution.",
            reason="Contract-first execution should remain the preferred production path.",
            path=script_path,
            options=["comparison only", "temporary migration", "do not use"],
        ),
        RequiredDecision(
            question="Confirm manual PySpark read/write behavior for non-append modes.",
            reason="Merge-based and governance-heavy modes require business-specific logic that should not be guessed.",
            path=script_path,
        ),
    ]

    return ProjectPlan(
        name=project_slug,
        target="classic-pyspark",
        artifacts=artifacts,
        report=DecisionReport(
            title=f"{project_name} Classic PySpark Comparison Project",
            summary="Generated classic PySpark comparison scaffold with ContractForge contracts as the recommended path.",
            assumptions=contract_plan.report.assumptions,
            decisions_required=decisions,
            warnings=[
                *contract_plan.report.warnings,
                "Classic PySpark artifacts are generated for migration and comparison, not as the preferred production pattern.",
            ],
        ),
        traceability=Traceability(
            confidence=contract_plan.traceability.confidence,
            evidence=[
                EvidenceItem(
                    source="contractforge_yaml_project",
                    reason="Generated classic PySpark comparison scaffold from deterministic ContractForge YAML project plan.",
                    value={"artifacts": len(artifacts), "contract_path": contract_path, "script_path": script_path},
                    confidence=contract_plan.traceability.confidence,
                )
            ],
            assumptions=contract_plan.traceability.assumptions,
            decisions_required=decisions,
            review_required=True,
        ),
    )


def _contract_file(root_key: str, payload: dict) -> dict:
    del root_key
    return {
        "_metadata": {
            "generated_by": "contractforge-ai",
            "draft": True,
            "review_required": True,
        },
        **payload,
    }


def _yaml(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False)


def _is_contractforge_project_artifact(artifact: ProjectArtifact) -> bool:
    return artifact.path == "project.yaml" or artifact.path.startswith(
        ("contracts/", "connections/", "environments/")
    )


def _contract_with_connection_reference(
    contract: dict[str, Any],
    *,
    connector: str,
    connection_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = dict(contract.get("source") or {})
    connection_source = {
        "source": {
            "type": source.get("type") or "connector",
            "connector": source.get("connector") or connector,
        }
    }
    ingestion_source = {
        "type": "connection",
        "connection_path": f"project://{connection_path}",
        **{
            key: value
            for key, value in source.items()
            if key not in {"type", "connector", "auth", "options"}
        },
    }
    if connector == "table" and "path" in ingestion_source and "table" not in ingestion_source:
        ingestion_source["table"] = ingestion_source.pop("path")
    if source.get("auth"):
        connection_source["source"]["auth"] = source["auth"]
    if source.get("options"):
        connection_source["source"]["options"] = source["options"]
    updated = dict(contract)
    updated["source"] = ingestion_source
    return updated, connection_source


def _resolved_contract_from_connection(contract: dict[str, Any], connection: dict[str, Any]) -> dict[str, Any]:
    source = dict(contract.get("source") or {})
    connection_source = dict(connection.get("source") or connection)
    overrides = {key: value for key, value in source.items() if key not in {"type", "connection_path"}}
    resolved = _deep_merge(connection_source, overrides)
    updated = dict(contract)
    updated["source"] = resolved
    return updated


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _review_environment_payload() -> dict[str, Any]:
    return {
        "name": "review",
        "adapter": "REVIEW_REQUIRED",
        "evidence": {
            "schema": "ops",
        },
    }


def _project_yaml(
    *,
    project_name: str,
    environment_path: str,
    connection_path: str,
    contract_path: str,
    step_name: str,
    schedule_cron: str,
    schedule_timezone: str,
    schedule_enabled: bool,
) -> str:
    return _yaml(
        {
            "name": project_name,
            "environments": {
                "review": environment_path,
            },
            "connections": {
                "source": connection_path,
            },
            "schedule": {
                "cron": schedule_cron,
                "timezone": schedule_timezone,
                "enabled": schedule_enabled,
            },
            "execution_order": [
                {
                    "name": step_name,
                    "depends_on": [],
                    "contracts": {
                        "review": contract_path,
                    },
                }
            ],
        }
    )


def _adapter_project_yaml(
    *,
    project_name: str,
    adapter: str,
    environment_path: str,
    connection_path: str,
    contract_path: str,
    step_name: str,
    schedule_cron: str,
    schedule_timezone: str,
    schedule_enabled: bool,
) -> str:
    return _yaml(
        {
            "name": project_name,
            "environments": {
                adapter: environment_path,
            },
            "connections": {
                "source": connection_path,
            },
            "schedule": {
                "cron": schedule_cron,
                "timezone": schedule_timezone,
                "enabled": schedule_enabled,
            },
            "execution_order": [
                {
                    "name": step_name,
                    "depends_on": [],
                    "contracts": {
                        adapter: contract_path,
                    },
                }
            ],
        }
    )


def _relocate_split_contract_artifacts(
    artifacts: list[ProjectArtifact],
    *,
    layer: str,
    contract_name: str,
    adapter: str,
) -> list[ProjectArtifact]:
    source_prefix = f"contracts/{layer}/{contract_name}"
    target_prefix = f"contracts/{adapter}/{layer}/{contract_name}/{contract_name}"
    relocated: list[ProjectArtifact] = []
    for artifact in artifacts:
        path = artifact.path
        if path.startswith(f"{source_prefix}."):
            suffix = path.removeprefix(source_prefix)
            path = f"{target_prefix}{suffix}"
        if path.startswith(("contracts/", "connections/")):
            relocated.append(
                ProjectArtifact(
                    path=path,
                    kind=artifact.kind,
                    description=artifact.description,
                    content=artifact.content,
                )
            )
    return relocated


def _with_adapter_project_environment(
    artifacts: list[ProjectArtifact],
    *,
    adapter: str,
    environment_path: str,
    environment_payload: dict[str, Any],
) -> list[ProjectArtifact]:
    updated: list[ProjectArtifact] = []
    for artifact in artifacts:
        if artifact.path != "project.yaml":
            updated.append(artifact)
            continue
        payload = yaml.safe_load(artifact.content)
        if not isinstance(payload, dict):
            updated.append(artifact)
            continue
        environments = dict(payload.get("environments") or {})
        environments[adapter] = environment_path
        payload["environments"] = environments
        for step in payload.get("execution_order") or []:
            if not isinstance(step, dict):
                continue
            contracts = dict(step.get("contracts") or {})
            contract_path = contracts.get(adapter) or contracts.get("review")
            if contract_path:
                contracts[adapter] = contract_path
                step["contracts"] = contracts
        updated.append(
            ProjectArtifact(
                path=artifact.path,
                kind=artifact.kind,
                description=artifact.description,
                content=_yaml(payload),
            )
        )
    updated.append(
        ProjectArtifact(
            path=environment_path,
            kind="config",
            description=f"{adapter.title()} environment contract scaffold. Fill runtime/deployment values before deploy.",
            content=_yaml(environment_payload),
        )
    )
    return updated


def _derive_project_names(
    *,
    project_name: str,
    target_table: str,
    layer: str,
    naming: Any | None,
) -> Any:
    return derive_names(
        target_table=target_table,
        layer=layer,
        data_product=project_name,
        config=normalize_naming_config(naming),
    )


def _naming_payload(naming: Any) -> dict[str, Any]:
    config = normalize_naming_config(naming)
    payload = {
        "policy": config.policy,
        "display_name": config.display_name,
        "logical_name": config.logical_name,
        "slug": config.slug,
        "contract_basename": config.contract_basename,
        "bundle_name": config.bundle_name,
        "job_name": config.job_name,
        "task_key": config.task_key,
        "artifact_prefix": config.artifact_prefix,
        "preserve_target_identifiers": config.preserve_target_identifiers,
    }
    return {key: value for key, value in payload.items() if value is not None}


def _decisions_markdown(project_name: str, assumptions: list[str], decisions: list[str], warnings: list[str]) -> str:
    lines = [
        f"# {project_name} Decisions",
        "",
        "This file lists assumptions and decisions that must be reviewed before using the generated project.",
    ]
    if warnings:
        lines.extend(["", "## Warnings", *[f"- {warning}" for warning in warnings]])
    if assumptions:
        lines.extend(["", "## Assumptions", *[f"- {assumption}" for assumption in assumptions]])
    if decisions:
        lines.extend(["", "## Decisions Required", *[f"- {decision}" for decision in decisions]])
    return "\n".join(lines).rstrip() + "\n"


def _runbook_markdown(
    *,
    project_name: str,
    target: str,
    purpose: str,
    entrypoints: list[str],
    validation_commands: list[str],
    review_notes: list[str],
) -> str:
    lines = [
        f"# {project_name} Runbook",
        "",
        f"Target: `{target}`",
        "",
        "## Purpose",
        "",
        purpose,
        "",
        "## Entry Points",
        "",
        *[f"- {entrypoint}" for entrypoint in entrypoints],
        "",
        "## Pre-Run Checklist",
        "",
        "- Review `DECISIONS.md` and resolve required decisions.",
        "- Confirm all placeholders and environment-specific values.",
        "- Confirm credentials are stored in the target platform secret manager, not in generated files.",
        "- Confirm the target runtime has required package dependencies.",
        "",
        "## Validation Commands",
        "",
    ]
    for command in validation_commands:
        lines.extend(["```bash", command, "```", ""])
    lines.extend(
        [
            "## Operational Review",
            "",
            *[f"- {note}" for note in review_notes],
            "- Capture run results, errors and evidence before promoting the scaffold.",
            "",
            "## Incident Notes",
            "",
            "- Start with the generated contract and runtime logs.",
            "- Check connector authentication, network access, dependency installation and target permissions.",
            "- Use ContractForge control-table evidence when the execution path uses ContractForge.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _validation_markdown(
    *,
    project_name: str,
    contract_path: str,
    deterministic: ValidationResult | None,
    contractforge: ValidationResult,
) -> str:
    lines = [
        f"# {project_name} Validation",
        "",
        f"Contract: `{contract_path}`",
        "",
        "## Deterministic Generated-Artifact Validation",
        "",
        *_validation_result_lines(deterministic),
        "",
        "## ContractForge Validation",
        "",
        *_validation_result_lines(contractforge),
        "",
        "## Review Boundary",
        "",
        "- Deterministic validation checks generated artifact structure and review placeholders.",
        "- ContractForge validation uses contractforge-core semantic normalization and does not execute ingestion.",
        "- Installation or dependency failures must be fixed before treating the scaffold as usable.",
        "- Resolve failed validation findings before treating the scaffold as usable.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _validation_result_lines(result: ValidationResult | None) -> list[str]:
    if result is None:
        return ["- Status: `WARN`", "- Summary: Validation result was not available."]
    lines = [f"- Status: `{result.status}`", f"- Summary: {result.summary}"]
    if not result.findings:
        return lines
    lines.extend(["", "Findings:"])
    for finding in result.findings:
        location = f" `{finding.path}`" if finding.path else ""
        lines.append(f"- `{finding.severity}` `{finding.code}`{location}: {finding.title}")
        lines.append(f"  Recommendation: {finding.recommendation}")
    return lines


def _contract_from_contract_artifacts(artifacts: list[ProjectArtifact]) -> dict[str, Any]:
    connection = _connection_from_artifacts(artifacts)
    for artifact in artifacts:
        if artifact.path.endswith(".ingestion.yaml"):
            try:
                payload = yaml.safe_load(artifact.content)
            except Exception:
                return {}
            if not isinstance(payload, dict):
                return {}
            source = payload.get("source")
            if connection is not None and isinstance(source, dict) and source.get("type") == "connection":
                return _resolved_contract_from_connection(payload, connection)
            return payload
    return {}


def _connection_from_artifacts(artifacts: list[ProjectArtifact]) -> dict[str, Any] | None:
    for artifact in artifacts:
        if artifact.path.startswith("connections/") and artifact.path.endswith((".yaml", ".yml", ".json")):
            try:
                payload = yaml.safe_load(artifact.content)
            except Exception:
                return None
            return payload if isinstance(payload, dict) else None
    return None


def _validation_from_contract_artifacts(artifacts: list[ProjectArtifact]) -> ValidationResult | None:
    contract = _contract_from_contract_artifacts(artifacts)
    if not contract:
        return None
    from contractforge_ai.validation import validate_generated_contract

    return validate_generated_contract(contract)


def _readme_markdown(
    *,
    project_name: str,
    layer: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    artifacts_base: str,
    project_yaml: bool = False,
) -> str:
    project_files = (
        "- `project.yaml`\n"
        "- `environments/review.environment.yaml`\n"
        "- `connections/source.yaml`\n"
        if project_yaml
        else ""
    )
    return (
        f"# {project_name}\n\n"
        "Generated ContractForge YAML project scaffold.\n\n"
        "## Target\n\n"
        f"- Layer: `{layer}`\n"
        f"- Catalog: `{target_catalog}`\n"
        f"- Schema: `{target_schema}`\n"
        f"- Table: `{target_table}`\n\n"
        "## Files\n\n"
        f"{project_files}"
        f"- `{artifacts_base}.ingestion.yaml`\n"
        f"- `{artifacts_base}.annotations.yaml`\n"
        f"- `{artifacts_base}.operations.yaml`\n"
        "- `DECISIONS.md`\n\n"
        "## Review Before Use\n\n"
        "- Confirm source connector options and credentials.\n"
        "- Confirm target catalog, schema and table.\n"
        "- Confirm write mode and merge keys.\n"
        "- Review generated annotations, PII candidates and quality rules with data owners.\n"
        "- Run ContractForge validation or dry-run before execution.\n"
    )


def _databricks_yml(bundle_name: str, *, compute: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "bundle": {"name": bundle_name},
        "include": ["resources/*.yml"],
        "workspace": {"root_path": f"~/.bundle/{bundle_name}/${{bundle.target}}"},
        "targets": {
            "dev": {
                "mode": "development",
                "default": True,
            }
        },
    }
    if _compute_kind(compute) in {"placeholder", "existing_cluster"}:
        payload["variables"] = {
            "existing_cluster_id": {
                "description": "Existing cluster ID for notebook tasks.",
                "default": _existing_cluster_default(compute),
            }
        }
    return _yaml(payload)


def _dab_jobs_yml(
    job_resource_key: str,
    job_name: str,
    task_key: str,
    notebook_path: str,
    *,
    compute: dict[str, Any] | None = None,
) -> str:
    task: dict[str, Any] = {
        "task_key": task_key,
        "notebook_task": {"notebook_path": f"./{notebook_path}"},
    }
    compute_kind = _compute_kind(compute)
    if compute_kind == "serverless":
        task["environment_key"] = "default"
    elif compute_kind == "job_cluster":
        task["job_cluster_key"] = "contractforge_job_cluster"
    else:
        task["existing_cluster_id"] = "${var.existing_cluster_id}"

    job: dict[str, Any] = {
        "name": f"[${{bundle.target}}] {job_name}",
        "max_concurrent_runs": 1,
        "tasks": [task],
    }
    if compute_kind == "serverless":
        job["environments"] = [{"environment_key": "default", "spec": {"client": "2"}}]
    if compute_kind == "job_cluster":
        job["job_clusters"] = [
            {
                "job_cluster_key": "contractforge_job_cluster",
                "new_cluster": {
                    "spark_version": "REVIEW_REQUIRED",
                    "node_type_id": "REVIEW_REQUIRED",
                    "num_workers": 1,
                },
            }
        ]
    return _yaml({"resources": {"jobs": {job_resource_key: job}}})


def _compute_kind(compute: dict[str, Any] | None) -> str:
    kind = str((compute or {}).get("type") or "").lower()
    if kind in {"serverless", "job_cluster", "existing_cluster"}:
        return kind
    return "placeholder"


def _compute_is_explicit(compute: dict[str, Any] | None) -> bool:
    return _compute_kind(compute) != "placeholder"


def _existing_cluster_default(compute: dict[str, Any] | None) -> str:
    if _compute_kind(compute) == "existing_cluster":
        return str((compute or {}).get("existing_cluster_id") or "REVIEW_REQUIRED")
    return "REVIEW_REQUIRED"


def _dab_compute_review_note(compute: dict[str, Any] | None) -> str:
    kind = _compute_kind(compute)
    if kind == "serverless":
        return "Confirm the serverless environment dependencies and workspace permissions before deployment."
    if kind == "job_cluster":
        return "Replace the generated job cluster spark_version and node_type_id placeholders before deployment."
    if kind == "existing_cluster":
        return "Confirm the selected existing cluster has ContractForge and connector dependencies installed."
    return "Choose job compute before deployment: existing cluster, job cluster or serverless job compute."


def _dab_compute_warning(compute: dict[str, Any] | None) -> str:
    kind = _compute_kind(compute)
    if kind == "serverless":
        return "The generated bundle uses serverless job compute because the prompt explicitly requested serverless."
    if kind == "job_cluster":
        return "The generated bundle uses a job cluster scaffold with review-required cluster attributes."
    if kind == "existing_cluster":
        return "The generated bundle uses the explicit existing cluster preference from the request."
    return "The generated bundle contains compute placeholders and must be reviewed before deployment."


def _dab_notebook(contract_path: str) -> str:
    return (
        "# Databricks notebook source\n"
        "\"\"\"Run a generated ContractForge ingestion contract.\n\n"
        "Review the generated contract and Databricks Asset Bundle settings before execution.\n"
        "\"\"\"\n\n"
        "from pathlib import Path\n\n"
        "from contractforge_databricks import ingest_databricks_bundle\n\n"
        f"CONTRACT_PATH = Path(__file__).resolve().parents[1] / {contract_path!r}\n\n"
        "result = ingest_databricks_bundle(CONTRACT_PATH, spark=spark, runner=spark)\n"
        "print(result)\n"
    )


def _dab_decisions_markdown(project_name: str, report: DecisionReport, *, compute: dict[str, Any] | None = None) -> str:
    compute_line = {
        "serverless": "- Confirm the generated serverless job environment and workspace permissions.",
        "job_cluster": "- Replace job cluster `spark_version` and `node_type_id` placeholders with approved runtime values.",
        "existing_cluster": "- Confirm the selected `existing_cluster_id` is available and has the required libraries.",
        "placeholder": "- Choose job compute: existing cluster, job cluster or serverless job compute.",
    }[_compute_kind(compute)]
    lines = [
        f"# {project_name} Databricks Asset Bundle Decisions",
        "",
        "Review these decisions before deploying the generated bundle.",
        "",
        "## Databricks Decisions",
        compute_line,
        "- Confirm `workspace.root_path` in `databricks.yml`.",
        "- Confirm bundle target names and deployment profile.",
        "- Ensure ContractForge and any source connector dependencies are installed on the selected runtime.",
    ]
    if report.warnings:
        lines.extend(["", "## Contract Warnings", *[f"- {warning}" for warning in report.warnings]])
    if report.assumptions:
        lines.extend(["", "## Contract Assumptions", *[item.to_markdown() for item in report.assumptions]])
    if report.decisions_required:
        lines.extend(["", "## Contract Decisions", *[item.to_markdown() for item in report.decisions_required]])
    return "\n".join(lines).rstrip() + "\n"


def _dab_readme_markdown(
    *,
    project_name: str,
    bundle_name: str,
    notebook_path: str,
    contract_path: str,
) -> str:
    return (
        f"# {project_name}\n\n"
        "Generated Databricks Asset Bundle scaffold for ContractForge ingestion.\n\n"
        "## Bundle\n\n"
        f"- Bundle name: `{bundle_name}`\n"
        f"- Notebook task: `{notebook_path}`\n"
        f"- Contract: `{contract_path}`\n\n"
        "## First Review\n\n"
        "1. Review `DECISIONS.md`.\n"
        "2. Replace `REVIEW_REQUIRED` placeholders.\n"
        "3. Confirm Databricks compute configuration in `resources/jobs.yml`.\n"
        "4. Confirm ContractForge and connector dependencies are available in the runtime.\n"
        "5. Run `databricks bundle validate` before deploy.\n\n"
        "## Typical Commands\n\n"
        "```bash\n"
        "databricks bundle validate\n"
        "databricks bundle deploy -t dev\n"
        "databricks bundle run <job-name> -t dev\n"
        "```\n"
    )


def _aws_decisions_markdown(project_name: str, report: DecisionReport) -> str:
    lines = [
        f"# {project_name} AWS Glue Iceberg Decisions",
        "",
        "Review these decisions before deploying the generated AWS project.",
        "",
        "## AWS Decisions",
        "- Set `environment.artifacts.uri` to an S3 prefix controlled by the platform team.",
        "- Set `parameters.aws.glue_job.role_arn` to the approved Glue execution role.",
        "- Set `parameters.aws.iceberg.warehouse` to the Iceberg warehouse S3 prefix.",
        "- Upload or reference ContractForge wheels through `parameters.aws.dependencies.extra_py_files`.",
        "- Confirm Glue workers, timeout, bookmarks and region before deployment.",
    ]
    if report.warnings:
        lines.extend(["", "## Contract Warnings", *[f"- {warning}" for warning in report.warnings]])
    if report.assumptions:
        lines.extend(["", "## Contract Assumptions", *[item.to_markdown() for item in report.assumptions]])
    if report.decisions_required:
        lines.extend(["", "## Contract Decisions", *[item.to_markdown() for item in report.decisions_required]])
    return "\n".join(lines).rstrip() + "\n"


def _aws_readme_markdown(
    *,
    project_name: str,
    project_slug: str,
    contract_path: str,
) -> str:
    return (
        f"# {project_name}\n\n"
        "Generated AWS Glue Spark + Iceberg scaffold for ContractForge ingestion.\n\n"
        "## Project\n\n"
        f"- Project id: `{project_slug}`\n"
        f"- Environment: `environments/aws.environment.yaml`\n"
        f"- Contract: `{contract_path}`\n\n"
        "## Runtime Model\n\n"
        "AWS execution uses the `contractforge-aws` adapter runtime. The deploy path publishes the reviewed contract and environment artifacts to S3, registers a Glue job that points at the stable ContractForge AWS runner, and passes the contract URI as a Glue argument. Ingestion behavior remains in the contracts, not in generated per-contract Python code.\n\n"
        "## First Review\n\n"
        "1. Review `DECISIONS.md`.\n"
        "2. Replace `REVIEW_REQUIRED` placeholders in `environments/aws.environment.yaml`.\n"
        "3. Confirm the reusable connection in `connections/source.yaml`.\n"
        "4. Run deterministic project validation with adapter planning.\n"
        "5. Run a dry-run deploy before creating or updating Glue jobs.\n\n"
        "## Typical Commands\n\n"
        "```bash\n"
        "contractforge-ai validate-project-structure . --adapter aws\n"
        f"contractforge-aws plan {contract_path} --environment environments/aws.environment.yaml\n"
        f"contractforge-aws deploy {contract_path} --environment environments/aws.environment.yaml --dry-run\n"
        "```\n"
    )


def _adapter_decisions_markdown(
    project_name: str,
    display_name: str,
    report: DecisionReport,
    extra_decisions: list[RequiredDecision],
) -> str:
    lines = [
        f"# {project_name} {display_name} Decisions",
        "",
        "Review these decisions before deploying the generated adapter project.",
        "",
        f"## {display_name} Decisions",
        "- Replace `REVIEW_REQUIRED` values in the environment file before deployment.",
        "- Run `contractforge-ai validate-project-structure` with the adapter gate enabled.",
        "- Run the adapter planner and treat `REVIEW_REQUIRED`, `UNSUPPORTED` and `BLOCKED` findings as release blockers.",
        "- Keep behavior-changing source, target, write, transform, quality and governance changes in contracts.",
        "- Keep runtime, deployment, credential and artifact-location changes in environment or adapter artifacts.",
    ]
    if extra_decisions:
        lines.extend(["", "## Adapter Decisions", *[item.to_markdown() for item in extra_decisions]])
    if report.warnings:
        lines.extend(["", "## Contract Warnings", *[f"- {warning}" for warning in report.warnings]])
    if report.assumptions:
        lines.extend(["", "## Contract Assumptions", *[item.to_markdown() for item in report.assumptions]])
    if report.decisions_required:
        lines.extend(["", "## Contract Decisions", *[item.to_markdown() for item in report.decisions_required]])
    return "\n".join(lines).rstrip() + "\n"


def _adapter_readme_markdown(
    *,
    project_name: str,
    display_name: str,
    project_slug: str,
    contract_path: str,
    validation_commands: list[str],
) -> str:
    commands = "\n".join(validation_commands)
    return (
        f"# {project_name}\n\n"
        f"Generated {display_name} scaffold for ContractForge ingestion.\n\n"
        "## Project\n\n"
        f"- Project id: `{project_slug}`\n"
        f"- Contract: `{contract_path}`\n"
        "- Runtime settings: `environments/`\n"
        "- Reusable source connection: `connections/source.yaml`\n\n"
        "## Runtime Model\n\n"
        f"{display_name} execution uses its ContractForge adapter runtime. The generated files keep ingestion behavior in "
        "split ContractForge contracts and keep platform-specific runtime values in environment and adapter artifacts.\n\n"
        "## First Review\n\n"
        "1. Review `DECISIONS.md`.\n"
        "2. Replace `REVIEW_REQUIRED` placeholders in the environment file.\n"
        "3. Confirm the reusable connection in `connections/source.yaml`.\n"
        "4. Run deterministic project validation with adapter planning.\n"
        "5. Render or deploy only after the adapter planner is clean.\n\n"
        "## Typical Commands\n\n"
        "```bash\n"
        f"{commands}\n"
        "```\n"
    )


def _schema_columns(schema_path: str | Path) -> list[dict[str, Any]]:
    path = Path(schema_path)
    try:
        import json

        raw = path.read_text(encoding="utf-8")
        payload = yaml.safe_load(raw) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(raw)
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []

    columns = payload.get("columns")
    if isinstance(columns, list):
        return [
            {"name": str(item["name"]), "type": item.get("type") or item.get("data_type")}
            for item in columns
            if isinstance(item, dict) and item.get("name")
        ]
    if isinstance(columns, dict):
        return [
            {"name": str(name), "type": value.get("type") or value.get("data_type")}
            for name, value in columns.items()
            if isinstance(value, dict)
        ]
    return [
        {"name": str(name), "type": value.get("type") or value.get("data_type")}
        for name, value in payload.items()
        if isinstance(value, dict) and ("type" in value or "data_type" in value)
    ]


def _dbt_project_yml(project_slug: str) -> str:
    return _yaml(
        {
            "name": project_slug,
            "version": "1.0.0",
            "config-version": 2,
            "profile": "REVIEW_REQUIRED",
            "model-paths": ["models"],
            "analysis-paths": ["analyses"],
            "test-paths": ["tests"],
            "seed-paths": ["seeds"],
            "macro-paths": ["macros"],
            "snapshot-paths": ["snapshots"],
            "target-path": "target",
            "clean-targets": ["target", "dbt_packages"],
            "models": {project_slug: {"+materialized": "view"}},
        }
    )


def _dbt_sources_yml(
    *,
    source_name: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    columns: list[dict[str, Any]],
    annotations: dict[str, Any],
) -> str:
    column_annotations = annotations.get("columns", {}) if isinstance(annotations, dict) else {}
    return _yaml(
        {
            "version": 2,
            "sources": [
                {
                    "name": source_name,
                    "description": "ContractForge-managed source table for dbt transformations.",
                    "database": target_catalog,
                    "schema": target_schema,
                    "tables": [
                        {
                            "name": target_table,
                            "description": "Table written by ContractForge ingestion.",
                            "columns": [
                                {
                                    "name": column["name"],
                                    "description": _column_description(column["name"], column_annotations),
                                }
                                for column in columns
                            ],
                        }
                    ],
                }
            ],
        }
    )


def _dbt_staging_sql(source_name: str, target_table: str, columns: list[dict[str, Any]]) -> str:
    selected_columns = [column["name"] for column in columns]
    if not selected_columns:
        select_list = "    *"
    else:
        select_list = ",\n".join(f"    {name}" for name in selected_columns)
    return (
        "with source as (\n"
        f"    select * from {{{{ source('{source_name}', '{target_table}') }}}}\n"
        ")\n\n"
        "select\n"
        f"{select_list}\n"
        "from source\n"
    )


def _dbt_model_yml(
    *,
    model_name: str,
    columns: list[dict[str, Any]],
    quality_rules: dict[str, Any],
    annotations: dict[str, Any],
) -> str:
    column_annotations = annotations.get("columns", {}) if isinstance(annotations, dict) else {}
    return _yaml(
        {
            "version": 2,
            "models": [
                {
                    "name": model_name,
                    "description": "Staging model generated from ContractForge/schema evidence.",
                    "columns": [
                        {
                            "name": column["name"],
                            "description": _column_description(column["name"], column_annotations),
                            "data_tests": _dbt_tests_for_column(column["name"], quality_rules),
                        }
                        for column in columns
                    ],
                }
            ],
        }
    )


def _dbt_tests_for_column(column_name: str, quality_rules: dict[str, Any]) -> list[Any]:
    tests: list[Any] = []
    if column_name in quality_rules.get("not_null", []):
        tests.append("not_null")
    unique_keys = quality_rules.get("unique_key", [])
    if isinstance(unique_keys, str):
        unique_keys = [unique_keys]
    if column_name in unique_keys:
        tests.append("unique")
    accepted_values = quality_rules.get("accepted_values", {})
    if isinstance(accepted_values, dict) and column_name in accepted_values:
        tests.append({"accepted_values": {"arguments": {"values": accepted_values[column_name]}}})
    return tests


def _column_description(column_name: str, column_annotations: dict[str, Any]) -> str:
    annotation = column_annotations.get(column_name, {})
    if isinstance(annotation, dict) and annotation.get("description"):
        return str(annotation["description"])
    return f"{column_name} value."


def _dbt_decisions_markdown(project_name: str, decisions: list[str], warnings: list[str]) -> str:
    lines = [
        f"# {project_name} dbt Decisions",
        "",
        "Review these decisions before using the generated dbt project.",
        "",
        "## dbt Decisions",
        "- Replace the `profile: REVIEW_REQUIRED` placeholder in `dbt_project.yml`.",
        "- Confirm that `models/sources.yml` points to the intended ContractForge-managed table.",
        "- Review generated generic tests before enabling dbt CI gates.",
    ]
    if warnings:
        lines.extend(["", "## Warnings", *[f"- {warning}" for warning in warnings]])
    if decisions:
        lines.extend(["", "## ContractForge Decisions", *[f"- {decision}" for decision in decisions]])
    return "\n".join(lines).rstrip() + "\n"


def _dbt_readme_markdown(
    *,
    project_name: str,
    source_name: str,
    target_catalog: str,
    target_schema: str,
    target_table: str,
    model_name: str,
) -> str:
    return (
        f"# {project_name}\n\n"
        "Generated dbt starter project for transformations over ContractForge-managed data.\n\n"
        "## Source\n\n"
        f"- dbt source: `{source_name}`\n"
        f"- Database/catalog: `{target_catalog}`\n"
        f"- Schema: `{target_schema}`\n"
        f"- Table: `{target_table}`\n\n"
        "## Model\n\n"
        f"- Staging model: `{model_name}`\n"
        "- Materialization defaults to `view` in `dbt_project.yml`.\n\n"
        "## First Review\n\n"
        "1. Review `DECISIONS.md`.\n"
        "2. Replace `profile: REVIEW_REQUIRED` with the correct dbt profile.\n"
        "3. Confirm source database, schema and table names for your adapter.\n"
        "4. Review generated tests in `models/staging/*.yml`.\n"
        "5. Run `dbt parse`, then `dbt build` when the profile is configured.\n\n"
        "## Typical Commands\n\n"
        "```bash\n"
        "dbt parse\n"
        "dbt build --select staging\n"
        "```\n"
    )


def _python_pyproject_toml(project_slug: str, package_name: str) -> str:
    return (
        "[project]\n"
        f"name = \"{project_slug}\"\n"
        "version = \"0.1.0\"\n"
        "description = \"Generated ContractForge ingestion project.\"\n"
        "requires-python = \">=3.10\"\n"
        "dependencies = [\n"
        "  \"contractforge-core\",\n"
        "  \"PyYAML\",\n"
        "]\n\n"
        "[project.optional-dependencies]\n"
        "databricks = [\"contractforge-databricks\"]\n"
        "aws = [\"contractforge-aws\"]\n\n"
        "[project.scripts]\n"
        f"{project_slug}-ingest = \"{package_name}.run_ingestion:main\"\n"
    )


def _python_config_py(contract_path: str, annotations_path: str, operations_path: str) -> str:
    return (
        '"""Generated project configuration paths."""\n\n'
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "PROJECT_ROOT = Path(__file__).resolve().parents[2]\n"
        f"DEFAULT_CONTRACT_PATH = PROJECT_ROOT / {contract_path!r}\n"
        f"DEFAULT_ANNOTATIONS_PATH = PROJECT_ROOT / {annotations_path!r}\n"
        f"DEFAULT_OPERATIONS_PATH = PROJECT_ROOT / {operations_path!r}\n"
    )


def _python_run_ingestion_py(package_name: str) -> str:
    return (
        '"""Validate or execute a generated ContractForge ingestion contract."""\n\n'
        "from __future__ import annotations\n\n"
        "import argparse\n"
        "import json\n"
        "from dataclasses import asdict, is_dataclass\n"
        "from pathlib import Path\n"
        "from typing import Any, Callable\n\n"
        "import yaml\n"
        "from contractforge_core.contracts import load_contract_bundle, semantic_contract_from_mapping\n\n"
        f"from {package_name}.config import DEFAULT_CONTRACT_PATH\n\n\n"
        "Action = Callable[[str | Path], dict[str, Any]]\n\n\n"
        "def load_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:\n"
        "    contract_path = Path(path)\n"
        "    with contract_path.open(\"r\", encoding=\"utf-8\") as handle:\n"
        "        payload = yaml.safe_load(handle)\n"
        "    if not isinstance(payload, dict):\n"
        "        raise ValueError(f\"Contract must be a YAML object: {contract_path}\")\n"
        "    return payload\n\n\n"
        "def load_bundle_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:\n"
        "    return load_contract_bundle(path).contract\n\n\n"
        "def validate(contract_path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:\n"
        "    bundle = load_contract_bundle(contract_path)\n"
        "    semantic = semantic_contract_from_mapping(bundle.contract)\n"
        "    return {\n"
        "        \"status\": \"VALIDATED\",\n"
        "        \"target\": semantic.target.name,\n"
        "        \"layer\": semantic.target.layer,\n"
        "        \"mode\": semantic.write.mode,\n"
        "    }\n\n\n"
        "def plan_databricks(contract_path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:\n"
        "    from contractforge_databricks.api import plan_databricks_contract\n\n"
        "    return _planning_result_to_dict(plan_databricks_contract(load_bundle_contract(contract_path)))\n\n\n"
        "def plan_aws(contract_path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:\n"
        "    from contractforge_aws.api import plan_aws_contract\n\n"
        "    return _planning_result_to_dict(plan_aws_contract(load_bundle_contract(contract_path)))\n\n\n"
        "def run_databricks(contract_path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:\n"
        "    from databricks.sdk.runtime import spark\n"
        "    from contractforge_databricks import ingest_databricks_bundle\n\n"
        "    result = ingest_databricks_bundle(contract_path, spark=spark, runner=spark)\n"
        "    if not isinstance(result, dict):\n"
        "        return {\"status\": \"UNKNOWN\", \"result\": result}\n"
        "    return result\n\n\n"
        "ACTIONS: dict[str, Action] = {\n"
        "    \"validate\": validate,\n"
        "    \"plan-databricks\": plan_databricks,\n"
        "    \"run-databricks\": run_databricks,\n"
        "    \"plan-aws\": plan_aws,\n"
        "}\n\n\n"
        "def run(contract_path: str | Path = DEFAULT_CONTRACT_PATH, *, action: str = \"validate\") -> dict[str, Any]:\n"
        "    try:\n"
        "        handler = ACTIONS[action]\n"
        "    except KeyError as exc:\n"
        "        raise ValueError(f\"action must be one of: {', '.join(sorted(ACTIONS))}\") from exc\n"
        "    return handler(contract_path)\n\n\n"
        "def _planning_result_to_dict(result: Any) -> dict[str, Any]:\n"
        "    payload = asdict(result) if is_dataclass(result) else dict(result)\n"
        "    return {\n"
        "        \"status\": payload.get(\"status\"),\n"
        "        \"plan\": payload.get(\"plan\"),\n"
        "        \"warnings\": payload.get(\"warnings\", ()),\n"
        "        \"blockers\": payload.get(\"blockers\", ()),\n"
        "    }\n\n\n"
        "def main(argv: list[str] | None = None) -> int:\n"
        "    parser = argparse.ArgumentParser(description=\"Run a ContractForge ingestion contract.\")\n"
        "    parser.add_argument(\"--contract\", default=str(DEFAULT_CONTRACT_PATH), help=\"Path to the ingestion contract YAML.\")\n"
        "    parser.add_argument(\"--action\", default=\"validate\", choices=sorted(ACTIONS), help=\"Validation, planning or execution action.\")\n"
        "    args = parser.parse_args(argv)\n"
        "    result = run(args.contract, action=args.action)\n"
        "    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))\n"
        "    return 0\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    raise SystemExit(main())\n"
    )


def _python_notebook_runner(package_name: str) -> str:
    return (
        "# Databricks notebook source\n"
        "\"\"\"Run the generated ContractForge Python project.\n\n"
        "Install the generated project and ContractForge dependencies before execution.\n"
        "\"\"\"\n\n"
        f"from {package_name}.run_ingestion import run\n\n"
        "result = run(action=\"run-databricks\")\n"
        "display(result)\n"
    )


def _python_decisions_markdown(project_name: str, report: DecisionReport) -> str:
    lines = [
        f"# {project_name} Python Project Decisions",
        "",
        "Review these decisions before using the generated Python project.",
        "",
        "## Python Decisions",
        "- Confirm how the generated package will be installed in the target runtime.",
        "- Confirm whether execution will run through the Python module, notebook, Databricks job, AWS Glue deployment or external orchestrator.",
        "- Keep ingestion behavior in contract files unless there is a clear reason to own custom Python logic.",
    ]
    if report.warnings:
        lines.extend(["", "## Contract Warnings", *[f"- {warning}" for warning in report.warnings]])
    if report.assumptions:
        lines.extend(["", "## Contract Assumptions", *[item.to_markdown() for item in report.assumptions]])
    if report.decisions_required:
        lines.extend(["", "## Contract Decisions", *[item.to_markdown() for item in report.decisions_required]])
    return "\n".join(lines).rstrip() + "\n"


def _python_readme_markdown(
    *,
    project_name: str,
    project_slug: str,
    package_name: str,
    contract_path: str,
    notebook_path: str,
) -> str:
    return (
        f"# {project_name}\n\n"
        "Generated Python-first ContractForge ingestion project.\n\n"
        "## Structure\n\n"
        f"- Python package: `src/{package_name}`\n"
        f"- Default ingestion contract: `{contract_path}`\n"
        f"- Notebook runner: `{notebook_path}`\n"
        "- Review checklist: `DECISIONS.md`\n\n"
        "## First Review\n\n"
        "1. Review `DECISIONS.md`.\n"
        "2. Review the generated contract files under `contracts/`.\n"
        "3. Confirm dependency installation for ContractForge and source connectors.\n"
        "4. Run ContractForge validation or dry-run before production execution.\n\n"
        "## Typical Commands\n\n"
        "```bash\n"
        "pip install -e .\n"
        f"{project_slug}-ingest --contract {contract_path}\n"
        f"{project_slug}-ingest --action plan-databricks --contract {contract_path}\n"
        f"{project_slug}-ingest --action plan-aws --contract {contract_path}\n"
        "```\n\n"
        "The Python wrapper should stay thin. Source behavior, write mode, quality rules and governance metadata remain in reviewable contracts. Databricks execution is available through `run-databricks`; AWS execution is deployment-owned by the AWS adapter after planning and artifact publication.\n"
    )


def _mode_from_contract_artifacts(artifacts: list[ProjectArtifact]) -> str:
    for artifact in artifacts:
        if artifact.path.endswith(".ingestion.yaml"):
            try:
                payload = yaml.safe_load(artifact.content)
            except Exception:
                return "append"
            if isinstance(payload, dict) and payload.get("mode"):
                return str(payload["mode"])
    return "append"


def _classic_pyspark_script(*, connector: str, source_path: str, target_fqn: str, mode: str) -> str:
    write_mode = "overwrite" if mode == "overwrite" else "append"
    return (
        '"""Classic PySpark comparison script generated beside a ContractForge contract.\n\n'
        "Use this file for migration review or behavior comparison. Prefer the generated\n"
        "ContractForge contract for governed production ingestion.\n"
        "\"\"\"\n\n"
        "from __future__ import annotations\n\n"
        "from pyspark.sql import SparkSession\n\n\n"
        "def get_spark() -> SparkSession:\n"
        "    return SparkSession.builder.getOrCreate()\n\n\n"
        "def read_source(spark: SparkSession):\n"
        f"    connector = {connector!r}\n"
        f"    source_path = {source_path!r}\n"
        "    # Review this mapping. ContractForge connectors may include behavior that\n"
        "    # is not equivalent to a plain Spark DataFrame reader.\n"
        "    if connector in {\"files\", \"azure_blob\", \"s3\", \"gcs\"}:\n"
        "        return spark.read.format(\"REVIEW_REQUIRED\").load(source_path)\n"
        "    raise NotImplementedError(f\"Manual PySpark reader requires review for connector: {connector}\")\n\n\n"
        "def write_target(df) -> None:\n"
        f"    target_table = {target_fqn!r}\n"
        f"    mode = {mode!r}\n"
        f"    write_mode = {write_mode!r}\n"
        "    if mode in {\"append\", \"overwrite\"}:\n"
        "        df.write.format(\"delta\").mode(write_mode).saveAsTable(target_table)\n"
        "        return\n"
        "    raise NotImplementedError(\n"
        "        f\"Manual PySpark implementation for {mode} requires explicit merge and governance logic. \"\n"
        "        \"Use the generated ContractForge contract as the production reference.\"\n"
        "    )\n\n\n"
        "def main() -> None:\n"
        "    spark = get_spark()\n"
        "    df = read_source(spark)\n"
        "    write_target(df)\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    main()\n"
    )


def _classic_pyspark_notebook(*, connector: str, source_path: str, target_fqn: str, mode: str) -> str:
    write_mode = "overwrite" if mode == "overwrite" else "append"
    return (
        "# Databricks notebook source\n"
        "\"\"\"Classic PySpark comparison notebook.\n\n"
        "This notebook mirrors the generated ContractForge contract only as a migration aid.\n"
        "\"\"\"\n\n"
        f"connector = {connector!r}\n"
        f"source_path = {source_path!r}\n"
        f"target_table = {target_fqn!r}\n"
        f"mode = {mode!r}\n\n"
        "if connector in {\"files\", \"azure_blob\", \"s3\", \"gcs\"}:\n"
        "    df = spark.read.format(\"REVIEW_REQUIRED\").load(source_path)\n"
        "else:\n"
        "    raise NotImplementedError(f\"Manual PySpark reader requires review for connector: {connector}\")\n\n"
        "if mode in {\"append\", \"overwrite\"}:\n"
        f"    df.write.format(\"delta\").mode({write_mode!r}).saveAsTable(target_table)\n"
        "else:\n"
        "    raise NotImplementedError(\n"
        "        f\"Manual PySpark implementation for {mode} requires explicit merge and governance logic. \"\n"
        "        \"Use the generated ContractForge contract as the production reference.\"\n"
        "    )\n"
    )


def _classic_migration_markdown(project_name: str, contract_path: str, script_path: str, notebook_path: str) -> str:
    return (
        f"# {project_name} Migration Notes\n\n"
        "This project includes a classic PySpark comparison scaffold beside the recommended ContractForge contract.\n\n"
        "## Recommended Path\n\n"
        f"- Review and execute `{contract_path}` with ContractForge.\n"
        "- Use ContractForge control tables for operational evidence, metrics, quality results and governance metadata.\n\n"
        "## Classic PySpark Artifacts\n\n"
        f"- Script: `{script_path}`\n"
        f"- Notebook: `{notebook_path}`\n\n"
        "These files are useful for migration review, but they intentionally do not attempt to recreate all ContractForge behavior. "
        "Merge strategies, quality gates, quarantine, schema evolution, lineage and control-table writes belong in ContractForge execution.\n"
    )


def _classic_decisions_markdown(project_name: str, report: DecisionReport) -> str:
    lines = [
        f"# {project_name} Classic PySpark Decisions",
        "",
        "Review these decisions before using the generated comparison artifacts.",
        "",
        "## Classic PySpark Decisions",
        "- Confirm whether generated PySpark files are for comparison only.",
        "- Replace `REVIEW_REQUIRED` Spark reader format/options before any manual execution.",
        "- Prefer ContractForge execution for governed production ingestion.",
    ]
    if report.warnings:
        lines.extend(["", "## Contract Warnings", *[f"- {warning}" for warning in report.warnings]])
    if report.assumptions:
        lines.extend(["", "## Contract Assumptions", *[item.to_markdown() for item in report.assumptions]])
    if report.decisions_required:
        lines.extend(["", "## Contract Decisions", *[item.to_markdown() for item in report.decisions_required]])
    return "\n".join(lines).rstrip() + "\n"


def _classic_readme_markdown(
    *,
    project_name: str,
    contract_path: str,
    script_path: str,
    notebook_path: str,
    target_fqn: str,
) -> str:
    return (
        f"# {project_name}\n\n"
        "Generated classic PySpark comparison project for migration from notebook-first ingestion to ContractForge.\n\n"
        "## Files\n\n"
        f"- Recommended ContractForge contract: `{contract_path}`\n"
        f"- Classic PySpark script: `{script_path}`\n"
        f"- Classic Databricks notebook: `{notebook_path}`\n"
        f"- Target table: `{target_fqn}`\n\n"
        "## Review Boundary\n\n"
        "The classic PySpark files are intentionally incomplete for advanced modes. They should not be treated as a full replacement for ContractForge governance, quality, lineage, schema and control-table behavior.\n\n"
        "## Typical Review Flow\n\n"
        "1. Review `MIGRATION.md` and `DECISIONS.md`.\n"
        "2. Compare generated PySpark logic with the ContractForge contract.\n"
        "3. Fill reader format/options only if you need a temporary manual execution path.\n"
        "4. Prefer ContractForge execution for production ingestion.\n"
    )


PROJECT_GENERATORS: Mapping[str, ProjectGenerator] = {
    "contractforge-yaml": generate_contractforge_yaml_project,
    "contractforge-python": generate_contractforge_python_project,
    "databricks-dab": generate_databricks_dab_project,
    "aws-glue-iceberg": generate_aws_glue_iceberg_project,
    "snowflake-sql-warehouse": generate_snowflake_sql_warehouse_project,
    "fabric-lakehouse": generate_fabric_lakehouse_project,
    "gcp-bigquery": generate_gcp_bigquery_project,
    "dbt": generate_dbt_project,
    "classic-pyspark": generate_classic_pyspark_project,
}


def generate_project_for_target(target: str, schema_path: str | Path, **kwargs: Any) -> ProjectPlan:
    """Generate a project scaffold for a registered target."""

    try:
        generator = PROJECT_GENERATORS[target]
    except KeyError as exc:
        supported = ", ".join(supported_project_targets())
        raise ValueError(f"Unsupported project target {target!r}. Supported targets: {supported}") from exc
    return generator(schema_path, **kwargs)
