# Control Table Parity

## Purpose

Control tables are a fundamental ContractForge evidence contract.

The core name is still **evidence model**, but adapters should preserve the ContractForge control-table vocabulary wherever the platform can support it. Platform adapters may persist the data as Delta tables, Iceberg tables, BigQuery tables, Snowflake audit tables, Fabric Lakehouse tables, or object-store artifacts, but the semantic fields below are the canonical audit surface.

This parity spec defines:

- canonical evidence/control tables
- canonical column groups from the current ContractForge implementation
- platform storage equivalence
- portability status for fields that are portable, adapter-specific, review-required, or unsupported

For the dense column-by-column mapping to each platform's native evidence source (Databricks, AWS, GCP, Snowflake, Fabric), see the [Evidence mapping matrix](evidence-mapping-matrix.md). For a Snowflake-specific, official-doc-backed mapping of Core parameters and control-table fields, see [Snowflake capability and evidence parity](snowflake-capability-parity.md).

## Status Legend

| Status | Meaning |
| --- | --- |
| `PORTABLE` | Field has the same ContractForge meaning across platforms. |
| `ADAPTER_MAPPED` | Field is portable in meaning but the adapter must translate platform-native values. |
| `REVIEW_REQUIRED` | Field can be captured, but equivalence depends on platform design or runtime integration. |
| `PLATFORM_SPECIFIC` | Field is useful evidence but only has native meaning on some platforms. |
| `OPTIONAL` | Field should be captured when available; plans must not depend on it. |

## Canonical Tables

| ContractForge table | Evidence concept | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- | --- |
| `ctrl_ingestion_runs` | Run-level contract execution evidence. | Delta table. | Iceberg/Glue table or S3 audit dataset. | BigQuery table or GCS audit dataset. | Audit table. | Lakehouse table. |
| `ctrl_ingestion_state` | Last successful state and watermark per target. | Delta table. | DynamoDB/Iceberg/S3 state. | BigQuery/Firestore/GCS state. | Audit/state table. | Lakehouse table. |
| `ctrl_ingestion_quality` | Quality rule results. | Delta table. | Iceberg/Glue table. | BigQuery table. | Audit table. | Lakehouse table. |
| `ctrl_ingestion_quarantine` | Quarantined record reference or payload pointer. | Delta table plus secured payload location. | S3 reference plus table metadata. | GCS reference plus BigQuery metadata. | Stage/table reference. | OneLake/Lakehouse reference. |
| `ctrl_ingestion_locks` | Best-effort target lock/idempotency guard. | Delta MERGE state. | DynamoDB or conditional object/table lock. | Firestore/BigQuery/GCS lock. | Table lock row/task state. | Lakehouse/pipeline state. |
| `ctrl_ingestion_errors` | Error and stack trace evidence. | Delta table. | Iceberg/Glue/S3 audit. | BigQuery/GCS audit. | Audit table. | Lakehouse table. |
| `ctrl_ingestion_schema_changes` | Detected/applied schema drift. | Delta table. | Catalog/table audit. | BigQuery/Data Catalog audit. | Information schema/audit table. | Lakehouse/Purview audit. |
| `ctrl_ingestion_streams` | Bounded or available-now stream run summary. | Delta table. | Glue/EMR streaming or bookmark audit. | Dataflow/Dataproc audit. | REVIEW_REQUIRED. | Fabric event/pipeline audit. |
| `ctrl_ingestion_lineage` | Lineage event persistence. | Delta table with OpenLineage payload. | OpenLineage/S3/Iceberg. | Dataplex/OpenLineage/BigQuery. | OpenLineage/audit table. | Purview/Lakehouse audit. |
| `ctrl_ingestion_annotations` | Catalog annotation application evidence. | Delta table plus Unity Catalog SQL evidence. | Glue/Lake Formation tag evidence. | Dataplex/Data Catalog evidence. | COMMENT/TAG evidence. | Purview/Fabric metadata evidence. |
| `ctrl_ingestion_access` | Access/governance application evidence. | Delta table plus Unity Catalog SQL evidence. | Lake Formation/IAM evidence. | IAM/BigQuery policy evidence. | GRANT/policy evidence. | Fabric/Purview permission evidence. |
| `ctrl_ingestion_operations` | Ownership, SLA and operational metadata. | Delta table. | Evidence table/artifact. | Evidence table/artifact. | Audit table. | Lakehouse table. |
| `ctrl_ingestion_explain` | Runtime execution plan diagnostics. | Spark explain text. | Glue/EMR/Spark explain. | BigQuery/Dataflow/Dataproc plan evidence. | Query profile/EXPLAIN evidence. | Pipeline/query diagnostics. |
| `ctrl_ingestion_cost` | Operational cost and throughput signals. | DBU-derived estimates. | DPU/EMR/Step Functions/bytes estimates. | Slot/Dataflow/Dataproc estimates. | Warehouse credit estimates. | Capacity/CU estimates. |
| `ctrl_ingestion_metadata` | Framework/control schema metadata or source metadata. | Delta metadata table or source metadata evidence. | Audit metadata table/artifact. | Audit metadata table/artifact. | Audit metadata table. | Lakehouse metadata table. |
| `ctrl_deployment_versions` | Deploy-time contract, environment, manifest and artifact version ledger. | Delta table. | Iceberg/Glue table. | BigQuery table. | Audit table. | Lakehouse table. |

## Runs Table

`ctrl_ingestion_runs` is the primary audit table. It should be available for production plans on every platform adapter.

