# Evidence Mapping Matrix

## Purpose

This is the column-by-column mapping from the canonical ContractForge control-table schema to the **native evidence surface of each adapter platform**. It is the authoritative reference for "where does this column's value come from on platform X" and the companion to [control-table-parity.md](control-table-parity.md) (which defines the canonical columns and portability status) and [evidence-model.md](evidence-model.md) (which defines the portable evidence vocabulary).

Platforms covered: **Databricks**, **AWS** (Glue + Iceberg), **GCP** (BigQuery / Dataproc), **Snowflake**, **Microsoft Fabric**.

## Design Principles

1. **Same information on every adapter.** The canonical schema is platform-neutral and lives once in `contractforge_core.evidence`. Every adapter fills the *same* columns, so evidence is comparable across platforms.
2. **Immutable, append-only.** Evidence tables are append-only (INSERT only, partitioned by date) — immutable like contracts. The state table is recorded as append-only history; "current state" is the latest row per target. Nothing is updated in place.
3. **JSON carries the richness, never dropped.** Anything native that has no first-class column is preserved in a `*_json` column (`operation_metrics_json`, `source_*_json`, `payload_json`, `details_json`, `event_json`, `batch_metrics_json`). Future reports/dashboards mine these.
4. **Compute, don't say "can't".** When a platform's run telemetry does not expose a counter directly, the adapter computes it in-job (it controls the SQL/DataFrame). Example: Iceberg snapshot summary does not split insert vs update, but the Glue MERGE job knows both — so it counts and fills `rows_inserted`/`rows_updated` instead of leaving them null.
5. **Neutral names, native values in JSON.** Columns are named by intent, not by one vendor's API. Vendor-specific identifiers (Delta version number, Iceberg snapshot id, BigQuery job id) are mapped into a neutral column and the native value is also kept in `operation_metrics_json`.

## Neutral Column Names (portabilization — applied)

A few columns previously leaked Databricks vocabulary. They are now renamed in the core schema (`contractforge_core.evidence.control_tables`) and the Databricks adapter is updated accordingly; the native value also goes into `operation_metrics_json`.

| Current column | Neutral name | Type | Rationale |
| --- | --- | --- | --- |
| `delta_version_before` / `delta_version_after` | `table_version_before` / `table_version_after` | STRING | Holds a Delta version number, an Iceberg snapshot id, a Fabric Delta version, or null (Snowflake). STRING fits all. |
| `notebook_name` | `runtime_entrypoint` | STRING | Notebook (Databricks/Fabric), Glue script (AWS), BigQuery script/proc (GCP), stored proc/query (Snowflake). |
| `spark_version` | `engine_version` | STRING | Spark version (Databricks/Fabric/Glue/Dataproc) or warehouse/engine version (Snowflake/BigQuery); null when not applicable. |
| `last_delta_version` (state) | `last_table_version` | STRING | Same reasoning as `table_version_*`. |

`runtime_type` is already neutral (`databricks`, `aws_glue`, `gcp_bigquery`, `snowflake`, `fabric`).

## Run Identity, Timing and Status

| Canonical column | Databricks | AWS (Glue) | GCP (BigQuery/Dataflow) | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- |
| `run_id` | `job.run_id` / `task.run_id` | Glue `JobRun.Id` | BigQuery `job_id` / Dataflow `Job.id` | `QUERY_HISTORY.query_id` | `ItemJobEventLogs.JobInstanceId` |
| `master_job_id` / `master_run_id` | `job.id` / `job.run_id` | `JobRun.JobName` / `JobRun.Id` | parent `job_id` / Dataflow job | `TASK_HISTORY.graph_run_group_id` | `ItemId` / parent job |
| `started_at_utc` | run start | `JobRun.StartedOn` | `start_time` | `start_time` | `JobStartTime` |
| `finished_at_utc` | run end | `JobRun.CompletedOn` | `end_time` | `end_time` | `JobEndTime` |
| `duration_seconds` | derived | `JobRun.ExecutionTime` (s) | `end_time - start_time` | `total_elapsed_time` (ms→s) | `DurationMs` (→s) |
| `status` | run state → `SUCCESS`/`FAILED`/`RUNNING` | `JobRunState` → mapped | `state` → mapped | `execution_status` (`success`/`fail`/`incident`) | `JobStatus` |
| `error_message` | exception (redacted) | `StateDetail` / `ErrorMessage` | job `error_result.message` | `error_code` + `error_message` | activity error |
| `runtime_entrypoint` | notebook name | Glue script name | BigQuery script/proc | proc/query | item/notebook name |
| `engine_version` | Spark version | Glue version | Dataproc Spark / BigQuery engine | Snowflake version (often null) | Fabric Spark runtime |

