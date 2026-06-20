"""Fabric stabilization status reporting."""

from __future__ import annotations

from typing import Any


def fabric_stabilization_report() -> dict[str, Any]:
    """Return the current Fabric adapter stabilization decision.

    ``supported_surface_ready`` covers the documented notebook-first Lakehouse
    subset with live USGS REST, public HTTP JSON/CSV/text, Lakehouse text/ORC/Avro/XML files, internal OneLake shortcut reads, authenticated Basic REST,
    authenticated bearer/API-key/OAuth REST, authenticated Basic/bearer/API-key
    HTTP JSON, authenticated Basic/bearer/API-key HTTP CSV, endpoint-enforced
    Basic/bearer/API-key-auth HTTP text, SQL Server JDBC, PostgreSQL JDBC,
    public Azure Blob CSV, private Azure Blob CSV with Key Vault-backed storage
    account key, external Azure Blob shortcut reads through a Fabric cloud
    connection, external ADLS Gen2 and Google Cloud Storage shortcut reads
    through Fabric cloud connections, external Amazon S3 and S3-compatible
    shortcut reads through Fabric cloud connections, ADLS Gen2, Amazon S3 and
    Google Cloud Storage Iceberg table shortcut reads, bounded Confluent Kafka
    replay, Confluent Kafka available-now catch-up, Azure Event Hubs
    Kafka-compatible available-now catch-up and stable-surface evidence.
    ``stable_final`` is true for the documented notebook-first Lakehouse
    surface because remaining non-portable or platform-native source families
    are explicit exclusions from this scoped claim.
    """

    return {
        "adapter": "contractforge-fabric",
        "subtarget": "fabric_lakehouse",
        "classification": "STABLE_SUPPORTED_SURFACE",
        "supported_surface_ready": True,
        "stable_final": True,
        "release_candidate": "next-fabric-stable-surface",
        "gates": _gates(),
        "real_validation_projects": _real_validation_projects(),
        "accepted_review_boundaries": _accepted_review_boundaries(),
        "next_promotion_gates": _next_promotion_gates(),
        "stability_criteria": "docs/adapters/fabric.md",
        "evidence_manifests": [
            "docs/reports/fabric-usgs-rest-e2e-smoke.json",
            "docs/reports/fabric-stable-surface-evidence.json",
            "docs/reports/fabric-platform-parity.json",
            "docs/reports/fabric-source-expansion-stable-scope-decision.json",
            "docs/reports/fabric-project-deploy-smoke.json",
            "docs/reports/fabric-onelake-data-access-role-smoke.json",
            "docs/reports/fabric-onelake-row-column-policy-smoke.json",
            "docs/reports/fabric-deployment-pipeline-read-probe.json",
            "docs/reports/fabric-deployment-pipeline-lifecycle-smoke.json",
            "docs/reports/fabric-deployment-pipeline-stage-promotion-smoke.json",
            "docs/reports/fabric-http-json-source-smoke.json",
            "docs/reports/fabric-http-csv-source-smoke.json",
            "docs/reports/fabric-http-text-source-smoke.json",
            "docs/reports/fabric-lakehouse-text-source-smoke.json",
            "docs/reports/fabric-lakehouse-file-formats-source-smoke.json",
            "docs/reports/fabric-onelake-shortcut-source-smoke.json",
            "docs/reports/fabric-auth-rest-source-smoke.json",
            "docs/reports/fabric-auth-rest-variants-source-smoke.json",
            "docs/reports/fabric-auth-rest-oauth-source-smoke.json",
            "docs/reports/fabric-auth-http-json-source-smoke.json",
            "docs/reports/fabric-auth-http-json-variants-source-smoke.json",
            "docs/reports/fabric-auth-http-csv-variants-source-smoke.json",
            "docs/reports/fabric-auth-http-text-basic-source-smoke.json",
            "docs/reports/fabric-auth-http-text-bearer-source-smoke.json",
            "docs/reports/fabric-auth-http-text-api-key-source-smoke.json",
            "docs/reports/fabric-sqlserver-jdbc-source-smoke.json",
            "docs/reports/fabric-postgres-jdbc-source-smoke.json",
            "docs/reports/fabric-azure-blob-source-smoke.json",
            "docs/reports/fabric-private-azure-blob-source-smoke.json",
            "docs/reports/fabric-external-azure-blob-shortcut-source-smoke.json",
            "docs/reports/fabric-adls-shortcut-source-smoke.json",
            "docs/reports/fabric-gcs-shortcut-source-smoke.json",
            "docs/reports/fabric-external-s3-shortcut-source-smoke.json",
            "docs/reports/fabric-s3-compatible-shortcut-source-smoke.json",
            "docs/reports/fabric-iceberg-table-shortcut-source-smoke.json",
            "docs/reports/fabric-adls-iceberg-table-shortcut-source-smoke.json",
            "docs/reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json",
            "docs/reports/fabric-confluent-kafka-bounded-source-smoke.json",
            "docs/reports/fabric-confluent-kafka-available-now-source-smoke.json",
            "docs/reports/fabric-eventhubs-kafka-available-now-source-smoke.json",
        ],
    }