| Column group | Columns | Status | Notes |
| --- | --- | --- | --- |
| Run identity | `run_id`, `run_ts_utc`, `run_date`, `parent_run_id`, `run_group_id`, `master_job_id`, `master_run_id` | `PORTABLE` | `master_*` values are adapter-mapped from jobs, workflows, tasks, pipelines or orchestration context. |
| Contract target | `target_table`, `layer`, `mode` | `PORTABLE` | `target_table` should use the adapter's fully qualified target name when available. `mode` preserves values such as `append`, `upsert`, `hash_diff_upsert`, `historical` and `snapshot_reconcile_soft_delete`. |
| Source identity | `source_table`, `source_type`, `source_connector`, `source_name`, `source_system`, `source_provider`, `source_format`, `source_path` | `PORTABLE` | These fields preserve ContractForge source semantics; adapters map native connector identifiers into them. `source_system` is evidence metadata populated from canonical `source.system`; it is not a required physical target column. |
| Source detail JSON | `source_options_json`, `source_read_json`, `source_request_json`, `source_auth_json`, `source_pagination_json`, `source_response_json`, `source_incremental_json`, `source_limits_json`, `source_capabilities_json`, `source_metrics_json` | `ADAPTER_MAPPED` | JSON payloads must be redacted before persistence. Exact shape is adapter-owned. Connector details that do not have first-class run columns, such as `source_mode`, `source_connection`, `source_host`, `source_port`, `source_mailbox`, `source_object`, `source_url`, `source_environment_url`, `source_entity`, `source_index`, `source_table` and `source_query`, must be preserved in source metadata evidence when available. |
| Write engine | `write_engine_requested`, `write_engine_selected`, `write_engine_status`, `write_engine_reason`, `write_engine_fallback_policy` | `ADAPTER_MAPPED` | Critical for proving when native engines are used versus ContractForge algorithms. |
| Status and metrics | `status`, `rows_read`, `rows_written`, `rows_inserted`, `rows_updated`, `rows_deleted`, `rows_expired`, `rows_quarantined`, `metrics_source`, `operation_metrics_json`, `metrics_json` | `ADAPTER_MAPPED` | Physical metrics differ by platform; normalized ContractForge counters are required. `metrics_json` is retained as a compatibility evidence alias for existing ContractForge-style consumers; new adapter logic should prefer `operation_metrics_json`. |
| Watermark | `watermark_column`, `watermark_previous`, `watermark_current` | `PORTABLE` | Applies to batch incremental, bounded replay and available-now patterns. |
| Timing | `started_at_utc`, `finished_at_utc`, `duration_seconds`, `write_started_at_utc`, `write_finished_at_utc` | `PORTABLE` | UTC is required. |
| Quality and schema | `quality_status`, `schema_policy`, `schema_changes_json` | `PORTABLE` | Detailed records live in `quality` and `schema_changes`. |
| Contract metadata | `contract_description`, `contract_owner`, `contract_domain`, `contract_tags_json`, `contract_sla`, `operations_json`, `ownership_json` | `PORTABLE` | Comes from annotations/operations/access contracts when declared. |
| Runtime parameters | `runtime_parameters_json`, `stage_durations_json` | `ADAPTER_MAPPED` | Should include only reviewed, redacted runtime parameters. |
| Commit/version | `table_version_before`, `table_version_after`, `write_committed` | `PLATFORM_SPECIFIC` | Databricks Delta has native version numbers. Other adapters map to snapshot id, Iceberg snapshot id, BigQuery job id, Snowflake query id/version marker, or leave null with review note. |
| Error summary | `error_message` | `PORTABLE` | Short redacted message. Full detail belongs in `ctrl_ingestion_errors`. |
| Idempotency | `idempotency_key`, `idempotency_policy`, `skip_reason`, `skipped_by_run_id` | `PORTABLE` | Required for repeatable delivery. |
| Framework/runtime | `framework_version`, `ctrl_schema_version`, `runtime_type`, `engine_version`, `python_version` | `ADAPTER_MAPPED` | `engine_version` is optional outside Spark-based adapters. |
| Annotations | `annotations_status`, `annotations_result_json` | `PORTABLE` | Tracks annotation application result independently from write success. |

## State And Locks

| Table | Columns | Status | Notes |
| --- | --- | --- | --- |
| `ctrl_ingestion_state` | `target_table`, `watermark_column`, `watermark_value`, `last_success_at_utc`, `last_run_id`, `last_status`, `last_rows_written`, `last_error_message`, `parent_run_id`, `run_group_id`, `master_job_id`, `master_run_id`, `last_table_version`, `last_write_completed_at_utc`, `last_watermark_candidate`, `last_updated_at_utc` | `PORTABLE` with `PLATFORM_SPECIFIC` version marker | `last_table_version` (STRING) is the platform-neutral version marker: Delta version, Iceberg snapshot id, Lakehouse Delta version, or null (Snowflake/BigQuery). The native value is also kept in `operation_metrics_json`. |
| `ctrl_ingestion_locks` | `target_table`, `run_id`, `owner`, `acquired_at_utc`, `expires_at_utc`, `ttl_minutes`, `released_at_utc`, `status` | `ADAPTER_MAPPED` | Lock strength differs by platform. Treat as best-effort unless the adapter declares transactional lock support. |

## Quality And Quarantine

| Table | Columns | Status | Notes |
| --- | --- | --- | --- |
| `ctrl_ingestion_quality` | `run_id`, `target_table`, `rule_name`, `status`, `severity`, `failed_count`, `observed_value`, `checked_at_utc`, `message`, `details_json` | `PORTABLE` | `observed_value` carries the compact check result; `details_json` carries adapter-specific SQL/query evidence. |
| `ctrl_ingestion_quarantine` | `run_id`, `target_table`, `rule_name`, `error_reason`, `record_payload`, `record_ref`, `reason`, `quarantined_at_utc` | `ADAPTER_MAPPED` | For security, adapters may store `record_payload` as a reference instead of raw data. `record_ref` is the preferred pointer field; `record_payload` remains for Databricks evidence parity. |

## Errors And Schema Changes

| Table | Columns | Status | Notes |
| --- | --- | --- | --- |
| `ctrl_ingestion_errors` | `run_id`, `error_ts_utc`, `error_date`, `target_table`, `source_table`, `mode`, `status`, `error_type`, `error_class`, `error_message`, `stack_trace`, `occurred_at_utc`, `framework_version`, `ctrl_schema_version`, `runtime_type`, `engine_version`, `python_version` | `PORTABLE` | Stack traces must be redacted and may be truncated by adapter policy. `error_class` captures structured platform classes when available. |
| `ctrl_ingestion_schema_changes` | `run_id`, `change_ts_utc`, `target_table`, `change_type`, `column_name`, `source_type`, `target_type`, `applied`, `details_json`, `payload_json`, `changed_at_utc`, `framework_version`, `ctrl_schema_version` | `PORTABLE` | Type names are adapter-normalized strings. `change_ts_utc`, `changed_at_utc`, `framework_version` and `ctrl_schema_version` are required evidence fields. `source_type` should be populated for `add_column` from the prepared/source schema when available. `payload_json` preserves the raw/adapter schema-change payload when richer than `details_json`. |

## Streaming And Bounded Replay

