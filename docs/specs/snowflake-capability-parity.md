# Snowflake Capability And Evidence Parity

## Purpose

This spec defines how a future `contractforge-snowflake` adapter should map
ContractForge Core contract parameters and evidence/control-table fields to
Snowflake-native capabilities.

The goal is not to make the core Snowflake-aware. The goal is to give the
Snowflake adapter a researched implementation target:

```text
ContractForge contract semantics
  -> Snowflake capability declaration
  -> Snowflake SQL / task / stream / policy implementation
  -> canonical ContractForge evidence tables populated with Snowflake values
```

The sources for this document are Snowflake's official documentation. The
adapter must verify behavior in a real Snowflake account before changing any
`REVIEW_REQUIRED` item to `SUPPORTED`.

## Reference Snowflake Surfaces

| Snowflake surface | ContractForge use |
| --- | --- |
| SQL warehouse | Primary runtime for table, SQL, staged file and merge-based ingestion. |
| Database and schema | Mapping for `target.catalog` and `target.schema`. |
| Tables, views and stages | Mapping for governed table sources and staged file sources. |
| `COPY INTO <table>` | Bounded staged file loading and load validation. |
| Snowpipe | Continuous or near-continuous staged file loading when the contract asks for file discovery beyond simple batch loads. |
| Streams | Change-data capture over Snowflake tables and views. |
| Tasks | Scheduled execution, task graphs and stream-triggered jobs. |
| Row access policies | Row filter implementation. |
| Masking policies | Column mask implementation. |
| Object tags and comments | Annotation and governance metadata implementation. |
| Account Usage and Information Schema | Native evidence source for queries, tasks, copy loads, costs, policies, tags and object metadata. |
| Data Metric Functions | Optional native quality metric surface. |

Primary references:

- [QUERY_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/query_history)
- [TASK_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/task_history)
- [QUERY_ATTRIBUTION_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/query_attribution_history)
- [COPY_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/copy_history)
- [COPY INTO table](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)
- [Snowpipe](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-intro)
- [Streams](https://docs.snowflake.com/en/user-guide/streams-intro)
- [CREATE TASK](https://docs.snowflake.com/en/sql-reference/sql/create-task)
- [MERGE](https://docs.snowflake.com/en/sql-reference/sql/merge)
- [Information Schema COLUMNS](https://docs.snowflake.com/en/sql-reference/info-schema/columns)
- [Data Metric Functions](https://docs.snowflake.com/en/user-guide/data-quality-system-dmfs)
- [CREATE ROW ACCESS POLICY](https://docs.snowflake.com/en/sql-reference/sql/create-row-access-policy)
- [Column-level security / masking policies](https://docs.snowflake.com/en/user-guide/security-column-intro)
- [CREATE MASKING POLICY](https://docs.snowflake.com/en/sql-reference/sql/create-masking-policy)
- [TAG_REFERENCES](https://docs.snowflake.com/en/sql-reference/functions/tag_references)
- [POLICY_REFERENCES](https://docs.snowflake.com/en/sql-reference/account-usage/policy_references)
- [ACCESS_HISTORY](https://docs.snowflake.com/en/sql-reference/account-usage/access_history)

## Adapter Subtargets

The Snowflake adapter should not declare one vague `snowflake` capability. It
should declare explicit subtargets.

| Subtarget | Status target | Purpose |
| --- | --- | --- |
| `snowflake_sql_warehouse` | Primary | SQL execution over warehouse compute. Handles table, SQL, file-stage, quality, merge and evidence writes. |
| `snowflake_task_graph` | Primary deployment path | Renders task/task-graph deployment artifacts for scheduled project execution. |
| `snowflake_snowpipe` | Review-first | Handles staged file continuous loading where Snowpipe semantics preserve the contract. |
| `snowflake_streams_tasks` | Review-first | Handles table CDC and incremental table-to-table workflows. |
| `snowflake_snowpark` | Future | Handles complex transforms or connector behavior that is not clean in SQL alone. |
| `snowflake_native_passthrough` | Future | Delegates to Snowflake-native connectors or marketplace/native app ingestion. |

## Core Parameter Parity

### Sources

| ContractForge parameter | Snowflake mapping | Status | Notes |
| --- | --- | --- | --- |
| `source.type: table` | `SELECT ... FROM <database>.<schema>.<table>` | `SUPPORTED` | Adapter resolves logical refs to fully-qualified names. |
| `source.type: view` | `SELECT ... FROM <database>.<schema>.<view>` | `SUPPORTED` | Secure view behavior must be recorded in planning details when relevant. |
| `source.type: sql` | Snowflake SQL query | `SUPPORTED_WITH_WARNINGS` | SQL dialect is Snowflake-specific. Portable `{{ table_ref:* }}` placeholders remain adapter-resolved. |
| `source.type: staged_files` with `format: csv/json/parquet` | Named internal/external stage plus named file format or stage default file format, read through a staged query | `SUPPORTED_WITH_WARNINGS` | CSV positional projection, JSON `VARIANT` payload/projection and Parquet projection are implemented. Other formats remain review-required. |
| `source.type: csv/json/parquet/orc/avro/xml/text` | Normalize to `staged_files` or reviewed source-specific shorthand | `REVIEW_REQUIRED` | The adapter accepts explicit `staged_files` first so file-format, stage and evidence boundaries are visible. |
| `source.type: object_storage` | External stage over S3, Azure or GCS | `SUPPORTED_WITH_WARNINGS` | Storage integration, stage ownership and path privileges are environment-owned. |
| `source.type: incremental_files` | `COPY_HISTORY`, Snowpipe, directory table, or adapter state table | `REVIEW_REQUIRED` | Snowflake offers related surfaces, but exactly-once, ordering and reprocessing semantics depend on the chosen load path. |
| `source.type: delta` | External table/integration or imported stage pattern | `REVIEW_REQUIRED` | Delta semantics are not Snowflake-native table semantics. |
| `source.type: iceberg_table` | Snowflake-managed or external Apache Iceberg support | `SUPPORTED_WITH_WARNINGS` | Catalog, write support and metadata refresh behavior must be declared by the adapter. |
| `source.type: http_file/http_csv/http_json/http_text` | External access integration, Snowpark procedure, or pre-stage file path | `REVIEW_REQUIRED` | The adapter should prefer pre-staged files for first implementation. |
| `source.type: jdbc/postgres/mysql/sqlserver/oracle/redshift/db2/mariadb` | External function/procedure, Snowpark, or native connector pattern | `REVIEW_REQUIRED` | Snowflake is not a general JDBC extraction runtime by default. |
| `source.type: kafka_bounded` | Snowpipe Streaming, connector-managed stage, or external stream bridge | `REVIEW_REQUIRED` | Kafka replay semantics differ from ContractForge bounded Spark-style replay. |
| `source.type: eventhubs_bounded` | External bridge to Snowflake stage/Snowpipe Streaming | `REVIEW_REQUIRED` | Cross-cloud event offset semantics require design review. |
| `source.type: delta_share` | Marketplace/native sharing/external table pattern | `SUPPORTED_WITH_WARNINGS` | Needs adapter-specific source resolver. |
| `source.type: native_passthrough` | Snowflake connector/native app/marketplace source | `SUPPORTED_WITH_WARNINGS` | Must return explicit warnings about connector-owned semantics and evidence gaps. |
| `source.connection_path` | Core-resolved shared connection before adapter planning | `SUPPORTED` | Snowflake adapter receives the resolved source; it must not re-read arbitrary local paths. |
| `source.auth` | Snowflake secrets, integrations, key-pair auth or environment secret resolver | `REVIEW_REQUIRED` | The adapter owns credential resolution and must redact evidence. |
| `source.watermark` | SQL predicate, stream offset, `COPY_HISTORY` marker or state table value | `SUPPORTED_WITH_WARNINGS` | The implementation path changes the strength of guarantees. |
| `source.progress_location` | ContractForge state table or stage/copy marker | `REVIEW_REQUIRED` | The core field is portable, but Snowflake implementation must choose table state vs native metadata. |
| `source.schema_tracking_location` | Information Schema snapshot or adapter state table | `REVIEW_REQUIRED` | Snowflake does not need a Databricks-style schema location; the adapter should map the intent to schema evidence. |

### Target And Write Semantics

| ContractForge parameter | Snowflake mapping | Status | Notes |
| --- | --- | --- | --- |
| `target.catalog` | Database | `SUPPORTED` | Logical catalog names should resolve through environment defaults. |
| `target.catalog_type` | `database` / `metastore` classification | `SUPPORTED` | Used for planning and diagnostics; not a Snowflake DDL parameter. |
| `target.schema` | Schema | `SUPPORTED` | Create/validate behavior is adapter-owned. |
| `target.table` | Table | `SUPPORTED` | Must be quoted safely by Snowflake identifier rules. |
| `layer` | Naming, comments, tags and evidence | `SUPPORTED` | Layer is ContractForge metadata, not a Snowflake primitive. |
| `mode: append` | `INSERT INTO ... SELECT` or `COPY INTO` append | `SUPPORTED` | File loads should persist `COPY_HISTORY` details. |
| `mode: overwrite` | Transactional replace pattern, `CREATE OR REPLACE TABLE AS SELECT`, or truncate/insert | `SUPPORTED_WITH_WARNINGS` | Atomicity and grants retention depend on the chosen pattern. |
| `mode: upsert` | `MERGE INTO` | `SUPPORTED` | Snowflake `MERGE` supports matched and not-matched clauses. Duplicate-source behavior must be prevalidated. |
| `mode: hash_diff_upsert` | Hash projection plus `MERGE` only for changed rows | `SUPPORTED_WITH_WARNINGS` | Hash function, null handling, collation and type casting must be adapter-defined and tested. |
| `mode: historical` | SQL `MERGE`/transaction pattern, possibly with streams/tasks | `REVIEW_REQUIRED` | Late-arriving records, effective dating and delete handling are project semantics, not a single Snowflake primitive. |
| `mode: snapshot_reconcile_soft_delete` | `MERGE` with matched/not matched source design | `SUPPORTED_WITH_WARNINGS` | Requires explicit snapshot boundary and source completeness proof. |
| `schema_policy: strict` | Compare incoming schema to `INFORMATION_SCHEMA.COLUMNS` and fail drift | `SUPPORTED` | Strict mode does not mutate target schema. |
| `schema_policy: additive_only` | `ALTER TABLE ADD COLUMN` after nullable additive diff | `SUPPORTED_WITH_WARNINGS` | Type mapping and default/nullability decisions must be explicit. |
| `schema_policy: permissive` | Reviewed DDL plan | `REVIEW_REQUIRED` | Type widening and incompatible changes require review. |

### Quality, Shape And Transform

| ContractForge parameter | Snowflake mapping | Status | Notes |
| --- | --- | --- | --- |
| `quality_rules.not_null` | SQL `COUNT_IF(column IS NULL)` or DMF `NULL_COUNT` | `SUPPORTED` | Runtime SQL is the first implementation; DMFs are optional governance integration. |
| `quality_rules.required_columns` | `INFORMATION_SCHEMA.COLUMNS` lookup | `SUPPORTED` | Missing columns fail before write. |
| `quality_rules.unique_key` | SQL grouped duplicate count or DMF `DUPLICATE_COUNT` | `SUPPORTED` | Composite keys must use SQL grouping unless DMF fit is verified. |
| `quality_rules.accepted_values` | SQL `NOT IN` or DMF `ACCEPTED_VALUES` | `SUPPORTED_WITH_WARNINGS` | Large value sets should use reference tables instead of inline lists. |
| `quality_rules.min_rows` | SQL row count or DMF `ROW_COUNT` | `SUPPORTED` | The result goes to `ctrl_ingestion_quality`. |
| `quality_rules.max_null_ratio` | SQL null count divided by row count | `SUPPORTED` | DMF use is optional. |
| `quality_rules.expressions` | Snowflake SQL boolean predicate | `SUPPORTED_WITH_WARNINGS` | Expressions are dialect-specific and must be marked as such in planning. |
| `on_quality_fail: fail` | Raise error before target commit | `SUPPORTED` | Failure must still persist error/run evidence where possible. |
| `on_quality_fail: warn` | Persist quality evidence and continue | `SUPPORTED` | Run status remains independent from quality status. |
| `on_quality_fail: quarantine` | Write failed rows to `ctrl_ingestion_quarantine`, then write passed rows | `SUPPORTED_WITH_WARNINGS` | Row-level quarantine is supported for row-identifiable SQL rules; aggregate rules become recorded warnings. |
| `shape` | SQL over `VARIANT`, `FLATTEN`, casts, or Snowpark | `REVIEW_REQUIRED` | Nested JSON and array explosion can be mapped, but parity with Spark/Glue shape behavior must be tested. |
| `transform.cast` | Snowflake `CAST` / `TRY_CAST` depending strictness | `SUPPORTED_WITH_WARNINGS` | Error behavior must match the contract. |
| `transform.derive` | SQL expression projection | `SUPPORTED_WITH_WARNINGS` | Dialect review required. |
| `transform.standardize` | SQL string functions | `SUPPORTED` | Trim, upper/lower and whitespace normalization are portable enough. |
| `transform.deduplicate` | `QUALIFY ROW_NUMBER() OVER (...) = 1` | `SUPPORTED_WITH_WARNINGS` | Deterministic ordering is required. |

### Execution, Project And Deployment

| ContractForge parameter | Snowflake mapping | Status | Notes |
| --- | --- | --- | --- |
| `project.schedule.cron` | `CREATE TASK ... SCHEDULE = 'USING CRON <expr> <timezone>'` | `SUPPORTED` | Snowflake task cron includes timezone in the schedule string. |
| `project.schedule.timezone` | Task cron timezone | `SUPPORTED` | Timezone behavior is task-specific and does not follow later session timezone changes. |
| `project.depends_on` | Task graph `AFTER <task>` | `SUPPORTED_WITH_WARNINGS` | Task graph skip/failure propagation must be captured in deployment docs. |
| `execution.freshness` | Task schedule, stream-triggered task, Snowpipe, or external scheduler | `SUPPORTED_WITH_WARNINGS` | Freshness is intent; enforcement depends on runtime path. |
| `execution.latency_target` | Preserved in plan/evidence and optionally task/Snowpipe design | `SUPPORTED` | It is not a hard runtime guarantee by itself. |
| `execution.preferred` | Scheduled, task graph, stream-triggered task, Snowpipe or external orchestration | `REVIEW_REQUIRED` | The adapter must block if the preferred mode cannot preserve semantics and no fallback is declared. |
| `execution.fallback` | Alternative implementation path | `SUPPORTED` | The planner may use the fallback only when explicitly allowed. |
| `environment.artifacts.uri` | Stage path, local output, Git artifact path, or object storage URI | `SUPPORTED_WITH_WARNINGS` | The Snowflake adapter should define accepted artifact schemes. |
| `environment.evidence` | Snowflake evidence database/schema | `SUPPORTED` | Evidence table names remain canonical `ctrl_ingestion_*`. |
| `environment.parameters.snowflake.warehouse` | Warehouse binding | `PLATFORM_EXTENSION` | Adapter-owned deployment/runtime setting. |
| `environment.parameters.snowflake.role` | Role binding | `PLATFORM_EXTENSION` | Adapter-owned security setting. |
| `environment.parameters.snowflake.task_schema` | Task deployment namespace | `PLATFORM_EXTENSION` | Keep out of ingestion contracts. |

### Annotations And Access

| ContractForge parameter | Snowflake mapping | Status | Notes |
| --- | --- | --- | --- |
| `annotations.table.description` | `COMMENT ON TABLE` | `SUPPORTED` | Evidence should record applied SQL/query id. |
| `annotations.columns.*.description` | `COMMENT ON COLUMN` | `SUPPORTED` | Evidence should record per-column status. |
| `annotations.*.tags` | Snowflake object tags | `SUPPORTED_WITH_WARNINGS` | Tag creation, namespace and allowed values are environment/governance decisions. |
| `annotations.*.pii` | Tags and optional masking policy recommendation | `SUPPORTED_WITH_WARNINGS` | PII tags do not automatically enforce masking unless access contract declares it. |
| `access.grants` | `GRANT` statements to roles/users | `SUPPORTED_WITH_WARNINGS` | Privilege vocabulary needs adapter mapping. Role hierarchy may create drift. |
| `access.row_filters` | Row access policies | `SUPPORTED_WITH_WARNINGS` | Snowflake policies return boolean and are applied to tables/views. Principal-specific logic usually lives inside the policy expression. |
| `access.column_masks` | Masking policies | `SUPPORTED_WITH_WARNINGS` | Policy signature/type compatibility must be checked. Some policy combinations have platform limits. |
| `access.access_policy.on_drift` | Compare declared grants/policies with actual state | `SUPPORTED_WITH_WARNINGS` | Reconcile/revoke paths require explicit review due to role inheritance. |
| `access.revoke_unmanaged` | Revocation plan | `REVIEW_REQUIRED` | Never default to destructive access changes. |

## Evidence Storage Strategy

The Snowflake adapter should persist evidence in Snowflake tables with the same
canonical names and columns defined by `contractforge_core.evidence`. These are
ContractForge evidence tables, not Snowflake Account Usage views. Snowflake
native views supply values; they do not replace the ContractForge evidence
model.

Recommended default:

```yaml
environment:
  adapter: snowflake
  evidence:
    database: CONTRACTFORGE
    schema: CF_EVIDENCE
```

Control tables should be append-only except lock/state helper surfaces where the
adapter has a clearly documented concurrency strategy.

## Control Table Mapping

### `ctrl_ingestion_runs`

| ContractForge field group | Snowflake source |
| --- | --- |
| Run identity | ContractForge `run_id`; Snowflake `QUERY_HISTORY.query_id`; task runs can also record `TASK_HISTORY.graph_run_group_id`. |
| Job identity | Task database/schema/name from `TASK_HISTORY`; manual runs use procedure/query entrypoint. |
| Timing | `QUERY_HISTORY.start_time`, `QUERY_HISTORY.end_time`, `total_elapsed_time`; task schedules use `TASK_HISTORY.scheduled_time` and `completed_time`. |
| Status | `QUERY_HISTORY.execution_status` plus adapter exception status; task status from `TASK_HISTORY.state`. |
| Error | `QUERY_HISTORY.error_code` and `error_message`; adapter exception details after redaction. |
| Row metrics | `QUERY_HISTORY.rows_inserted`, `rows_updated`, `rows_deleted`, `rows_unloaded`, `rows_produced`; adapter-computed `rows_read`, `rows_written`, `rows_quarantined` when native counters are insufficient. |
| Bytes/partition metrics | `bytes_scanned`, `bytes_written`, `bytes_written_to_result`, `partitions_scanned`, `partitions_total`, spill/network fields into `operation_metrics_json`. |
| Runtime | Warehouse name/size, role/user, query tag, entrypoint and `CURRENT_VERSION()` where collected. |
| Table version | Snowflake has no Delta/Iceberg-style target table version for standard tables; keep `table_version_before` and `table_version_after` null and store query/transaction markers in `operation_metrics_json`. |

### `ctrl_ingestion_state`

| ContractForge field | Snowflake source |
| --- | --- |
| `watermark_column`, `watermark_value` | Contract watermark and post-read high-watermark query result. |
| `last_success_at_utc`, `last_status`, `last_run_id` | ContractForge run finalization. |
| `last_rows_written` | Adapter row metrics. |
| `last_table_version` | Null for standard tables; stream offset/copy marker may be stored in JSON. |
| `last_watermark_candidate` | Candidate max watermark before commit. |
| `state_details_json` | Stream name/offset marker, `COPY_HISTORY` file marker, Snowpipe pipe name or task metadata. |

Snowflake Account Usage views can have latency. State that affects correctness
should be written by the adapter during the run instead of relying only on
Account Usage reconciliation.

### `ctrl_ingestion_quality`

| ContractForge field | Snowflake source |
| --- | --- |
| `rule_name` | Contract rule name or native DMF name. |
| `status`, `severity`, `failed_count` | Adapter SQL evaluation result. |
| `observed_value` | Count/ratio/value from SQL check or Data Metric Function. |
| `details_json` | SQL predicate, DMF name, query id, sample limits and dialect classification. |

Snowflake Data Metric Functions are useful evidence inputs, but they are not a
complete replacement for ContractForge runtime quality checks because
ContractForge must support fail/warn/quarantine behavior during ingestion.

### `ctrl_ingestion_quarantine`

| ContractForge field | Snowflake source |
| --- | --- |
| `record_payload` | `OBJECT_CONSTRUCT(*)` / `TO_JSON` payload from failed row projection. |
| `record_ref` | Optional staging table key, target natural key or file/row reference. |
| `reason`, `rule_name` | Failed ContractForge row-level rule. |
| `quarantined_at_utc` | Adapter timestamp at quarantine write. |

Aggregate quality failures cannot produce row-level quarantine without an
explicit row predicate. The adapter should record those as warnings or failures,
not invent quarantined rows.

### `ctrl_ingestion_errors`

| ContractForge field | Snowflake source |
| --- | --- |
| `error_type`, `error_class` | Adapter exception classifier plus Snowflake error category when available. |
| `error_message` | Redacted adapter error plus `QUERY_HISTORY.error_message`. |
| `stack_trace` | Procedure/Snowpark stack when available; otherwise null. |
| `query_id` / `runtime_context_json` | `QUERY_HISTORY.query_id`, role, warehouse, task metadata. |

### `ctrl_ingestion_schema_changes`

| ContractForge field | Snowflake source |
| --- | --- |
| Before/after schema | Adapter schema snapshots from `INFORMATION_SCHEMA.COLUMNS`. |
| Applied DDL | `ALTER TABLE` / `CREATE TABLE` statement and `QUERY_HISTORY.query_id`. |
| Drift classification | Core schema policy result: strict/additive/permissive. |

### `ctrl_ingestion_streams`

| ContractForge field | Snowflake source |
| --- | --- |
| Batch identity | Task run id, graph run group id, stream name, Snowpipe pipe name or copy batch marker. |
| Source progress | Stream offset state, `COPY_HISTORY.file_name`, `last_load_time`, pipe received time. |
| Metrics | Rows loaded, parsed rows, error count, file size, task/query metrics. |
| Status | Task/COPY/Snowpipe status normalized to ContractForge status. |

Streaming and available-now semantics must remain `REVIEW_REQUIRED` until the
adapter proves checkpoint/state behavior for each source family.

### `ctrl_ingestion_lineage`

| ContractForge field | Snowflake source |
| --- | --- |
| Input/output objects | `ACCESS_HISTORY` direct/base/modified objects where available. |
| Query identity | `query_id`, query tag and execution timestamp. |
| Event payload | Native `ACCESS_HISTORY` object arrays plus ContractForge source/target refs. |

`ACCESS_HISTORY` is an audit source; the adapter should still emit a
ContractForge lineage event during the run so dashboards do not depend only on
Account Usage latency.

Runtime execution now writes an immediate ContractForge/OpenLineage-style
`COMPLETE` event with the contract run id, source reference, target table, row
count and Snowflake query ids. Native `ACCESS_HISTORY` reconciliation remains a
delayed Account Usage path: it probes by structured `QUERY_TAG` `run_id` and
returns `PENDING` without writing rows until matching native lineage rows are
published.

### `ctrl_ingestion_annotations`

| ContractForge field | Snowflake source |
| --- | --- |
| Table/column descriptions | Applied `COMMENT` statements and query ids. |
| Tags | `TAG_REFERENCES` table function or Account Usage view, plus applied SQL. |
| Status | Applied/validated/warned/failed per annotation. |

### `ctrl_ingestion_access`

| ContractForge field | Snowflake source |
| --- | --- |
| Grants | Applied `GRANT` statements and information schema/account usage checks. |
| Row access policies | Created/applied row access policy DDL and `POLICY_REFERENCES`. |
| Masking policies | Created/applied masking policy DDL and `POLICY_REFERENCES`. |
| Drift status | Adapter comparison of declared access contract and current Snowflake state. |

### `ctrl_ingestion_operations`

Operations fields come from ContractForge `operations.yaml`. Snowflake can add
task name, schedule, warehouse, alert integration and query tag evidence, but it
must not redefine ownership, criticality or SLA semantics.

### `ctrl_ingestion_explain`

| ContractForge field | Snowflake source |
| --- | --- |
| `plan_text` | `EXPLAIN` output or profile/report reference. |
| `explain_format` | `TEXT` or `JSON` when supported by the rendered statement. |
| `captured_at_utc` | Adapter timestamp. |
| `details_json` | Query id/profile URL when available. |

Runtime execution captures `EXPLAIN USING TEXT` for the rendered write
statement by default and stores failures as run metrics without failing the
ingestion run. Contracts can disable capture with
`extensions.snowflake.explain_enabled: false`.

### `ctrl_ingestion_cost`

| ContractForge field | Snowflake source |
| --- | --- |
| `signal_name` | `query_count`, `bytes_scanned`, `execution_time_ms`, `cloud_services_credits`, `rows_produced`, `warehouse_count`, `attributed_compute_credits`, `query_acceleration_credits`, later `snowpipe_bytes_billed`. |
| `signal_value` | `QUERY_HISTORY` totals, `QUERY_ATTRIBUTION_HISTORY.credits_attributed_compute`, warehouse metadata counts, or later `COPY_HISTORY.bytes_billed` for Snowpipe. |
| `payload_json` | Warehouse id/name, query id, root query id, query tag, cloud-services credits, acceleration credits, bytes scanned/written and task metadata. |

Cost is an operational signal, not a billing reconciliation. Account Usage
latency means cost evidence may be appended by a later reconciliation command.
If Account Usage has not produced matching rows yet, reconciliation reports a
pending status without inserting duplicate evidence. The same pending path is
used when the executing role cannot read Account Usage, with a warning so
operators can grant the needed Snowflake database role separately from runtime
ingestion privileges.

### `ctrl_ingestion_metadata`

The adapter fills ContractForge component metadata, core version, adapter
version, control schema version, Snowflake account/region when configured,
warehouse/role defaults and runtime feature flags. Sensitive values must be
redacted.

## Query Tag Requirement

The Snowflake adapter should set a structured `QUERY_TAG` for every statement it
owns. At minimum:

```json
{
  "product": "contractforge",
  "adapter": "snowflake",
  "run_id": "<contractforge-run-id>",
  "project": "<project-name>",
  "target": "<database.schema.table>"
}
```

This gives `QUERY_HISTORY`, `QUERY_ATTRIBUTION_HISTORY`, `ACCESS_HISTORY` and
task diagnostics a stable join key back to ContractForge evidence.

## Review Boundaries

The initial Snowflake planner should return `REVIEW_REQUIRED` or
`SUPPORTED_WITH_WARNINGS` for these areas until proven by real tests:

- `incremental_files` using Snowpipe or copy history.
- Kafka/Event Hubs bounded replay.
- historical with late-arriving rows, deletes and overlapping validity windows.
- Snapshot soft delete without a proven complete source snapshot.
- Row access and masking policies with principal-specific logic.
- Tag-based masking policy generation.
- Complex `shape` operations over nested `VARIANT` payloads.
- Quarantine for aggregate quality rules.
- Type widening and incompatible schema changes.
- Cost attribution when Account Usage latency delays query-cost rows.

## Initial Capability Declaration Target

The first Snowflake adapter capability set should be conservative:

| Area | Initial status |
| --- | --- |
| Table/view/sql sources | `SUPPORTED` |
| Staged file batch load | `SUPPORTED_WITH_WARNINGS` |
| Append | `SUPPORTED` |
| Overwrite | `SUPPORTED_WITH_WARNINGS` |
| current-state upsert | `SUPPORTED` |
| hash-diff upsert | `SUPPORTED_WITH_WARNINGS` |
| historical | `REVIEW_REQUIRED` |
| Snapshot soft delete | `SUPPORTED_WITH_WARNINGS` |
| Strict schema policy | `SUPPORTED` |
| Additive schema policy | `SUPPORTED_WITH_WARNINGS` |
| Core quality rules | `SUPPORTED` |
| Quality quarantine | `SUPPORTED_WITH_WARNINGS` |
| Annotations comments | `SUPPORTED` |
| Tags | `SUPPORTED_WITH_WARNINGS` |
| Grants | `SUPPORTED_WITH_WARNINGS` |
| Row access policies | `SUPPORTED_WITH_WARNINGS` |
| Masking policies | `SUPPORTED_WITH_WARNINGS` |
| Scheduled projects | `SUPPORTED` |
| Task dependencies | `SUPPORTED_WITH_WARNINGS` |
| Cost evidence | `SUPPORTED_WITH_WARNINGS` |
| Lineage evidence | `SUPPORTED_WITH_WARNINGS` |

## Acceptance Tests For A Future Adapter

1. Plan the canonical Supabase medallion project against Snowflake and produce
   exact warnings/review items.
2. Render SQL for table, SQL and staged file sources without importing a
   Snowflake client in the core.
3. Execute append, overwrite and current-state upsert in a real Snowflake account.
4. Verify `ctrl_ingestion_runs`, `state`, `quality`, `quarantine`, `errors`,
   `schema_changes`, `annotations`, `access`, `lineage`, `operations`, `explain`
   and `cost` tables use the core schema.
5. Join ContractForge `run_id` to Snowflake `QUERY_HISTORY` through `QUERY_TAG`.
6. Capture task evidence for a scheduled project with at least one dependency.
7. Apply comments/tags and validate them through `TAG_REFERENCES`.
8. Apply row access and masking policies and validate them through
   `POLICY_REFERENCES`.
9. Prove that historical remains `REVIEW_REQUIRED` until the project declares the
   late-arriving, delete and effective-date policies needed for safe execution.