Status normalization keeps the ContractForge vocabulary (`SUCCESS`, `FAILED`, `RUNNING`, `SKIPPED`) so runs compare across platforms.

## Write / Row Metrics

The normalized ContractForge counters (`rows_read`, `rows_written`, `rows_inserted`, `rows_updated`, `rows_deleted`, `rows_quarantined`) are required. The full native commit metrics always go into `operation_metrics_json`.

| Canonical column | Databricks (Delta `operationMetrics`) | AWS (Iceberg snapshot `summary`) | GCP (BigQuery `dml_statistics`) | Snowflake (`QUERY_HISTORY`) | Fabric |
| --- | --- | --- | --- | --- | --- |
| `rows_read` | input rows | `df.count()` before write | rows scanned / `total_bytes_processed` proxy | source query `rows_produced` | Delta input / Copy `dataRead` |
| `rows_written` | `numOutputRows` | `added-records` | written rows | `rows_produced` | `numOutputRows` / Copy `rowsCopied` |
| `rows_inserted` | `numTargetRowsInserted` | **computed in MERGE job** (summary lacks split) | `dml_statistics.inserted_row_count` | `rows_inserted` | `numTargetRowsInserted` |
| `rows_updated` | `numTargetRowsUpdated` | **computed in MERGE job** | `dml_statistics.updated_row_count` | `rows_updated` | `numTargetRowsUpdated` |
| `rows_deleted` | `numTargetRowsDeleted` | `deleted-records` / **computed** | `dml_statistics.deleted_row_count` | `rows_deleted` | `numTargetRowsDeleted` |
| `rows_quarantined` | computed in job | computed in job | computed in job | computed in job | computed in job |
| `table_version_before` / `_after` | Delta `version` | Iceberg `snapshot_id` (before/after) | BigQuery `job_id` / Dataproc snapshot | null (`query_id` in JSON) | Delta `version` |
| `write_committed` | commit success | snapshot committed | DML success | DML success | commit success |
| `operation_metrics_json` | full `operationMetrics` map | full Iceberg snapshot `summary` map | `dml_statistics` + `total_bytes_billed` + `total_slot_ms` | rows/bytes/partitions fields | `operationMetrics` / Copy output JSON |

GCP, Snowflake and Databricks/Fabric expose the insert/update/delete split directly. AWS Iceberg does not, so the adapter counts the MERGE branches in the Glue job — see principle 4.

## Cost Signals

`ctrl_ingestion_cost` (`signal_name`, `signal_value`, `payload_json`) is the cross-platform home for cost. Each adapter emits its native signal; the breakdown goes into `payload_json` for dashboards.

| Adapter | `signal_name` | `signal_value` | `payload_json` (native breakdown) |
| --- | --- | --- | --- |
| Databricks | `databricks_dbu` | DBUs consumed | cluster/sku, system billing usage attribution |
| AWS | `glue_dpu_seconds` | `JobRun.DPUSeconds` | `WorkerType`, `NumberOfWorkers`, `MaxCapacity`, `ExecutionClass`, `ExecutionTime` |
| GCP | `gcp_bigquery_slot_ms` | `total_slot_ms` | `total_bytes_billed`, `total_bytes_processed`, reservation; Dataflow vCPU/mem for Dataproc |
| Snowflake | `snowflake_credits` | `credits_used_cloud_services` (+ warehouse credits via `QUERY_ATTRIBUTION_HISTORY`) | `warehouse_size`, `partitions_scanned`/`partitions_total`, `bytes_scanned` |
| Fabric | `fabric_cu_seconds` | CU-seconds | Capacity Metrics CPU/processing/memory, `CapacityId` |

Cost is an operational signal, not billing reconciliation.

## Quality

`ctrl_ingestion_quality` (`rule_name`, `status`, `severity`, `failed_count`, `observed_value`, `details_json`) maps each platform's data-quality result. `details_json` holds the native evaluation payload.

| Adapter | Native quality system | `rule_name` | `observed_value` | `details_json` |
| --- | --- | --- | --- | --- |
| Databricks | Spark precheck / Lakehouse Monitoring | rule name | metric | check SQL / monitor metric |
| AWS | **Glue Data Quality (DQDL)** | DQDL rule | rule metric/outcome | DQDL ruleset + `EvaluateDataQuality` result |
| GCP | **Dataplex** data quality / data profiling | scan rule | rule metric | Dataplex scan result |
| Snowflake | **Data Metric Functions (DMF)** | `NULL_COUNT`/`DUPLICATE_COUNT`/`FRESHNESS`/`ROW_COUNT`/`UNIQUE_COUNT` | DMF value | DMF schedule + `SYSTEM$DATA_METRIC_SCAN` output |
| Fabric | Spark precheck | rule name | metric | check SQL |

