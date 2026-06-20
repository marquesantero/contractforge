# Databricks Adapter Specification

## Purpose

`contractforge_databricks` is the Databricks implementation layer for ContractForge Core.

It may understand Databricks-native concepts, but it must consume ContractForge contracts through public core models:

- `SemanticContract`
- `PlatformCapabilities`
- `PlanningResult`
- `ExecutionPlan`
- `RenderedArtifacts`

Databricks feature parity against the Databricks adapter baseline is tracked in [databricks-contractforge-parity.md](databricks-contractforge-parity.md).

## Domain Layout

The adapter is intentionally split by domain:

- `adapter.py`: small adapter facade.
- `cli.py`: Databricks adapter CLI for registry, template, dashboard and render utilities.
- `capabilities/`: Databricks-native capability evidence and mapping to core capabilities.
- `runtime/`: optional runtime detection. This is the only place where PySpark may be imported.
- `runtime/orchestrator.py`: prepared-view ingestion harness equivalent to the `ingest_plan`-style runtime boundary.
- `rendering/`: artifact bundling and review report rendering.
- `write_modes/`: Databricks write-mode rendering notes and future write implementations.
- `annotations/`: Unity Catalog comments, tags, aliases, PII tags and lifecycle metadata.
- `governance/`: Unity Catalog governance rendering and future application logic.
- `evidence/`: Databricks implementation of the core evidence model.
- `lakeflow/`: Lakeflow AUTO CDC compatibility and artifact planning.
- `parity/`: deterministic write-engine parity catalog ported from ContractForge.
- `sources/`: Databricks source rendering and source artifact routing, including Auto Loader for portable `incremental_files`.
- `presets/`: Databricks-owned preset defaults ported from ContractForge.
- `templates/`: Databricks split-contract template catalog ported from ContractForge.
- `maintenance/`: Databricks table maintenance SQL and control-table retention planning.
- `bundles/`: Databricks Asset Bundle YAML rendering.
- `quality/`: Databricks SQL rendering for portable quality checks.
- `schema/`: Databricks schema policy planning and writer option mapping.
- `state/`: Databricks Delta state, lock and idempotency SQL helpers.
- `lineage/`: OpenLineage event construction and lineage evidence SQL.
- `operations/`: ownership, SLA, support and runbook metadata rendering for Databricks evidence.
- `security/`: redaction helpers for rendered artifacts and evidence payloads.
- `diagnostics/`: Databricks explain-plan diagnostics and supporting DDL.
- `metrics/`: Delta operation metric normalization by ContractForge write mode.
- `partitioning/`: partition predicate and `replaceWhere` rendering.
- `cost/`: logical operational cost and throughput SQL over Databricks evidence.
- `dashboards/`: Databricks SQL/Lakeview control-table dashboard artifacts.
- `watermark/`: Databricks SQL predicates and candidate calculation for core typed watermarks.
- `transforms/`: Databricks SQL review rendering for core transform intent.
- `shapes/`: Databricks SQL review rendering for core shape intent.

## Boundaries

The Databricks adapter may import platform runtime libraries. The core may not.

Runtime imports must be lazy and isolated. Importing `contractforge_databricks` in a local Python process must not require PySpark or Databricks Connect.

Databricks adapts to ContractForge, not the opposite. Concepts such as annotations, operations, access drift policy, SCD modes, evidence and governed source intent remain ContractForge semantics even when the Databricks adapter currently has the richest implementation.

## Environment Binding

The Databricks adapter can consume the core `environment` contract.

Adapter-owned interpretations:

- `environment.runtime.kind` may provide runtime evidence when explicit runtime evidence is not passed by the caller.
- `environment.deployment.workspace_path` controls generated notebook paths in Databricks Asset Bundle artifacts.
- `environment.deployment.target` controls the generated bundle target name.
- `environment.evidence.catalog` and `environment.evidence.schema` control Delta evidence, state, diagnostics, lineage and cost artifact locations.
- `environment.parameters.databricks` is reserved for Databricks-native defaults and deployment parameters.

The environment contract does not alter source, target table, write mode, annotations, operations or access semantics.

## Naming Binding

The Databricks adapter uses core naming policy only for derived Databricks artifacts:

- artifact prefix
- Databricks Asset Bundle name
- job name
- task key

It does not rewrite the physical target table. The target catalog, schema and table come from the core target intent.

## Current Scope

The current adapter supports dry planning and reviewable artifact rendering:

- capability evidence JSON
- planning review Markdown
- write mode SQL notes
- annotations SQL notes
- annotations audit SQL insert template
- governance SQL notes
- access audit SQL insert template
- schema policy JSON
- source metadata JSON
- evidence table mapping notes
- state and lock table DDL
- OpenLineage insert template
- diagnostics table DDL
- operational cost query
- operations metadata JSON and SQL evidence insert template
- typed watermark SQL predicate and candidate calculation
- transform SQL review artifact
- shape SQL review artifact
- Databricks-owned preset and template catalog for split contracts
- control-table dashboard SQL and blueprint artifacts
- Databricks runtime ingestion harness over prepared source views
- Databricks adapter CLI entry point for registry, dashboard and artifact rendering
- control-table retention SQL planning
- cost-report SQL planning over control-table run evidence
- core naming policy for bundle, job, task and artifact names
- Lakeflow compatibility report
- parity catalog queries for native-write validation harnesses

Capability evaluation is intentionally non-destructive. It classifies passive runtime evidence and target naming shape for:

- Databricks runtime and serverless runtime
- Delta tables and SQL MERGE
- Unity Catalog comments, tags, grants, row filters and column masks
- Unity Catalog ABAC policies, External Locations and Volumes
- Databricks Connections
- Auto Loader `cloudFiles`
- Lakeflow Declarative Pipelines and AUTO CDC
- Liquid Clustering
- Databricks Delta evidence stores and snapshot soft-delete MERGE eligibility

Workspace-scoped features generally return `unknown` when the runtime and target are eligible but permissions/configuration have not been probed. That status is deliberate review evidence, not a failure.

It also includes a narrow execution helper for `upsert` through Databricks SQL MERGE:

- `execution/sql_merge.py`
- deterministic SQL rendering
- injected SQL runner protocol
- no top-level Spark or Databricks SDK dependency

Additional write-mode execution helpers follow the same pattern:

- `execution/delta_basic.py`: `append` and `overwrite`
- `execution/hash_diff.py`: ContractForge-compatible `hash_diff_upsert` insert over a prepared hash staging view
- `execution/scd2.py`: ContractForge-compatible `historical` Delta MERGE over a prepared historical staging view
- `execution/snapshot.py`: ContractForge-compatible `snapshot_reconcile_soft_delete` Delta MERGE over a prepared snapshot staging view

The final write SQL assumes PySpark preparation has already produced the required columns and staging views.

## Write Metrics

The adapter normalizes Databricks Delta `operationMetrics` into ContractForge row counters:

- `rows_inserted`
- `rows_updated`
- `rows_deleted`
- `rows_expired`
- `rows_affected`

When Delta history is available, the adapter combines physical Delta metrics with logical row counts. For `historical`, updated rows are also treated as expired historical rows for normalized evidence. When Delta metrics are missing, the adapter falls back to logical metrics derived from the write mode and rows written.

Metric normalization is adapter-owned because Delta operation metric names and physical update behavior are platform-specific.

Runtime code may use `render_delta_history_query()` to collect the latest `DESCRIBE HISTORY` row and `latest_operation_metrics_from_history_row()` to extract the stable payload consumed by `resolve_write_metrics()`.

## Cost Signals

The adapter renders logical operational cost SQL over Databricks evidence tables.

The cost model accepts:

- `dbu_per_hour`
- `currency_per_dbu`
- `currency`

This is not provider billing reconciliation. It estimates compute cost from recorded run duration and a user-supplied hourly DBU rate, then derives throughput and cost-per-million-row signals. Real billing joins remain platform/workspace-specific future work.

## Future Execution Modules

Execution should be added behind explicit modules, for example:

- `execution/delta_writes.py`
- `execution/sql_merge.py`
- `execution/scd2_merge.py`
- `execution/snapshot_reconcile_soft_delete.py`
- `execution/governance_apply.py`
- `execution/evidence_writer.py`

These modules must not be imported by the top-level package unless their platform dependencies are optional and lazy.

Execution modules should accept small injected dependencies, such as a SQL runner, Spark session, filesystem client, or workspace client. This keeps business semantics testable without a live Databricks workspace.

## Preparation vs Execution Pattern

The Databricks adapter uses a hybrid pattern:

```text
source/read/shape/quality/hash/dedup
        PySpark preparation
          |
prepared temp view or staged Delta table
          |
write-mode execution
        SQL MERGE / INSERT / ALTER
          |
evidence/governance
        SQL artifacts and small runtime helpers
```

Use SQL for final table operations:

- `MERGE`
- `INSERT INTO`
- `INSERT OVERWRITE`
- `ALTER TABLE`
- comments, tags, aliases, PII metadata and deprecation markers
- grants, row filters and masks
- evidence/control table DDL
- additive evidence/control table migration SQL
- partition predicates and scoped overwrite review

Use PySpark for preparation:

- connector reads
- Auto Loader
- shape and flatten operations
- complex transform execution where SQL review is not sufficient
- row hash and hash diff preparation
- deduplication
- quality checks and quarantine preparation
- schema normalization
- emergency string encoding repair through `extensions.databricks.fix_encoding`

This keeps final Databricks operations auditable while preserving the mature ContractForge algorithms where Databricks-native features are not semantically equivalent.