| Table | Columns | Status | Notes |
| --- | --- | --- | --- |
| `ctrl_ingestion_streams` | `stream_run_id`, `run_id`, `idempotency_key`, `idempotency_policy`, `skip_reason`, `skipped_by_stream_run_id`, `target_table`, `target_catalog`, `target_layer`, `runtime_entrypoint`, `source_type`, `source_path`, `trigger`, `checkpoint_location`, `status`, `started_at_utc`, `ended_at_utc`, `duration_seconds`, `batches_processed`, `total_rows_read`, `total_rows_written`, `total_rows_quarantined`, `batch_id`, `batch_metrics_json`, `captured_at_utc`, `framework_version`, `ctrl_schema_version`, `runtime_type`, `engine_version`, `python_version`, `error_message`, `master_job_id`, `master_run_id`, `parent_run_id`, `run_group_id` | `ADAPTER_MAPPED` | Portable for bounded/available-now semantics. Continuous streaming requires adapter-specific review. Batch fields support micro-batch reconciliation from child `ctrl_ingestion_runs` rows. |

## Lineage, Diagnostics And Cost

| Table | Columns | Status | Notes |
| --- | --- | --- | --- |
| `ctrl_ingestion_lineage` | `run_id`, `event_time_utc`, `event_type`, `target_table`, `source_table`, `namespace`, `producer`, `event_json` | `ADAPTER_MAPPED` | OpenLineage-compatible JSON is preferred when available. |
| `ctrl_ingestion_explain` | `run_id`, `target_table`, `source_table`, `mode`, `explain_format`, `plan_text`, `captured_at_utc` | `ADAPTER_MAPPED` | Format differs: Spark explain, BigQuery plan, Snowflake profile, Fabric pipeline/query plan. |
| `ctrl_ingestion_cost` | `run_id`, `target_table`, `signal_name`, `signal_value`, `payload_json`, `captured_at_utc` | `ADAPTER_MAPPED` | Cost is an operational signal, not billing reconciliation. |
| `ctrl_ingestion_metadata` | `component`, `framework_version`, `ctrl_schema_version`, `updated_at_utc` or `run_id`, `target_table`, `source_metadata_json`, `captured_at_utc` | `REVIEW_REQUIRED` | The metadata table tracks framework metadata. Adapter evidence may also store a redacted source metadata payload for connector observability; keep names explicit in adapter specs. |

## Annotations, Access And Operations

| Table | Columns | Status | Notes |
| --- | --- | --- | --- |
| `ctrl_ingestion_annotations` | `run_id`, `target_table`, `annotation_scope`, `annotation_type`, `column_name`, `key`, `previous_value`, `value`, `status`, `error_message`, `applied_sql`, `annotation_ts_utc`, `annotation_date`, `framework_version`, `ctrl_schema_version` | `ADAPTER_MAPPED` | Native metadata systems differ; applied artifact SQL/API payload must be captured when possible. |
| `ctrl_ingestion_access` | `access_run_id`, `run_id`, `target_table`, `access_type`, `principal`, `privilege`, `column_name`, `function_name`, `object_name`, `status`, `error_message`, `applied_sql`, `previous_value`, `new_value`, `mode`, `drift_policy`, `revoke_unmanaged`, `access_ts_utc`, `access_date`, `framework_version`, `ctrl_schema_version` | `ADAPTER_MAPPED` | Principal and privilege models differ by platform. Destructive drift reconciliation requires review. |
| `ctrl_ingestion_operations` | `run_id`, `target_table`, `criticality`, `expected_frequency`, `freshness_sla_minutes`, `alert_on_failure`, `alert_on_quality_fail`, `runbook_url`, `ownership_json`, `owners_json`, `groups_json`, `tags_json`, `status`, `recorded_at_utc`, `framework_version`, `ctrl_schema_version` | `PORTABLE` | Alert integration is review-required; the intent and evidence fields are portable. |

## Platform Persistence Rules

| Platform | Recommended persistence | Notes |
| --- | --- | --- |
| Databricks | Delta tables in `environment.evidence.catalog/schema`. | Preserve ContractForge table names. Delta versions may populate platform-specific version columns. |
| AWS | Iceberg tables registered in Glue, with optional S3 JSON artifacts for large payloads. | DynamoDB may be used for strong locks/state, but evidence should still be queryable. |
| GCP | BigQuery audit dataset, or GCS JSON artifacts plus BigQuery external/managed tables. | Dataplex/OpenLineage can supplement lineage but should not replace queryable evidence. |
| Snowflake | Audit schema tables. | Query IDs, streams/tasks and warehouse credit data map into runtime/cost payloads. |
| Fabric | Lakehouse tables in an evidence lakehouse/schema. | Purview/Fabric metadata can supplement annotations/access evidence. |

## Adapter Requirements

1. Production adapters must declare an evidence persistence strategy.
2. `ctrl_ingestion_runs` or an equivalent queryable run ledger is required for production plans.
3. Evidence writes must never silently drop ContractForge semantics.
4. Sensitive source/auth/runtime values must be redacted before persistence.
5. Platform-specific metrics must be normalized into ContractForge row counters where possible.
6. Version/runtime columns use platform-neutral names: `table_version_before`/`table_version_after` (STRING), `last_table_version` (STRING), `runtime_entrypoint`, `engine_version`. Each adapter maps its native value (Delta version, Iceberg snapshot id, BigQuery job id, etc.) into them and keeps the raw native value in `operation_metrics_json`.
7. Every adapter must document which canonical columns are native, mapped, null, or review-required.

## Research-Backed Platform Evidence Sources

The following sources define what adapters should read from each platform when filling control-table fields. These are not optional naming preferences; they are the concrete platform evidence surfaces the adapter should use when available.

