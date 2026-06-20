"""BigQuery runtime helpers for GCP smoke execution."""

from contractforge_gcp.runtime.bigquery import (
    BqCliBigQueryClient,
    BigQueryJobEvidence,
    BigQueryRuntimeClient,
    GoogleCloudBigQueryClient,
    bigquery_job_evidence,
    bigquery_job_evidence_from_resource,
    bigquery_runtime_client_from_environment,
    load_job_config_from_artifact,
    split_bigquery_script,
)

from . import bigquery as _bigquery

shutil = _bigquery.shutil
subprocess = _bigquery.subprocess

__all__ = [
    "BqCliBigQueryClient",
    "BigQueryJobEvidence",
    "BigQueryRuntimeClient",
    "GoogleCloudBigQueryClient",
    "bigquery_job_evidence",
    "bigquery_job_evidence_from_resource",
    "bigquery_runtime_client_from_environment",
    "load_job_config_from_artifact",
    "split_bigquery_script",
]