## Runtime Ingestion Harness

The adapter exposes `runtime.ingest_databricks_contract()` as the Databricks equivalent of the Databricks adapter baseline `ingest_plan` orchestration boundary.

The harness accepts:

- a core semantic contract or validated contract mapping
- an injected SQL runner
- a `PreparedViewInput` describing an already prepared Databricks temp view or staging view
- `DatabricksIngestOptions` for evidence location, locks, idempotency, dry-run and runtime metadata
- optional quality results and an idempotency lookup callback

Implemented behavior:

- plan validation against Databricks capabilities before execution
- idempotent skip/fail behavior over `ctrl_ingestion_runs`
- optional lock acquire/release over `ctrl_ingestion_locks`
- dispatch to Databricks write-mode executors for append, overwrite, current-state, hash diff, historical and snapshot soft delete
- run ledger persistence through `ctrl_ingestion_runs`
- failure persistence through `ctrl_ingestion_errors`
- state persistence through `ctrl_ingestion_state`

The harness deliberately starts after source reading and PySpark preparation. Connector reads, shape normalization, row hash preparation, historical staging and quarantine materialization remain Databricks runtime preparation concerns. This keeps the core platform-neutral while preserving the Databricks adapter baseline execution lifecycle in the Databricks adapter.

## Databricks CLI

The adapter wheel exposes a `contractforge-databricks` console script backed by `contractforge_databricks.cli:main`.

This entry point belongs to the `contractforge-databricks` distribution, not to the `contractforge-core` wheel.

Implemented commands:

- `presets list|show`
- `templates list|show|write|wizard`
- `dashboard`
- `render`

The CLI is adapter-scoped. It does not make the core executable and does not require Spark, Databricks SDK or workspace credentials at import time.

Workspace mutation, bundle deployment and live job execution remain deployment concerns. The CLI renders reviewable artifacts and split-contract examples that a CI/CD pipeline or Databricks workspace workflow may consume.

## Transform Interpretation

The core carries transform intent; the Databricks adapter interprets it.

Implemented review artifact:

- `transforms.render_transform_sql()`
- `transform.cast`
- `transform.standardize`
- `transform.derive`
- `transform.deduplicate`

The generated SQL is a reviewable Databricks representation of the intent. Runtime code may execute equivalent PySpark preparation when that is safer for complex schemas, shape interactions or connector-specific DataFrame preparation.

Shape execution remains PySpark-preparation oriented for Databricks because JSON parsing, arrays, flattening and cardinality-changing operations are DataFrame-shaped semantics. The core preserves the contract; the adapter owns execution.

## Shape Interpretation

The Databricks adapter renders a `*.shape.sql` review artifact for core shape intent.

Implemented review coverage:

- `shape.parse_json` as `from_json(...)`
- `shape.zip_arrays` as `arrays_zip(...)`
- `shape.arrays` as `to_json`, `size`, `element_at`, `explode` or `explode_outer`
- `shape.columns` as projection, expression and cast
- flatten and cardinality-changing operations as explicit review notes

The SQL artifact is not a promise that every nested-shape operation should execute as SQL. Complex flattening, schema-aware nested expansion and cardinality-changing operations are expected to run through adapter-owned PySpark preparation in Databricks when needed.

## Source Translation

The Databricks adapter translates portable source intent to Databricks-native reads when safe.

`source.type: incremental_files` renders an Auto Loader `cloudFiles` read artifact. This is the preferred portable contract surface when the source itself is an incremental file source.

The adapter also treats object-storage and file sources with `source.intent: file_stream` as Databricks incremental-file semantics. For example, `source.type: s3` plus `source.intent: file_stream` renders the same Auto Loader path while preserving the raw core source type for evidence. This is a first-class adapter translation, not a compatibility alias: the contract states portable intent, and the adapter maps that intent to the Databricks-native capability.

Adapter-local Databricks migration tooling may recognize native Auto Loader vocabulary, but `contractforge_core` does not define it. Portable contracts must use `source.type: incremental_files`.

The adapter interprets core source parameters before rendering:

| Core parameter | Databricks rendering |
| --- | --- |
| `source.progress_location` | available-now/stream checkpoint location variable |
| `source.state.location.path` where `source.state.storage: external` | fallback available-now/stream checkpoint location for `source.intent: file_stream` |
| `source.schema_tracking_location` | `cloudFiles.schemaLocation` |
| `source.schema_hints` | `cloudFiles.schemaHints` |
| `source.max_files_per_trigger` | `cloudFiles.maxFilesPerTrigger` |
| `source.options.infer_column_types` | `cloudFiles.inferColumnTypes` |
| `environment.parameters.databricks.incremental_files.*` | Databricks source defaults |

This interpretation layer is adapter-owned. The core does not validate or know `cloudFiles` parameters.