Aggregate quality status stays the ContractForge vocabulary (`PASSED`, `FAILED`, `WARNED`, `NOT_CONFIGURED`) regardless of the native system.

## JSON Columns — what each holds

| JSON column | Content |
| --- | --- |
| `operation_metrics_json` | Full native write/commit metrics (Delta `operationMetrics`, Iceberg snapshot `summary`, BigQuery `dml_statistics`, Snowflake row/byte fields). |
| `source_*_json` (`options`/`read`/`request`/`auth`/`pagination`/`response`/`incremental`/`limits`/`capabilities`/`metrics`) | Redacted connector configuration and per-run source metrics. |
| `metrics_json` | Compatibility alias of the run metrics dict (existing consumers); new logic prefers `operation_metrics_json`. |
| `cost.payload_json` | Native cost breakdown (worker/warehouse/capacity/slot detail). |
| `quality.details_json` | Native data-quality evaluation payload (DQDL/DMF/Dataplex/Spark check). |
| `lineage.event_json` | OpenLineage-compatible event when available. |
| `schema_changes.payload_json` | Raw native schema-change payload. |
| `streams.batch_metrics_json` | Per micro-batch metrics. |

## Immutability

- **Evidence tables** (`runs`, `errors`, `quality`, `quarantine`, `schema_changes`, `lineage`, `explain`, `metadata`, `streams`, `annotations`, `access`, `operations`, `cost`): append-only, partitioned by event date. Never `UPDATE`/`DELETE`. Each run/event is a new immutable row.
- **State** (`ctrl_ingestion_state`): recorded as append-only history; the current watermark/state per target is the latest row (`row_number()`/max `last_updated_at_utc`). This keeps state auditable and immutable like the evidence tables.
- **Locks** (`ctrl_ingestion_locks`): best-effort, adapter-mapped; the only inherently mutable surface (acquire/release), and may be a non-table mechanism (DynamoDB conditional write, etc.) per adapter.

## Per-Adapter Native Source Reference

| Platform | Run/timing | Write/version | Cost | Quality | Lineage |
| --- | --- | --- | --- | --- | --- |
| Databricks | `job.*`/`task.*` refs, `system.lakeflow.job_run_timeline` | Delta `DESCRIBE HISTORY` (`version`, `operationMetrics`) | DBUs, system billing usage | Spark checks / Lakehouse Monitoring | OpenLineage, Spark explain |
| AWS | Glue `JobRun` | Iceberg snapshot id + `summary`; computed merge counts | `DPUSeconds`, worker type/count | Glue Data Quality (DQDL) | OpenLineage/CloudTrail/CloudWatch |
| GCP | BigQuery `INFORMATION_SCHEMA.JOBS`, Dataflow Job | `dml_statistics`, `job_id`, Dataproc snapshot | `total_slot_ms`, `total_bytes_billed` | Dataplex data quality | Dataplex Data Lineage |
| Snowflake | `ACCOUNT_USAGE.QUERY_HISTORY`, `TASK_HISTORY` | `rows_*`, `query_id` (no table version) | `credits_used_cloud_services`, `QUERY_ATTRIBUTION_HISTORY` | Data Metric Functions | `ACCESS_HISTORY`, query profile |
| Fabric | Workspace Monitoring `ItemJobEventLogs` | Lakehouse Delta version, Copy job id | CU-seconds, Capacity Metrics | Spark checks | Monitoring hub, Purview lineage |

## Sources

- Snowflake: [QUERY_HISTORY view](https://docs.snowflake.com/en/sql-reference/account-usage/query_history) · [TASK_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/task_history) · [COPY_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/copy_history) · [System Data Metric Functions](https://docs.snowflake.com/en/user-guide/data-quality-system-dmfs) · [QUERY_ATTRIBUTION_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/query_attribution_history) · [Snowflake capability and evidence parity](snowflake-capability-parity.md)
- AWS / Iceberg: [Iceberg snapshots](https://py.iceberg.apache.org/reference/pyiceberg/table/snapshots/) · [Glue Data Quality](https://docs.aws.amazon.com/glue/latest/dg/glue-data-quality.html)
- GCP: [BigQuery INFORMATION_SCHEMA.JOBS](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs)
- Fabric: [Monitor pipeline runs](https://learn.microsoft.com/en-us/fabric/data-factory/monitor-pipeline-runs) · [Fabric operations / capacity](https://learn.microsoft.com/en-us/fabric/enterprise/fabric-operations) · [Spark monitoring](https://learn.microsoft.com/en-us/fabric/data-engineering/spark-monitoring-best-practices)
- Databricks: Delta `DESCRIBE HISTORY` `operationMetrics`; `system.lakeflow.*` run timelines.