| Platform | Runtime/run source | Write/version source | Metrics/cost source | Governance/annotation source | Lineage/diagnostics source |
| --- | --- | --- | --- | --- | --- |
| Databricks | Dynamic value references: `job.id`, `job.run_id`, `task.run_id`, `task.name`, `job.start_time.*`, `job.trigger.type`; system tables `system.lakeflow.job_run_timeline` and `system.lakeflow.job_task_run_timeline`. | Delta `DESCRIBE HISTORY` / table history: `version`, `timestamp`, `operation`, `operationParameters`, `operationMetrics`. | Delta `operationMetrics`; system billing usage with `usage_metadata.job_id` and `usage_metadata.job_run_id` when job compute/serverless attribution exists. | Unity Catalog comments, tags, grants, row filters and masks; adapter should persist applied SQL/API payloads. | OpenLineage event payloads, Spark explain text, Databricks system tables. |
| AWS | AWS Glue `JobRun`: `Id`, `PreviousRunId`, `StartedOn`, `CompletedOn`, `JobRunState`, `StateDetail`, `Arguments`, `Attempt`, `TriggerName`, `WorkerType`, `NumberOfWorkers`, `ExecutionClass`. | Iceberg snapshot id, Hudi commit instant, Redshift query id, Athena query execution id, or Glue job output commit metadata depending on adapter. | Glue `DPUSeconds`, `ExecutionTime`, `MaxCapacity`, `WorkerType`, `NumberOfWorkers`; CloudWatch metrics/logs; Athena/Redshift query stats when used. | Lake Formation `GrantPermissions`, `RevokePermissions`, data filters and CloudTrail events; Glue Catalog table/column parameters. | OpenLineage where configured, AWS Glue lineage-like metadata, CloudTrail, CloudWatch logs, Spark explain on Glue/EMR. |
| GCP | BigQuery `INFORMATION_SCHEMA.JOBS`: `job_id`, `parent_job_id`, `state`, `creation_time`, `start_time`, `end_time`, `user_email`, `job_type`, `statement_type`; Dataflow Job: `id`, `name`, `createTime`, `endTime`, `state`, `status`. | BigQuery job id / transaction id / destination table metadata; Iceberg/Delta/Hudi snapshot id on Dataproc if used. | BigQuery `total_bytes_processed`, `total_bytes_billed`, `total_slot_ms`, `total_modified_partitions`, DML stats; Dataflow job metrics. | BigQuery IAM, row access policies, policy tags, Dataplex/Data Catalog metadata. | Dataplex Data Lineage process/run/event model; BigQuery query plan and job statistics; Dataflow job details. |
| Snowflake | `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY`: `query_id`, `execution_status`, `start_time`, `end_time`, `error_code`, `error_message`, `query_tag`; `TASK_HISTORY`: `run_id`, `query_id`, `state`, `scheduled_time`, `completed_time`, `graph_run_group_id`. | `query_id`, `transaction_id`, stream/task metadata, table metadata; no Delta-style table version. | `QUERY_HISTORY` rows/bytes fields; `QUERY_ATTRIBUTION_HISTORY` credits via `query_id`, `parent_query_id`, `root_query_id`. | `TAG_REFERENCES`, `POLICY_REFERENCES`, grants/policies, masking and row access policy metadata. | `ACCESS_HISTORY` direct/base/modified objects, `QUERY_HISTORY` profile data, `EXPLAIN` output. |
| Fabric | Workspace Monitoring `ItemJobEventLogs`: `JobInstanceId`, `JobStatus`, `JobStartTime`, `JobEndTime`, `DurationMs`, `JobInvokeType`, `ItemId`, `ItemName`, `WorkspaceId`, `CapacityId`, `ExecutingPrincipalId`. | Lakehouse Delta version where accessible, Warehouse query/request id, pipeline/copy job run id. | Copy activity output: `dataRead`, `dataWritten`, files/rows copied, throughput and duration details; Capacity Metrics app CU/CPU/processing/memory signals. | Fabric permissions, Purview/Microsoft governance metadata, item metadata, sensitivity labels where available. | Monitoring hub, ItemJobEventLogs, pipeline activity input/output/error, Purview lineage where configured. |

## Runs Field Population Rules

The table below defines how each `ctrl_ingestion_runs` field should be populated by platform adapters.