JDBC batch sources render a Databricks PySpark `spark.read.format("jdbc")` artifact for:

- `jdbc`
- `postgres`
- `mysql` / `mariadb`
- `sqlserver`
- `oracle`
- `redshift`

The renderer validates `table`/`query` exclusivity, maps partitioned read options, and emits redacted review options. Oracle remains supported as a contract/source type, but the adapter does not bundle Oracle JDBC drivers; the Databricks runtime or job deployment must provide the driver.

Databricks JDBC sources must not declare inline credentials. `auth.password`, `options.password`, `options.sfpassword` and JDBC URLs containing `user:password@host` are rejected unless the value is expressed with a `{{ secret:scope/key }}` placeholder or an adapter-owned runtime authentication mechanism such as RDS IAM. This matches the AWS adapter principle that contract files and rendered artifacts must not carry real credentials.

For RDS IAM JDBC authentication, the adapter preserves the Databricks adapter baseline boundary:

- `auth.type: rds_iam` is recognized.
- host, port and AWS region are derived from the JDBC URL when possible.
- rendered review options use `{{rds_iam_token}}` instead of embedding a token.
- `sources.generate_rds_iam_auth_token()` provides a pure SigV4 helper for runtime code that chooses to generate tokens inside the Databricks job.

The adapter does not require `boto3`, `botocore` or AWS credentials at import/render time.

Batch file and object-storage sources render Databricks `spark.read` artifacts for:

- `csv`
- `json` / `jsonl` / `ndjson`
- `parquet`
- `delta`
- `orc`
- `text`
- `avro`
- `xml`
- object-storage aliases such as `s3`, `adls`, `azure_blob`, `gcs`, `blob` and `object_storage` when `format` and `path` are declared

XML rendering uses `spark.read.format("xml")` and passes parser options from `source.options`. Databricks runtimes must provide native XML support or an equivalent compatible parser; otherwise the adapter should surface a runtime/capability warning instead of silently changing format.

Catalog sources render `spark.table(...)`, `spark.sql(...)` or path-based `spark.read.format(...).load(...)` artifacts for `table`, `view`, `sql`, `delta_table` and `iceberg_table` contracts.

Delta Sharing consumer sources render `spark.read.format("deltaSharing")` artifacts for `delta_share` contracts with profile file and shared table identifiers. Profile files and credentials remain deployment/runtime concerns.

HTTP file sources render bounded Python `urllib` fetch artifacts followed by Spark file reads:

- `http_file`
- `http_csv`
- `http_json`
- `http_text`

The renderer supports request headers, bearer-token auth, API-key header auth, timeout and max-bytes guardrails. HTTP file rendering is intended for small and medium bounded files, not SaaS API pagination or long-running API extraction.

The generated Databricks artifact also preserves the Databricks adapter baseline bounded-file behavior for:

- query parameters from `source.request.params`
- GET-only enforcement
- retry attempts and linear backoff for transient HTTP/network errors
- Spark reader options such as CSV headers, delimiters and JSON options

Generic REST API connector contracts render a review artifact and expose a bounded runtime resolver:

- `connector: rest_api`
- `connector: api`
- `connector: http_api`

The artifact recommends either:

- `http_file`/`http_json`/`http_csv` when the source is a bounded public or authenticated file.
- `native_passthrough` for proprietary SaaS APIs.
- a reviewed landing step to object storage followed by `incremental_files`.

The runtime resolver is intentionally bounded and supports the Databricks adapter baseline generic REST semantics that can be executed safely without a SaaS-specific connector:

- GET and POST requests
- request params, headers, JSON/body payloads and redacted auth evidence
- bearer token, API key, basic auth and OAuth client credentials
- page, offset, cursor and Link-header pagination
- response records path or raw payload mode
- max page bytes, max total bytes, max records, retry attempts, retry backoff and rate-limit spacing through `limits.rate_limit_per_minute`
- incremental watermark injection into query params, headers or JSON body fields

For raw response mode, `source.response.raw_column` must be a simple column name. Complex SaaS semantics still belong in `native_passthrough` or a reviewed landing step to object storage followed by `incremental_files`.

The bundle emits `*.source_metadata.json` for every contract. This artifact normalizes source evidence for Databricks control/evidence workflows:

- source type and kind
- connector and provider
- path, URL, table, query or object identifiers
- read/options/request/auth/pagination/response sections
- incremental and limit metadata
- source capability hints such as bounded, incremental and native passthrough

Sensitive values are redacted before rendering. This ports the Databricks adapter baseline source metadata discipline into the Databricks adapter without requiring the core to understand Delta control-table columns.

Bounded stream sources render finite Databricks batch read artifacts:

- `kafka_bounded` renders `spark.read.format("kafka")` with topic/assign and starting/ending offset or timestamp options.
- `eventhubs_bounded` renders `spark.read.format("eventhubs")` with reviewed Event Hubs connector options.

