"""Non-destructive Databricks capability evaluation."""

from __future__ import annotations

from contractforge_databricks.capabilities.builders import capability, uc_sql_capability, workspace_capability
from contractforge_databricks.capabilities.models import DatabricksCapabilities
from contractforge_databricks.capabilities.runtime import is_three_part_name, runtime_evidence, runtime_kind


def evaluate_databricks_capabilities(
    *,
    target_table: str | None = None,
    runtime_type: str | None = None,
    spark_version: str | None = None,
    spark_conf: dict[str, str] | None = None,
    environment: dict[str, str] | None = None,
) -> DatabricksCapabilities:
    """Evaluate Databricks-native capability eligibility from passive evidence."""
    conf = {str(key): str(value) for key, value in (spark_conf or {}).items()}
    env = {str(key): str(value) for key, value in (environment or {}).items()}
    kind = runtime_kind(runtime_type=runtime_type, spark_conf=conf, environment=env)
    is_databricks = kind in {"databricks_classic", "databricks_serverless"}
    is_uc_target = is_three_part_name(target_table)
    evidence = runtime_evidence(runtime_kind=kind, spark_version=spark_version, spark_conf=conf, environment=env)

    capabilities = {
        "databricks_runtime": capability(
            "databricks_runtime",
            "supported" if is_databricks else "unsupported",
            "Databricks runtime evidence was detected."
            if is_databricks
            else "No Databricks runtime evidence was detected.",
            evidence=evidence,
        ),
        "serverless_runtime": capability(
            "serverless_runtime",
            "supported" if kind == "databricks_serverless" else "unsupported",
            "The current runtime is Databricks serverless."
            if kind == "databricks_serverless"
            else "The current runtime is not classified as Databricks serverless.",
            evidence=evidence,
        ),
        "delta_tables": capability(
            "delta_tables",
            "supported" if is_databricks else "unknown",
            "Delta tables are native to Databricks runtimes."
            if is_databricks
            else "Delta support was not probed outside Databricks.",
            evidence=evidence,
            requires=("Delta Lake runtime",),
        ),
        "sql_merge": capability(
            "sql_merge",
            "supported" if is_databricks else "unknown",
            "Databricks SQL MERGE is eligible in Databricks runtimes."
            if is_databricks
            else "SQL MERGE support was not probed outside Databricks.",
            evidence=evidence,
            requires=("Delta table", "MERGE privilege"),
        ),
        "unity_catalog_table": capability(
            "unity_catalog_table",
            "supported" if is_uc_target else "unsupported",
            "Target table is a three-part Unity Catalog name."
            if is_uc_target
            else "Target table is not a three-part Unity Catalog name.",
            requires=("catalog.schema.table",),
        ),
        "uc_table_comments": uc_sql_capability(
            "uc_table_comments", is_uc_target=is_uc_target, is_databricks=is_databricks
        ),
        "uc_column_comments": uc_sql_capability(
            "uc_column_comments", is_uc_target=is_uc_target, is_databricks=is_databricks
        ),
        "uc_table_tags": uc_sql_capability("uc_table_tags", is_uc_target=is_uc_target, is_databricks=is_databricks),
        "uc_column_tags": uc_sql_capability("uc_column_tags", is_uc_target=is_uc_target, is_databricks=is_databricks),
        "uc_grants": uc_sql_capability("uc_grants", is_uc_target=is_uc_target, is_databricks=is_databricks),
        "uc_row_filters": uc_sql_capability("uc_row_filters", is_uc_target=is_uc_target, is_databricks=is_databricks),
        "uc_column_masks": uc_sql_capability("uc_column_masks", is_uc_target=is_uc_target, is_databricks=is_databricks),
        "uc_abac_policies": workspace_capability(
            "uc_abac_policies",
            is_databricks=is_databricks,
            is_uc_target=is_uc_target,
            reason="Unity Catalog ABAC policies require workspace/account feature support and permissions.",
            requires=("Unity Catalog", "policy privileges", "supported workspace feature"),
        ),
        "uc_external_locations": workspace_capability(
            "uc_external_locations",
            is_databricks=is_databricks,
            is_uc_target=True,
            reason="External Locations are Unity Catalog storage-governance objects.",
            requires=("Unity Catalog", "storage credential", "external location privileges"),
        ),
        "uc_volumes": workspace_capability(
            "uc_volumes",
            is_databricks=is_databricks,
            is_uc_target=True,
            reason="Volumes are Unity Catalog storage objects exposed through /Volumes paths.",
            requires=("Unity Catalog", "volume privileges"),
        ),
        "databricks_connections": workspace_capability(
            "databricks_connections",
            is_databricks=is_databricks,
            is_uc_target=True,
            reason="Databricks Connections are governed workspace objects and must be configured externally.",
            requires=("Databricks connection", "connection privileges"),
        ),
        "autoloader_cloudfiles": capability(
            "autoloader_cloudfiles",
            "supported" if is_databricks else "unsupported",
            "Auto Loader cloudFiles is a Databricks runtime capability."
            if is_databricks
            else "Auto Loader cloudFiles requires Databricks runtime support.",
            evidence=evidence,
            requires=("spark.readStream.format('cloudFiles')",),
        ),
        "lakeflow_declarative_pipelines": workspace_capability(
            "lakeflow_declarative_pipelines",
            is_databricks=is_databricks,
            is_uc_target=True,
            reason="Lakeflow Declarative Pipelines are Databricks-native pipeline artifacts.",
            requires=("Databricks workspace pipeline support", "Unity Catalog for governed pipelines"),
        ),
        "lakeflow_auto_cdc": workspace_capability(
            "lakeflow_auto_cdc",
            is_databricks=is_databricks,
            is_uc_target=is_uc_target,
            reason="Lakeflow AUTO CDC requires workspace support and CDC-compatible source semantics.",
            requires=("Lakeflow Declarative Pipelines", "keys", "sequence_by", "CDC source semantics"),
        ),
        "liquid_clustering": workspace_capability(
            "liquid_clustering",
            is_databricks=is_databricks,
            is_uc_target=True,
            reason="Liquid Clustering is a Databricks Delta table optimization feature.",
            requires=("Delta table", "supported Databricks runtime", "table alter privileges"),
        ),
        "delta_control_tables": capability(
            "delta_control_tables",
            "supported" if is_databricks else "unknown",
            "Delta tables can implement ContractForge evidence stores on Databricks."
            if is_databricks
            else "Evidence storage was not probed outside Databricks.",
            evidence=evidence,
            requires=("Delta table create/write privileges",),
        ),
        "snapshot_soft_delete_merge": capability(
            "snapshot_soft_delete_merge",
            "supported" if is_databricks else "unknown",
            "Databricks Delta MERGE supports NOT MATCHED BY SOURCE update semantics."
            if is_databricks
            else "Snapshot reconciliation was not probed outside Databricks.",
            evidence=evidence,
            requires=("Delta MERGE", "NOT MATCHED BY SOURCE"),
        ),
    }
    return DatabricksCapabilities(
        runtime_kind=kind,
        target_table=target_table,
        spark_version=spark_version,
        capabilities=capabilities,
    )