| Field | ContractForge meaning | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- | --- |
| `run_id` | ContractForge execution id for one target write. | Prefer `task.run_id`; use generated UUID for local/manual runs. | Glue `JobRun.Id` or generated UUID inside EMR/Lambda. | BigQuery `job_id`, Dataflow `id`, or generated UUID for multi-step adapters. | `query_id` for single SQL write; generated orchestration id for multi-query/task runs. | `JobInstanceId` or generated id for notebook/lakehouse execution. |
| `run_ts_utc` | Event timestamp for ledger row creation. | Adapter UTC clock; may use `job.start_time.*` for scheduled job start. | Adapter UTC clock or Glue `StartedOn`. | Adapter UTC clock or BigQuery/Dataflow start time. | Adapter UTC clock or `QUERY_HISTORY.start_time`. | Adapter UTC clock or `JobStartTime`. |
| `run_date` | UTC date partition for run evidence. | Date from `run_ts_utc`. | Date from `run_ts_utc`. | Date from `run_ts_utc`. | Date from `run_ts_utc`. | Date from `run_ts_utc`. |
| `runtime_entrypoint` | Runtime artifact name/path. | `task.notebook_path` when notebook task; otherwise task/job name. | Glue job name, EMR step name, Lambda/function name. | Dataflow job name, BigQuery job label, Composer task id. | Task name, procedure name, or query tag value. | `ItemName` for pipeline/dataflow/notebook item. |
| `layer` | Contract target layer. | From core target/layer. | From core target/layer. | From core target/layer. | From core target/layer. | From core target/layer. |
| `source_table` | Main source object when table-like. | UC/Hive table, path, or view name. | Glue Catalog table, S3 prefix, Redshift table, JDBC table. | BigQuery table, GCS path, Dataflow source, JDBC table. | Snowflake table/stage/external table/source object. | Lakehouse/Warehouse table, OneLake path, pipeline source. |
| `source_type` | ContractForge source type. | Contract `source.type`, e.g. `incremental_files`, `jdbc`, `delta_share`. | Same contract value, not AWS product name. | Same contract value, not GCP product name. | Same contract value. | Same contract value. |
| `source_connector` | Logical connector/system. | Connector name or Databricks native target such as Lakeflow Connect. | Glue connector, AppFlow, DMS, JDBC driver, S3. | BigQuery/Dataflow connector, Datastream, JDBC. | Snowflake connector/stage/external access integration. | Dataflow Gen2 connector, Data Pipeline connector, shortcut. |
| `source_name` | Readable source name. | Contract source name or table/path. | Glue connection/source name, S3 prefix, table name. | BigQuery table/job source, GCS prefix, Dataflow source. | Stage/table/query tag source name. | Fabric item/source name. |
| `source_system` | Business/source-system identifier for observability. | Canonical `source.system` or source metadata. | Canonical `source.system` or native source system label. | Canonical `source.system` or native source system label. | Canonical `source.system` or native source system label. | Canonical `source.system` or native source system label. |
| `source_provider` | Provider family for source. | `databricks`, `aws`, `azure`, `gcp`, `snowflake`, or SaaS system. | `aws`, `jdbc`, SaaS system. | `gcp`, `jdbc`, SaaS system. | `snowflake`, `external_stage`, SaaS system. | `fabric`, `azure`, SaaS system. |
| `source_format` | Data format/protocol. | Spark reader format, JDBC, Delta Sharing, Lakeflow native. | Glue format, JDBC, Iceberg, Parquet/CSV/JSON. | BigQuery, GCS format, Dataflow connector format. | Table/stage file format, SQL, Snowpipe/native. | Lakehouse format, Dataflow connector format. |
| `source_path` | Path, URL, topic, table or object locator. | S3/ADLS/GCS/Volumes path, table, topic, URL. | S3 URI, Glue table, Kafka topic, JDBC URL/table. | GCS URI, BigQuery table, Pub/Sub topic, JDBC URL/table. | Stage path, table, query, external location. | OneLake path, item id, URL, table, shortcut. |
| `source_options_json` | Redacted source options. | Spark read/cloudFiles/JDBC options. | Glue connection_options/additional_options. | BigQuery/Dataflow/Dataproc read options. | COPY/connector/stage options. | Pipeline/Dataflow Gen2/copy options. |
| `source_read_json` | Read plan details. | Reader format/load/table/query and projection. | Glue DynamicFrame/Spark read plan. | BigQuery query/load/read session or Dataflow source. | SQL/COPY/stage read plan. | Copy activity source/input payload. |
| `source_request_json` | HTTP/API request metadata. | HTTP file or REST review request, redacted. | AppFlow/API Gateway/Lambda/request metadata. | Cloud Run/API/Dataflow request metadata. | External function/API integration metadata. | Pipeline connector request metadata. |
| `source_auth_json` | Secret/auth reference evidence. | Secret scope/key, UC connection, Databricks Connection. | IAM role, Glue Connection, Secrets Manager ARN. | Service account, Secret Manager ref, connection profile. | Secret/integration/role reference. | Connection, Key Vault/credential reference. |
| `source_pagination_json` | API pagination plan. | HTTP/API review metadata. | AppFlow/custom API pagination metadata. | Dataflow/API pagination metadata. | External function/native connector pagination metadata. | Dataflow Gen2/pipeline connector pagination metadata. |
| `source_response_json` | API response/shape metadata. | HTTP status/content metadata, redacted. | API response metadata, redacted. | API response metadata, redacted. | API/external function response metadata. | Pipeline activity output response metadata. |
| `source_incremental_json` | Watermark/checkpoint/bookmark state. | Auto Loader checkpoint/schema location, watermark candidate. | Glue bookmark keys, `transformation_ctx`, `JobBookmarkEntry`. | BigQuery watermark, Dataflow checkpoint/state, Datastream offset. | Stream/task high watermark, query predicate, external table pipe status. | Pipeline/Dataflow incremental refresh or event trigger state. |
| `source_limits_json` | Read limits/guardrails. | max files/bytes/records/timeouts. | Glue job limits, bounded read limits. | Dataflow/BigQuery limit settings. | Warehouse timeout/statement timeout, row/file limits. | Pipeline timeout, copy limits. |
| `source_capabilities_json` | Adapter-declared source capabilities. | bounded/incremental/native_passthrough/cloudFiles flags. | Glue bookmark/native connector/Iceberg flags. | BigQuery/Dataflow/Dataplex flags. | stage/stream/task/native connector flags. | Dataflow Gen2/pipeline/copy capability flags. |
| `source_metrics_json` | Source-side observed metrics. | input files, bytes, batch id, Spark source progress. | Glue/Spark source metrics, S3 object counts. | BigQuery/Dataflow source counters. | query/source scan metrics. | Copy output source metrics. |
| `target_table` | Fully qualified target name. | UC three-part table or path-backed target. | Glue database/table, S3/Iceberg identifier, Redshift table. | BigQuery `project.dataset.table` or lake table. | `database.schema.table`. | Lakehouse/Warehouse table or OneLake path. |
| `mode` | ContractForge write mode. | Exact contract mode. | Exact contract mode. | Exact contract mode. | Exact contract mode. | Exact contract mode. |
| `write_engine_requested` | User/adaptor requested engine. | `delta_sql`, `lakeflow_auto_cdc`, `contractforge_algorithm`, etc. | `glue_spark`, `athena`, `emr`, `iceberg`, `appflow`, etc. | `bigquery_sql`, `dataflow`, `dataproc`, etc. | `snowflake_sql`, `snowpark`, `task`, etc. | `fabric_pipeline`, `dataflow_gen2`, `lakehouse_sql`, etc. |
| `write_engine_selected` | Engine actually used. | Strategy result engine. | Strategy result engine. | Strategy result engine. | Strategy result engine. | Strategy result engine. |
| `write_engine_status` | Selection status. | native/algorithm/fallback/review/unsupported. | Same normalized vocabulary. | Same normalized vocabulary. | Same normalized vocabulary. | Same normalized vocabulary. |
| `write_engine_reason` | Why engine was selected. | Strategy reason, including Delta/Lakeflow blockers. | Capability/semantic reason. | Capability/semantic reason. | Capability/semantic reason. | Capability/semantic reason. |
| `write_engine_fallback_policy` | Whether fallback was allowed. | Contract/environment fallback policy. | Contract/environment fallback policy. | Contract/environment fallback policy. | Contract/environment fallback policy. | Contract/environment fallback policy. |
| `status` | ContractForge run outcome. | Map from task result, exception, quality/write status. | Map from `JobRunState` plus adapter validation. | Map from job state/error result. | Map from `execution_status`/task `state`. | Map from `JobStatus`. |
| `rows_read` | Logical input rows. | Spark count/source progress. | Glue/Spark metrics or source count. | BigQuery/Dataflow counters. | Query profile/result metrics when available. | Copy output rows read/copied when available. |
| `rows_written` | Logical rows written to target. | Normalized Delta metrics. | Iceberg/Hudi/SQL/Spark metrics. | BigQuery DML stats/Dataflow counters. | `rows_inserted + rows_updated + rows_deleted` as applicable, with CTAS caveats. | Copy activity rows copied or Lakehouse write metrics. |
| `rows_inserted` | Inserted row count. | Delta `operationMetrics` insert keys normalized. | Engine-specific insert metrics. | BigQuery DML `insertedRowCount`. | `QUERY_HISTORY.rows_inserted`. | Copy/Lakehouse write output when available. |
| `rows_updated` | Updated current rows. | Delta merge update metrics normalized. | Engine-specific update metrics. | BigQuery DML `updatedRowCount`. | `QUERY_HISTORY.rows_updated`. | REVIEW_REQUIRED unless SQL endpoint exposes update metrics. |
| `rows_deleted` | Deleted rows. | Delta delete/merge delete metrics. | Engine-specific delete metrics. | BigQuery DML `deletedRowCount`. | `QUERY_HISTORY.rows_deleted`. | REVIEW_REQUIRED unless SQL endpoint exposes delete metrics. |
| `rows_expired` | Historical rows expired by historical. | Logical ContractForge historical count, not just physical update count. | Logical adapter-computed count. | Logical adapter-computed count. | Logical adapter-computed count. | Logical adapter-computed count. |
| `rows_quarantined` | Rows withheld by quality/quarantine. | Quality/quarantine result count. | Quality/quarantine result count. | Quality/quarantine result count. | Quality/quarantine result count. | Quality/quarantine result count. |
| `watermark_column` | Watermark column/key. | Contract watermark. | Glue bookmark key or contract watermark. | Contract/BigQuery/Dataflow watermark. | Contract stream/task watermark. | Pipeline/Dataflow watermark. |
| `watermark_previous` | Previous successful high-watermark. | `ctrl_ingestion_state` or checkpoint-derived value. | Glue bookmark/adapter state. | BigQuery/adapter state. | Stream/task/adapter state. | Pipeline/Dataflow/adapter state. |
| `watermark_current` | New committed high-watermark. | Candidate committed after successful write. | Bookmark or adapter candidate after success. | Candidate after success. | Candidate after success. | Candidate after success. |
| `started_at_utc` | Run start. | `job.start_time.*`, system table start, or adapter clock. | Glue `StartedOn`. | BigQuery/Dataflow start time. | `QUERY_HISTORY.start_time` or task query start. | `JobStartTime`. |
| `finished_at_utc` | Run finish. | system table period end or adapter clock. | Glue `CompletedOn`. | BigQuery/Dataflow end time. | `QUERY_HISTORY.end_time` or task completed time. | `JobEndTime`. |
| `duration_seconds` | Elapsed seconds. | Difference or system-table duration. | Glue `ExecutionTime` or timestamp difference. | Timestamp difference or Dataflow/BigQuery duration. | `total_elapsed_time / 1000` or timestamp difference. | `DurationMs / 1000`. |
| `quality_status` | Aggregate quality status. | ContractForge quality result. | ContractForge quality result. | ContractForge quality result. | ContractForge quality result. | ContractForge quality result. |
| `schema_policy` | Contract schema policy. | Exact contract value. | Exact contract value. | Exact contract value. | Exact contract value. | Exact contract value. |
| `schema_changes_json` | Schema drift/evolution evidence. | Delta/table schema diff payload. | Glue Catalog/Iceberg schema diff. | BigQuery/Data Catalog schema diff. | INFORMATION_SCHEMA/schema diff. | Lakehouse/Purview schema diff. |
| `stage_durations_json` | Internal stage timing. | Spark/job prep/write/evidence timings. | Glue/EMR stage timings. | BigQuery/Dataflow stages/timeline. | Query profile/task timings. | Pipeline activity duration breakdown. |
| `contract_description` | Business description. | From annotations/operations contract. | Same. | Same. | Same. | Same. |
| `contract_owner` | Contract owner. | From operations/annotations/access contract. | Same. | Same. | Same. | Same. |
| `contract_domain` | Business data domain. | From core target/domain. | Same. | Same. | Same. | Same. |
| `contract_tags_json` | Contract tags. | From annotations/operations contract. | Same. | Same. | Same. | Same. |
| `contract_sla` | SLA summary. | From operations contract. | Same. | Same. | Same. | Same. |
| `runtime_parameters_json` | Runtime parameters after redaction. | Job/task parameters, env Databricks params. | Glue arguments, EMR step args, Lambda env refs. | BigQuery job labels/config, Dataflow params. | Query tag/session params/task config. | Pipeline parameters, item config. |
| `operation_metrics_json` | Raw platform operation metrics. | Delta `operationMetrics`, Spark progress, job system metadata. | Glue/EMR/Athena/Redshift metrics. | BigQuery job stats, Dataflow metrics. | QUERY_HISTORY/profile metrics. | Copy output/ItemJobEventLogs/Capacity metrics. |
| `write_started_at_utc` | Target write start. | Adapter write timer. | Adapter write timer. | Adapter write timer. | Query start time for write statement. | Activity start time for write/copy. |
| `write_finished_at_utc` | Target write finish. | Adapter write timer. | Adapter write timer. | Adapter write timer. | Query end time for write statement. | Activity end time for write/copy. |
| `table_version_before` | Version marker before write. | Delta table version before write. | Iceberg snapshot id before write if applicable; otherwise null. | Snapshot/version marker if applicable; otherwise null. | Null or transaction/query marker in `operation_metrics_json`. | Lakehouse Delta version if available; otherwise null. |
| `table_version_after` | Version marker after write. | Delta table version after write. | Iceberg snapshot id after write if applicable; otherwise null. | Snapshot/version marker if applicable; otherwise null. | Null or transaction/query marker in `operation_metrics_json`. | Lakehouse Delta version if available; otherwise null. |
| `write_committed` | Whether target write committed. | True after successful Delta/Lakeflow commit. | True after engine reports success and evidence persisted. | True after job success and target commit. | True after successful transaction/query. | True after pipeline/copy/lakehouse success. |
| `error_message` | Short redacted error. | Normalized Spark/Delta/SQL error. | Glue/CloudWatch/engine error. | BigQuery/Dataflow error result/status. | `error_message` from QUERY_HISTORY/TASK_HISTORY. | Pipeline/activity error. |
| `parent_run_id` | Parent/orchestrator run. | `job.run_id` for task rows or `parent_run_id` where provided. | Glue `PreviousRunId`, workflow run id, Step Functions execution id. | BigQuery `parent_job_id`, Composer DAG run id. | `parent_query_id`, task graph parent, or orchestration id. | Parent pipeline run or triggering item/job id. |
| `run_group_id` | Correlation group across related runs. | Job run id or repair/group id. | Glue workflow run id / Step Functions execution id. | Composer DAG run / Dataflow pipeline group / generated id. | `graph_run_group_id` for tasks or generated id. | Workspace/pipeline run correlation id. |
| `master_job_id` | Stable orchestrator/job definition id. | `job.id`. | Glue job name/ARN, Step Functions state machine ARN. | Dataflow job name/template, Composer DAG id, BigQuery job config label. | Task name/id, procedure name, warehouse job tag. | Fabric `ItemId` / pipeline item id. |
| `master_run_id` | Top-level run id. | `job.run_id`. | Glue JobRun.Id/workflow run id. | BigQuery job id / Dataflow id / Composer DAG run id. | Task `run_id`, root query id, graph run group id. | `JobInstanceId`. |
| `idempotency_key` | ContractForge replay guard key. | Adapter-generated from contract/source window/watermark. | Glue bookmark key, source window, or adapter-generated key. | BigQuery/Dataflow source window or generated key. | Query tag/source window or generated key. | Pipeline trigger/window or generated key. |
| `idempotency_policy` | How duplicate runs are handled. | Contract/environment policy. | Contract/environment policy. | Contract/environment policy. | Contract/environment policy. | Contract/environment policy. |
| `skip_reason` | Why write was skipped. | Existing successful idempotent run, no new files, no changes. | Glue bookmark/no new input/idempotent run. | No source changes/idempotent run. | No stream rows/no source changes/idempotent run. | No trigger data/no source changes/idempotent run. |
| `skipped_by_run_id` | Prior run that satisfied request. | Prior ContractForge run id. | Prior ContractForge run id. | Prior ContractForge run id. | Prior ContractForge run id. | Prior ContractForge run id. |
| `metrics_source` | Source of row/cost metrics. | `delta_history`, `spark_progress`, `logical`. | `glue_jobrun`, `spark_metrics`, `logical`. | `bigquery_job`, `dataflow_metrics`, `logical`. | `query_history`, `query_profile`, `logical`. | `copy_output`, `item_job_event_logs`, `logical`. |
| `framework_version` | ContractForge adapter/core version. | Adapter package version. | Adapter package version. | Adapter package version. | Adapter package version. | Adapter package version. |
| `ctrl_schema_version` | Control schema version. | Databricks evidence schema version. | AWS evidence schema version. | GCP evidence schema version. | Snowflake evidence schema version. | Fabric evidence schema version. |
| `runtime_type` | Runtime classifier. | `databricks_serverless`, `databricks_classic`, etc. | `aws_glue`, `emr_serverless`, `lambda`, etc. | `bigquery`, `dataflow`, `dataproc`, etc. | `snowflake_warehouse`, `snowpark`, `task`. | `fabric_pipeline`, `dataflow_gen2`, `lakehouse`. |
| `engine_version` | Spark runtime version when present. | Spark version for Spark/Databricks runtime. | Glue/EMR Spark version if Spark-based. | Dataproc Spark version if Spark-based. | Null unless Snowpark exposes compatible runtime detail. | Null unless Spark notebook/runtime exposes it. |
| `python_version` | Python runtime version when present. | Python version from runtime. | Python version from Glue/EMR/Lambda. | Python version from Dataflow/Dataproc. | Python connector/Snowpark runtime when applicable. | Python notebook/runtime version when applicable. |
| `annotations_status` | Annotation application aggregate. | Unity Catalog application result. | Glue/Lake Formation/Data Catalog metadata application result. | BigQuery/Dataplex metadata application result. | COMMENT/TAG application result. | Fabric/Purview metadata application result. |
| `annotations_result_json` | Annotation step payloads. | Applied SQL/API payloads and errors. | Glue/LF payloads and CloudTrail refs. | BigQuery/Dataplex payloads. | COMMENT/TAG payloads. | Fabric/Purview payloads. |
| `ownership_json` | Ownership evidence. | UC owner plus operations owners. | Glue/LF owner metadata plus operations owners. | IAM/Data Catalog/Dataplex owners. | TABLE_OWNER/role plus operations owners. | Workspace/item owner plus operations owners. |
| `operations_json` | Operational metadata evidence. | Operations contract normalized JSON. | Same. | Same. | Same. | Same. |