These artifacts are for catch-up/replay only. They intentionally use `spark.read`, not `spark.readStream`, and must not be treated as continuous streaming jobs.

Native passthrough sources are intentionally not implemented as custom Python API clients in the adapter. Future work should render Lakeflow Connect, Databricks Connections or other native workspace artifacts where available.

For `source.type: native_passthrough`, the adapter emits a planning artifact:

- `*.native_passthrough.json`

The artifact records:

- source system
- source object
- recommended Databricks native targets
- watermark intent
- redacted auth metadata
- notes preventing accidental custom SaaS client implementation

Example recommendation:

| Source system | Recommended Databricks target |
| --- | --- |
| Salesforce | Lakeflow Connect |
| Workday | Lakeflow Connect |
| ServiceNow | Lakeflow Connect |
| SFTP/FTP | Databricks Connection + Auto Loader |
| Other systems | Databricks Connection or Lakeflow Connect if available |

## Lakeflow AUTO CDC Artifacts

The adapter exposes an explicit Lakeflow AUTO CDC Python renderer.

It requires:

- reviewed source table/view name or snapshot function
- keys
- `sequence_by` for historical change-feed flows
- compatibility check passing without unsupported blockers

Supported rendering paths:

- `source_kind="change_feed"` renders `dp.create_auto_cdc_flow(...)`.
- `source_kind="snapshot"` renders `dp.create_auto_cdc_from_snapshot_flow(...)`.

`render_lakeflow_auto_cdc_artifact()` returns a serializable review artifact with:

- language
- source kind
- generated Python code
- compatibility status
- mapped Lakeflow fields
- required fields
- translation-required fields
- unsupported fields
- warnings

`render_lakeflow_auto_cdc_python()` remains a convenience wrapper returning only the generated code.

The renderer uses the core target intent as the Databricks table name. When the contract declares catalog and schema, the generated Lakeflow artifact targets the fully qualified table name.

Supported adapter-owned options:

- `ignore_null_updates`
- `once`
- `apply_as_deletes` from the ContractForge historical write intent for change-feed flows
- `apply_as_truncates` for current-state change-feed flows
- `track_history_column_list` from `scd2_change_columns`

Explicit semantic blockers:

- `apply_as_truncates` is rejected for historical because it is an current-state Lakeflow option.
- snapshot flows reject CDC delete predicates because deletes are derived from snapshot comparison.
- shape, transform, projection, column mapping, filter, watermark and quality intent require upstream materialization or external enforcement before AUTO CDC consumes the prepared source table/view.

The renderer is intentionally not added automatically to the contract bundle because Lakeflow execution requires source CDC/snapshot semantics and workspace pipeline readiness that must be reviewed separately.

## Evidence Implementation

The Databricks adapter implements the core evidence model with Delta tables.

Implemented pieces:

- `evidence/ddl.py`: `CREATE SCHEMA` and `CREATE TABLE ... USING DELTA`.
- `evidence/schemas.py`: full ContractForge control-table schema catalog for Databricks Delta evidence tables.
- `evidence/records.py`: run, error, quality, lineage, schema-change and cost evidence records.
- `evidence/sql.py`: deterministic `INSERT INTO` statements.
- `evidence/run_log.py`: full `ctrl_ingestion_runs` insert rendering from runtime payloads with type coercion and redaction.
- `evidence/ops_log.py`: full `ctrl_ingestion_errors`, `ctrl_ingestion_schema_changes` and `ctrl_ingestion_streams` rendering plus stream child-run metric aggregation SQL.
- `evidence/governance_log.py`: full `ctrl_ingestion_annotations`, `ctrl_ingestion_access` and `ctrl_ingestion_operations` runtime log rendering.
- `evidence/writer.py`: SQL runner based writer.
- `operations/sql.py`: operations metadata normalization and `ctrl_ingestion_operations` insert template.
- `state/migrations.py`: additive control-table migration planning ported from ContractForge.

The core still uses the platform-neutral term evidence model. Delta control tables are only the Databricks adapter persistence implementation.

New Databricks evidence tables are created with the mature ContractForge control-table columns where they are table-local. The Databricks DDL keeps the Databricks Delta partitioning for high-volume ledgers: `ctrl_ingestion_runs` by `run_date` and `ctrl_ingestion_errors` by `error_date`. The bundle also emits `*.control_table_migrations.sql` as a review artifact for existing installations. It contains additive `ALTER TABLE ... ADD COLUMNS` statements for fields such as idempotency metadata, runtime evidence, source metadata, write-engine selection, write timing/version evidence, parent-run hierarchy, state write markers, annotation results, ownership, access drift policy and lock release metadata. Operators should apply only columns that are missing; the core never mutates evidence storage directly.