def _gates() -> list[dict[str, str]]:
    return [
        {"id": "F1", "name": "package", "status": "PASS"},
        {"id": "F2", "name": "environment binding", "status": "PASS"},
        {"id": "F3", "name": "notebook-first runtime architecture", "status": "PASS"},
        {"id": "F4", "name": "public REST bronze-to-gold E2E", "status": "PASS"},
        {"id": "F5", "name": "control-table evidence", "status": "PASS"},
        {"id": "F6", "name": "quality and failure evidence", "status": "PASS"},
        {"id": "F7", "name": "core write modes", "status": "PASS"},
        {"id": "F8", "name": "hash-diff upsert", "status": "PASS"},
        {"id": "F9", "name": "historical SCD2", "status": "PASS"},
        {"id": "F10", "name": "snapshot reconciliation", "status": "PASS"},
        {"id": "F11", "name": "source expansion", "status": "PASS"},
        {"id": "F12", "name": "governance apply mode", "status": "PASS"},
        {"id": "F13", "name": "deployment promotion", "status": "PASS"},
        {"id": "F14", "name": "contract parity report", "status": "PASS"},
    ]


def _real_validation_projects() -> list[dict[str, str]]:
    return [
        {"name": "fabric_usgs_rest_medallion", "status": "PASS"},
        {"name": "fabric_stable_surface_sql_suite", "status": "PASS"},
        {"name": "fabric_http_json_source_expansion", "status": "PASS"},
        {"name": "fabric_http_csv_source_expansion", "status": "PASS"},
        {"name": "fabric_http_text_source_expansion", "status": "PASS"},
        {"name": "fabric_lakehouse_text_source_expansion", "status": "PASS"},
        {"name": "fabric_lakehouse_file_formats_source_expansion", "status": "PASS"},
        {"name": "fabric_onelake_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_authenticated_rest_source_expansion", "status": "PASS"},
        {"name": "fabric_authenticated_rest_variants_source_expansion", "status": "PASS"},
        {"name": "fabric_authenticated_rest_oauth_source_expansion", "status": "PASS"},
        {"name": "fabric_authenticated_http_json_source_expansion", "status": "PASS"},
        {"name": "fabric_authenticated_http_json_variants_source_expansion", "status": "PASS"},
        {"name": "fabric_authenticated_http_csv_variants_source_expansion", "status": "PASS"},
        {"name": "fabric_endpoint_enforced_http_text_basic_source_expansion", "status": "PASS"},
        {"name": "fabric_endpoint_enforced_http_text_bearer_source_expansion", "status": "PASS"},
        {"name": "fabric_endpoint_enforced_http_text_api_key_source_expansion", "status": "PASS"},
        {"name": "fabric_sqlserver_jdbc_source_expansion", "status": "PASS"},
        {"name": "fabric_postgres_jdbc_source_expansion", "status": "PASS"},
        {"name": "fabric_azure_blob_source_expansion", "status": "PASS"},
        {"name": "fabric_private_azure_blob_source_expansion", "status": "PASS"},
        {"name": "fabric_external_azure_blob_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_adls_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_gcs_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_external_s3_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_s3_compatible_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_iceberg_table_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_adls_iceberg_table_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_gcs_iceberg_table_shortcut_source_expansion", "status": "PASS"},
        {"name": "fabric_confluent_kafka_bounded_source_expansion", "status": "PASS"},
        {"name": "fabric_confluent_kafka_available_now_source_expansion", "status": "PASS"},
        {"name": "fabric_eventhubs_kafka_available_now_source_expansion", "status": "PASS"},
        {"name": "fabric_governance_review_evidence", "status": "PASS"},
        {"name": "fabric_onelake_data_access_role_apply", "status": "PASS"},
        {"name": "fabric_onelake_row_column_policy_apply", "status": "PASS"},
        {"name": "fabric_project_deploy_only_promotion", "status": "PASS"},
        {"name": "fabric_deployment_pipeline_read_probe", "status": "PASS"},
        {"name": "fabric_deployment_pipeline_lifecycle", "status": "PASS"},
        {"name": "fabric_deployment_pipeline_stage_promotion", "status": "PASS"},
    ]