## Non-Runs Field Population Rules

| Table | Field | ContractForge meaning | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ctrl_ingestion_state` | `target_table` | State key. | Qualified table. | Glue/Iceberg/S3 target id. | BigQuery/lake target id. | `database.schema.table`. | Lakehouse/Warehouse target id. |
| `ctrl_ingestion_state` | `watermark_column`, `watermark_value` | Last committed watermark. | Contract watermark/state table. | Glue bookmark or adapter state. | BigQuery/Dataflow state. | Stream/task/query watermark. | Pipeline/Dataflow state. |
| `ctrl_ingestion_state` | `last_success_at_utc`, `last_run_id`, `last_status`, `last_rows_written`, `last_error_message` | Last run summary. | From latest successful ContractForge run evidence. | Same. | Same. | Same. | Same. |
| `ctrl_ingestion_state` | `last_table_version`, `last_write_completed_at_utc`, `last_watermark_candidate` | Last platform version/write/watermark candidate. | Delta version and write timestamp. | Iceberg snapshot id or null. | Snapshot/job version marker or null. | Query/transaction marker in JSON; column may be null. | Lakehouse Delta version or null. |
| `ctrl_ingestion_locks` | `target_table`, `run_id`, `owner`, `acquired_at_utc`, `expires_at_utc`, `ttl_minutes`, `released_at_utc`, `status` | Best-effort lock lease. | Delta MERGE lock row. | DynamoDB conditional lock preferred; evidence mirror optional. | Firestore/Spanner/BigQuery lock or object lease. | Audit table row or task/session lock pattern. | Lakehouse/pipeline state lock. |
| `ctrl_ingestion_quality` | `rule_name`, `status`, `severity`, `failed_count`, `observed_value`, `checked_at_utc`, `message`, `details_json` | Quality result. | SQL/Spark result payload. | Glue/Spark/SQL result payload. | BigQuery/Dataflow result payload. | SQL/Snowpark result payload. | Pipeline/Dataflow/Lakehouse result payload. |
| `ctrl_ingestion_quarantine` | `rule_name`, `error_reason`, `record_payload`, `record_ref`, `reason`, `quarantined_at_utc` | Quarantine reference/payload. | Prefer secured Delta/path reference for payload. | Prefer S3 object reference. | Prefer GCS object or BigQuery reference. | Prefer stage/table reference. | Prefer OneLake/Lakehouse reference. |
| `ctrl_ingestion_errors` | `error_ts_utc`, `error_date`, `error_type`, `error_class`, `error_message`, `stack_trace`, `occurred_at_utc` | Full error evidence. | Spark/Delta/SQL normalized error. | Glue state detail/CloudWatch error. | BigQuery/Dataflow error result/status. | QUERY_HISTORY/TASK_HISTORY error fields. | Pipeline/activity error fields. |
| `ctrl_ingestion_schema_changes` | `change_type`, `column_name`, `source_type`, `target_type`, `applied`, `details_json`, `payload_json`, `changed_at_utc` | Schema change evidence. | Delta/UC schema diff; `add_column.source_type` comes from prepared schema. | Glue Catalog/Iceberg schema diff. | BigQuery schema diff. | INFORMATION_SCHEMA/schema diff. | Lakehouse/Purview schema diff. |
| `ctrl_ingestion_streams` | `stream_run_id`, `run_id`, `trigger`, `checkpoint_location`, `batches_processed`, `total_rows_read`, `total_rows_written`, `total_rows_quarantined`, `batch_id`, `batch_metrics_json`, `captured_at_utc` | Available-now/bounded stream evidence. | Structured Streaming/Auto Loader/Lakeflow source progress. | Glue streaming/bookmark/bounded replay metrics. | Dataflow/Dataproc/Pub/Sub replay metrics. | REVIEW_REQUIRED; use streams/tasks only with explicit design. | Eventstream/pipeline/Dataflow Gen2 metrics. |
| `ctrl_ingestion_lineage` | `event_time_utc`, `event_type`, `source_table`, `namespace`, `producer`, `event_json` | Lineage event. | OpenLineage/Databricks namespace and payload. | OpenLineage/CloudTrail/Glue lineage payload. | Dataplex process/run/event or OpenLineage payload. | ACCESS_HISTORY/QUERY_HISTORY/OpenLineage payload. | Purview/Fabric lineage or pipeline payload. |
| `ctrl_ingestion_explain` | `source_table`, `mode`, `explain_format`, `plan_text`, `captured_at_utc` | Execution plan diagnostics. | Spark `explain` or SQL explain. | Spark/Glue/EMR explain, Athena/Redshift explain. | BigQuery query plan/job statistics. | EXPLAIN/query profile. | Pipeline details/query plan where available. |
| `ctrl_ingestion_cost` | `signal_name`, `signal_value`, `payload_json`, `captured_at_utc` | Operational cost signal. | DBU estimate/system billing usage. | DPUSeconds/EMR/Athena/Redshift estimates. | BigQuery slot/bytes or Dataflow resource estimates. | QUERY_ATTRIBUTION credits. | Capacity Metrics CU/processing/memory signals. |
| `ctrl_ingestion_annotations` | `annotation_scope`, `annotation_type`, `column_name`, `key`, `previous_value`, `value`, `status`, `error_message`, `applied_sql`, `annotation_ts_utc`, `annotation_date` | Metadata application evidence. | UC comments/tags SQL. | Glue/LF tags/catalog metadata payload. | BigQuery descriptions/policy tags/Dataplex metadata. | COMMENT/TAG metadata. | Fabric/Purview metadata payload. |
| `ctrl_ingestion_access` | `access_run_id`, `access_type`, `principal`, `privilege`, `column_name`, `function_name`, `object_name`, `status`, `error_message`, `applied_sql`, `previous_value`, `new_value`, `mode`, `drift_policy`, `revoke_unmanaged`, `access_ts_utc`, `access_date` | Access/governance application evidence. | UC grants/row filters/masks. | Lake Formation/IAM grants, data filters, CloudTrail refs. | BigQuery IAM, row access policies, policy tags. | GRANT, masking policies, row access policies. | Fabric permissions/Purview policy evidence. |
| `ctrl_ingestion_operations` | `criticality`, `expected_frequency`, `freshness_sla_minutes`, `alert_on_failure`, `alert_on_quality_fail`, `runbook_url`, `ownership_json`, `owners_json`, `groups_json`, `tags_json`, `status`, `recorded_at_utc` | Operational metadata. | Operations contract plus Databricks job/UC evidence. | Operations contract plus Glue/LF evidence. | Operations contract plus BigQuery/Dataplex evidence. | Operations contract plus Snowflake metadata. | Operations contract plus Fabric item/workspace evidence. |
| `ctrl_ingestion_metadata` | `component`, `framework_version`, `ctrl_schema_version`, `updated_at_utc` | Framework/control schema metadata. | Adapter version/control schema row. | Adapter version/control schema row. | Adapter version/control schema row. | Adapter version/control schema row. | Adapter version/control schema row. |
| `ctrl_deployment_versions` | `deployment_id`, `deployment_step_id`, `deployment_hash`, `contract_hash`, `environment_hash`, `manifest_hash`, `artifact_kind`, `artifact_name`, `artifact_id`, `deployment_status` | Deploy version ledger. | Asset Bundle/job/notebook artifact evidence. | Glue/Step Functions/S3 artifact evidence. | BigQuery/Workflows artifact evidence. | Procedure/task/stage artifact evidence. | Notebook/deployment-pipeline artifact evidence. |

## Research References

- [Databricks dynamic value references](https://docs.databricks.com/aws/en/jobs/dynamic-value-references) document job/task run identifiers, start time and trigger values.
- [Databricks Delta table history](https://docs.databricks.com/aws/en/delta/history) documents table versions and `operationMetrics`.
- [Databricks jobs system tables](https://docs.databricks.com/gcp/en/admin/system-tables/jobs) document `system.lakeflow.job_run_timeline`, task timelines and job cost attribution metadata.
- [AWS Glue JobRun](https://docs.aws.amazon.com/glue/latest/webapi/API_JobRun.html) documents run ids, start/end, state, arguments, workers and `DPUSeconds`.
- [AWS Glue GetJobBookmark](https://docs.aws.amazon.com/glue/latest/webapi/API_GetJobBookmark.html) and [job bookmarks](https://docs.aws.amazon.com/glue/latest/dg/monitor-continuations.html) document bookmark state and `JobBookmarkEntry`.
- [AWS Lake Formation CloudTrail logging](https://docs.aws.amazon.com/en_us/lake-formation/latest/dg/logging-using-cloudtrail.html) documents `GrantPermissions` and `RevokePermissions` audit events.
- [BigQuery `INFORMATION_SCHEMA.JOBS`](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs), [Job REST resource](https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/Job), and [DmlStats](https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/DmlStats) document job ids, timing, bytes, slot-ms and inserted/updated/deleted counts.
- [Dataflow Job resource](https://docs.cloud.google.com/dataflow/docs/reference/data-pipelines/rest/v1/Job) documents job id, create/end time, state and status.
- [Dataplex data lineage](https://docs.cloud.google.com/dataplex/docs/lineage-views) documents process/run/event lineage concepts.
- Snowflake [`QUERY_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/query_history), [`TASK_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/task_history), [`QUERY_ATTRIBUTION_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/query_attribution_history), [`ACCESS_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/access_history), [`TAG_REFERENCES`](https://docs.snowflake.com/en/sql-reference/functions/tag_references), and [`POLICY_REFERENCES`](https://docs.snowflake.com/en/sql-reference/account-usage/policy_references) document query ids, task ids, rows/bytes, credits, object access, tags and policies.
- [Microsoft Fabric Workspace Monitoring / ItemJobEventLogs](https://learn.microsoft.com/en-us/fabric/data-factory/create-alerts-for-pipeline-runs) documents `JobInstanceId`, job status/timing/duration/workspace/capacity fields.
- [Microsoft Fabric Copy activity monitoring](https://learn.microsoft.com/en-us/fabric/data-factory/monitor-copy-activity) documents data read/written, file/row copy counts, throughput and duration details.
- [Microsoft Fabric Capacity Metrics app](https://learn.microsoft.com/en-us/fabric/enterprise/metrics-app) documents Capacity Units and capacity consumption monitoring.