Runtime code can use `EvidenceWriter.write_run_log()` or `render_run_log_insert_sql()` to persist a complete `ctrl_ingestion_runs` row from adapter runtime payloads. These helpers coerce integer, boolean, date and timestamp fields, serialize `*_json` fields, and redact sensitive values before rendering SQL. The Databricks runtime populates write start/finish timestamps and `stage_durations_json` for schema setup, merge preflight, write execution, post-write maintenance and governance side effects.

Runtime code can also use:

- `EvidenceWriter.write_error_log()` / `render_error_log_insert_sql()`
- `EvidenceWriter.write_schema_change_log()` / `render_schema_change_log_insert_sql()`
- `render_schema_change_log_insert_sqls()` for ContractForge-style schema diff payloads
- `EvidenceWriter.write_stream_log()` / `render_stream_log_insert_sql()`
- `EvidenceWriter.finish_stream_log()` / `render_stream_finish_update_sql()`
- `render_stream_child_run_metrics_sql()`
- `EvidenceWriter.write_annotation_log()` / `render_annotation_log_insert_sql()`
- `render_annotation_log_insert_sqls()` for applied comment/tag entries
- `EvidenceWriter.write_access_log()` / `render_access_log_insert_sql()`
- `render_access_log_insert_sqls()` for grants, row filters and masks
- `EvidenceWriter.write_operations_log()` / `render_operations_log_insert_sql()`

These port the Databricks adapter baseline control-table logging behavior without importing Spark at module import time. The runtime owns execution by passing a Databricks SQL/Spark runner that implements `sql(statement)`.

Bundle ingestion supports core `execution.window` and enabled `execution.catchup` contracts. The Databricks adapter expands the parent contract into child runs, adds a Databricks SQL timestamp window predicate to the canonical `filter_expression`, creates a separate prepared source view per window, and persists each child in `ctrl_ingestion_runs` with:

- `parent_run_id` pointing to the parent bundle run
- window-scoped `idempotency_key` values when the parent contract declares idempotency
- `_contractforge_window_label`, `_contractforge_window_column`, `_contractforge_window_start` and `_contractforge_window_end` in `runtime_parameters_json`

This is adapter-owned execution behavior. The core only validates and carries the portable execution intent.

Available-now streaming preserves the Databricks adapter baseline stream observability pattern when an `EvidenceWriter` is supplied to `run_available_now_stream()`:

- a `RUNNING` row is inserted into `ctrl_ingestion_streams` before the Structured Streaming query starts
- the final stream row is updated through `finish_stream_log()` after termination
- failed streams write a full error row into `ctrl_ingestion_errors`
- local micro-batch metrics are reconciled with persisted child-run metrics from `ctrl_ingestion_runs.parent_run_id` when a `query_one` reader is supplied

This keeps the serverless/Spark Connect behavior from the Databricks runtime implementation: if `foreachBatch` callback state is not reliable in the driver process, the evidence tables remain the source of truth for batch counts and row totals.

`ctrl_ingestion_operations` preserves the Databricks adapter baseline operational metadata pattern: criticality, expected frequency, freshness SLA, alerting flags, runbook URL, ownership, owners, groups and tags. The core carries this as semantic operations metadata; Databricks owns the Delta persistence shape.

`ctrl_ingestion_annotations` preserves the Databricks adapter baseline annotation audit boundary for comments, tags, aliases, PII metadata and deprecation markers. The adapter renders the SQL artifacts and exposes the Delta table DDL; runtime application can record per-step status without the core knowing about Unity Catalog.

## Annotations And Governance

The adapter keeps descriptive annotations separate from access governance.

`annotations/` renders Unity Catalog metadata:

- table comments
- column comments
- table tags
- column tags
- aliases rendered as deterministic `alias_N` tags
- PII metadata rendered as column tags
- deprecation lifecycle metadata rendered as table or column tags
- per-step audit insert templates for `ctrl_ingestion_annotations`

`governance/` renders access controls:

- grants
- row filters
- column masks
- owner review notes
- per-step audit insert templates for `ctrl_ingestion_access`

The bundle emits `*.annotations.sql`, `*.annotations_audit.sql`, `*.governance.sql` and `*.access_audit.sql`. For backward review compatibility, `*.governance.sql` also includes the annotations SQL when annotations are declared.

These artifacts remain reviewable SQL. The core carries only semantic governance and annotation intent; Unity Catalog SQL is adapter-owned.

The access audit template follows the Databricks adapter baseline control-table shape: access type, principal, privilege, column/function/object names, applied SQL, mode, drift policy and revoke-unmanaged intent. Runtime execution can mark each step as applied, validated, warned, failed or ignored.

Runtime application helpers are adapter-owned and use injected SQL runners:

- `annotations.apply_annotations_contract()`
- `governance.apply_access_contract()`
- `operations.record_operations_contract()`

