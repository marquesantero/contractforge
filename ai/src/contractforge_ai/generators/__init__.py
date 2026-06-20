"""Metadata and contract generation helpers."""

from contractforge_ai.generators.contract import generate_contract_draft
from contractforge_ai.generators.metadata import suggest_metadata
from contractforge_ai.generators.project import (
    generate_aws_glue_iceberg_project,
    generate_classic_pyspark_project,
    generate_contractforge_python_project,
    generate_contractforge_yaml_project,
    generate_databricks_dab_project,
    generate_dbt_project,
    generate_fabric_lakehouse_project,
    generate_gcp_bigquery_project,
    generate_project_for_target,
    generate_snowflake_sql_warehouse_project,
)
from contractforge_ai.generators.shape import suggest_shape
from contractforge_ai.generators.targets import supported_project_targets

__all__ = [
    "generate_contract_draft",
    "generate_aws_glue_iceberg_project",
    "generate_classic_pyspark_project",
    "generate_contractforge_python_project",
    "generate_contractforge_yaml_project",
    "generate_databricks_dab_project",
    "generate_dbt_project",
    "generate_fabric_lakehouse_project",
    "generate_gcp_bigquery_project",
    "generate_project_for_target",
    "generate_snowflake_sql_warehouse_project",
    "suggest_metadata",
    "suggest_shape",
    "supported_project_targets",
]