def _accepted_review_boundaries() -> list[dict[str, str]]:
    return [
        {
            "code": "FABRIC_AUTHENTICATED_HTTP_REVIEW",
            "area": "authenticated REST and HTTP file sources",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "Public HTTP JSON, CSV and text are validated. Authenticated REST Basic, bearer token, API-key and OAuth plus authenticated HTTP JSON and HTTP CSV Basic, bearer token and API-key with Key Vault placeholder auth are validated. Endpoint-enforced Basic, bearer-scheme and API-key auth are validated for HTTP text. OAuth for HTTP-file sources is not part of the current source vocabulary and is excluded from this stable-final claim.",
        },
        {
            "code": "FABRIC_SOURCE_EXPANSION_REVIEW",
            "area": "remaining shortcut object storage variants, Delta Sharing, direct-catalog Iceberg variants and native Fabric streaming modes",
            "decision": "EXCLUDED_FROM_STABLE_FINAL",
            "reason": "Lakehouse text, ORC, Avro and XML files, internal OneLake shortcut reads, SQL Server JDBC, PostgreSQL JDBC, public Azure Blob CSV, direct private Azure Blob CSV with a Key Vault-backed storage account key, external Azure Blob shortcut reads through a Fabric cloud connection, external ADLS Gen2 shortcut reads through a Fabric cloud connection, external Google Cloud Storage shortcut reads through a Fabric cloud connection, external Amazon S3 and S3-compatible shortcut reads through Fabric cloud connections, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads, bounded Confluent Kafka replay, Confluent Kafka available-now catch-up and Azure Event Hubs Kafka-compatible available-now catch-up are validated. Native Event Hubs/Fabric Real-Time streaming, private-network shortcut variants, managed identity/OAuth object-storage access, Delta Sharing and direct-catalog Iceberg variants remain review-required and are excluded from the notebook-first stable-final claim. Additional JDBC dialects are intentionally outside this F11 promotion batch.",
        },
        {
            "code": "FABRIC_GOVERNANCE_APPLY_REVIEW",
            "area": "Fabric/Purview metadata and access-policy apply mode",
            "decision": "ACCEPTED_STABLE_SCOPE",
            "reason": "Operations, annotations and access review evidence is validated. The adapter now renders and can execute explicit Fabric-native workspace role assignment, sensitivity-label and OneLake data access role apply steps when contracts provide Fabric IDs. Live Fabric evidence proves OneLake role create/list/delete for a Path=* and Action=Read policy with cleanup, plus row and column constraints against a Fabric-resolved Lakehouse table. Arbitrary ContractForge row-filter functions are not auto-translated to OneLake SQL predicates; contracts must declare explicit Fabric-native OneLake policy payloads for apply mode.",
        },
        {
            "code": "FABRIC_DEPLOYMENT_PROMOTION_REVIEW",
            "area": "project deployment, Git integration and deployment pipelines",
            "decision": "ACCEPTED_STABLE_SCOPE",
            "reason": "Generated Notebook deployment is validated. The adapter renders deterministic project deployment manifests and exposes deploy-project for deploy-only Notebook promotion without running notebooks. Live deployment-pipeline read, create/list/delete lifecycle and stage-to-stage Notebook content promotion probes succeeded with cleanup. Data Factory lifecycle promotion and Git integration remain outside the current notebook-first stable scope.",
        },
    ]


def _next_promotion_gates() -> list[dict[str, str]]:
    return []