They do not import Spark or Databricks SDKs. Runtime code passes a Databricks SQL/Spark runner that implements `sql(statement)`. Access drift inspection can additionally use a runner-provided `query(statement)` method to read `SHOW GRANTS ON TABLE ...`; runners that do not expose query support still render and apply declared access SQL without attempting catalog drift inspection.

The application helpers execute native metadata SQL and return status objects. The evidence/governance log helpers persist detailed runtime audit rows. Keeping these separate lets deployments choose apply-only, evidence-only or apply-and-record behavior explicitly.

Supported application behavior:

- annotations `policy=ignore` returns `IGNORED` without execution
- annotations `policy=warn` records failures in the result and continues
- annotations `policy=fail` returns `FAILED` on first failed statement
- access `mode=ignore` returns `IGNORED` without execution
- access `mode=validate_only` returns `VALIDATED` without execution
- access apply mode executes grants, row filters and masks
- access `on_drift=fail` returns `FAILED` on detected current-vs-declared grant drift when query support is available, or on the first failed statement during apply
- access `revoke_unmanaged=true` can render and execute `REVOKE` steps for unmanaged grants, but only when the caller explicitly passes the adapter runtime confirmation for destructive reconciliation
- operations metadata is recorded into the Databricks evidence location resolved from the environment contract
- operations recording returns `NOT_CONFIGURED` when the contract has no operations metadata
- runtime helper errors are shortened and redacted before being returned in result objects

## Operational Error Handling

The Databricks adapter normalizes operational errors before exposing them in runtime results or evidence payloads.

Implemented behavior:

- secret-bearing strings are redacted
- stack traces are reduced to the most relevant final line
- `Caused by`, storage, SQL, analysis and Delta error lines are preferred when present
- normalized messages are bounded in length

This is adapter-owned because Databricks, Spark, JVM and connector failures have platform-specific stack-trace shapes. The core evidence model only requires an error concept; it does not prescribe Databricks error parsing.

## Operational State

The adapter provides Databricks Delta SQL for operational state that ContractForge historically stores in control tables:

- target watermark state
- last successful run metadata
- best-effort target locks
- idempotent run lookup SQL
- idempotent stream lookup SQL
- lock status read-back SQL
- successful-run existence SQL
- control schema metadata registration SQL

These helpers live under `contractforge_databricks.state` and use injected SQL runners for execution. The core does not import this package and does not require Delta tables.

`StateWriter.record_control_metadata()` records the `contractforge` component row in `ctrl_ingestion_metadata`, matching the Databricks adapter baseline control-table version registration pattern. Lock acquisition remains best-effort: the adapter renders both the `MERGE` statement and `render_lock_status_sql()` so runtime code can verify that the current `run_id` owns the active lock after the merge.

## Watermarks

The core owns the typed watermark JSON format. The Databricks adapter owns SQL application:

- `watermark.render_watermark_filter_predicate()` renders simple and composite lexicographic predicates.
- `watermark.render_select_watermark_candidate_sql()` renders SQL to calculate the next typed candidate from a Databricks table.
- `state.render_select_previous_watermark_sql()` reads the last committed target watermark from `ctrl_ingestion_state`.

This ports the Databricks adapter baseline simple/composite watermark behavior while keeping Spark execution out of the core. Databricks bundle source preparation can read the previous state value through an injected query runner, apply the adapter-owned SQL predicate before registering the prepared view, and persist both `watermark_previous` and `watermark_current` in `ctrl_ingestion_runs` after a successful write.

The runtime applies the previous-watermark predicate after projection, column mapping, shape handling, casts, standardization, derived columns, filter expression and composite key construction, and before deduplication. This preserves the Databricks adapter baseline preparation order while allowing canonical watermark columns to be produced by the contract preparation step.

## Lineage

The adapter can render OpenLineage-compatible events and persist them as Databricks evidence.

Implemented pieces:

- namespace defaults to `databricks://<catalog>`
- event type maps successful runs to `COMPLETE` and failures to `FAIL`
- input/output schema facets can be supplied by runtime code
- output row count is emitted as a data-quality metric facet
- ContractForge-specific metrics are redacted before persistence

The bundle emits `*.openlineage.sql` as a review template. Runtime code should fill real run ids, timestamps, row counts, schemas and operation metrics before writing lineage evidence.

## Diagnostics

The adapter supports Databricks-specific diagnostic artifacts without making diagnostics a portable core execution concern.

Implemented pieces:

- `ctrl_ingestion_explain` DDL
- deterministic explain-plan insert SQL
- redaction and truncation before persistence

Spark `DataFrame.explain()` capture is intentionally not implemented at import time. Runtime code may capture explain text inside Databricks and pass the text into the diagnostics renderer.

## Quality

The adapter renders SQL checks for portable quality rules normalized by the core:

- `required_columns`
- `not_null`
- `unique_key`
- `accepted_values`
- `row_count_minimum`
- `max_null_ratio`
- `expression`

Quality execution and evidence persistence are adapter-owned. The core only carries the semantic intent.

Implemented pieces:

- SQL check rendering for review and runtime execution.
- qualified-table required-column checks through `system.information_schema.columns`.
- required-column review comments for temp views where SQL cannot inspect the schema.
- `QualityRuleResult` normalization with `PASSED`, `WARNED`, `FAILED` and `NOT_CONFIGURED` aggregate status.
- quarantine filtering for failed rules with `severity=quarantine`.
- SQL rendering for quality evidence inserts.
- SQL rendering for quarantine reference inserts.

The adapter stores quarantine references, not arbitrary source payloads, at this layer. Runtime code may persist row payloads to a secured platform location and pass the reference into the evidence renderer.

## Schema Policy

The adapter maps core schema policy intent to Databricks-specific execution requirements:

- `strict`: requires preflight schema comparison and does not enable Delta `mergeSchema`.
- `additive_only`: requires preflight validation and enables `mergeSchema` for nullable additive columns.
- `permissive`: enables `mergeSchema`, requires preflight, and records type widening or other changes as schema-change evidence.

The bundle emits `*.schema_policy.json` so deployment review can see writer options, warnings and required checks before execution.

Schema preflight is implemented as pure comparison logic:

- `compare_schema()` compares source and target `column -> type` maps.
- `validate_schema_diff()` enforces `strict`, `additive_only` and `permissive`.
- `render_add_columns_sql()` renders additive Delta evolution.
- `render_type_widening_sql()` renders reviewed type widening.

Runtime code is responsible for reading actual Databricks table schemas and passing normalized type maps into these helpers.

## Maintenance

The adapter exposes table maintenance SQL helpers:

- `ALTER TABLE ... SET TBLPROPERTIES`
- `OPTIMIZE`
- `VACUUM`
- `ANALYZE TABLE ... COMPUTE STATISTICS`
- historical control-table retention `DELETE` statements
- optional control-table `VACUUM` statements
- query-only operational cost reports from `ctrl_ingestion_runs`, including grouping, success-only filtering, currency/rate estimation and row limit metadata for optional execution surfaces

Maintenance remains adapter-owned because optimization features and retention policies are platform-specific.

## Databricks Asset Bundles

The adapter can render a reviewable `databricks.yml` artifact for a contract.

This is only artifact generation. The adapter does not call Databricks CLI, deploy jobs, or mutate the workspace from the core planning path.

Generated bundle artifacts are intended to be checked into a deployment repository or passed to a CI/CD stage that owns Databricks deployment credentials.

## Templates And Presets

The adapter ports the mature ContractForge built-in presets and split-contract templates as Databricks-owned catalog artifacts.

Implemented pieces:

- `presets.list_presets()`, `get_preset()`, `preset_details()` and `apply_preset()`
- `templates.list_contract_templates()`, `get_contract_template()`, `contract_template_details()`, `contract_template_files()` and `recommend_contract_templates()`
- bronze, silver and gold scenario coverage for Auto Loader/incremental files, HTTP file snapshots, object storage, JDBC current-state, hash diff, historical, snapshot soft delete, Lakeflow AUTO CDC review artifacts and gold full refresh
- the full Databricks adapter baseline preset count is represented: 29 Databricks-owned presets covering bronze ingestion, silver SCD/write modes, gold serving patterns, Delta properties, quality policy, runtime defaults, governance defaults and write-engine preview selection
- CLI parity includes `templates wizard` recommendations and optional bundle materialization through `--output`, matching the interactive workflow without moving templates into the core CLI

The preset catalog is split by domain (`bronze`, `silver`, `gold`, `modifiers`, `runtime`, `write_engine`) so new defaults do not accumulate in one central file. Native Databricks terms such as Auto Loader remain acceptable in adapter preset/template names, but contract payloads use canonical core source names such as `incremental_files`. The adapter translates those semantics to Databricks runtime behavior.

These helpers are not part of `contractforge_core`. They are Databricks adapter examples and defaults. Core contracts stay semantic; the adapter catalog shows how those semantics are commonly used on Databricks.

## Control Dashboard

The adapter ports the Databricks adapter baseline operations command center as Databricks-owned artifacts over the evidence/control tables.

Implemented pieces:

- `dashboards.control_dashboard_queries()` returns the 22-query catalog.
- `dashboards.render_control_dashboard_sql()` renders Databricks SQL over the selected evidence catalog/schema.
- `dashboards.control_dashboard_blueprint()` groups the queries into overview, reliability, performance, quality, streaming and governance pages.
- `dashboards.render_control_dashboard_artifacts()` emits SQL plus a serializable blueprint.

Dashboard rendering is adapter-owned because table names, SQL dialect, visualization targets and Lakeview deployment are Databricks-specific.
