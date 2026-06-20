# AWS Capability Parity

This document records researched AWS-native capabilities that should inform the `contractforge-aws` adapter roadmap. It exists to avoid under-building the AWS adapter simply because a capability was not part of an earlier implementation pass.

The adapter should aim for the maximum ContractForge semantics that AWS can preserve natively, while still returning `REVIEW_REQUIRED` or `UNSUPPORTED` when semantic equivalence is not proven.

## Primary Runtime Thesis

The primary AWS runtime remains:

```text
AWS Glue Spark
Apache Iceberg
AWS Glue Data Catalog
Amazon S3
AWS Lake Formation
Iceberg evidence tables
```

This target is capable of more than review artifacts:

- Glue supports Apache Iceberg tables and DataFrame writes through the Glue Data Catalog.
- Iceberg tables support append, create/replace and SQL/DataFrame merge patterns through Spark.
- Glue Data Quality provides DQDL and a PySpark `EvaluateDataQuality` transform.
- Lake Formation data filters support column-level, row-level and cell-level access controls for read operations.
- Glue job bookmarks provide incremental source tracking for JDBC and selected S3 formats.
- Glue native connectors and custom connectors provide a better native passthrough target than writing SaaS connector code inside ContractForge.

## Runtime Parity Matrix

| ContractForge area | AWS-native capability | Adapter target status | Implementation direction |
| --- | --- | --- | --- |
| `append` | Iceberg append through Glue Spark/DataFrame writer | `SUPPORTED` | Runtime script generated. If the target table does not exist, the job bootstraps it from the prepared dataframe before future append runs and applies `extensions.aws.iceberg.table_properties` on that create path. Keep table format version and catalog config explicit. |
| `overwrite` | Iceberg create/replace or overwrite patterns | `SUPPORTED_WITH_WARNINGS` | Runtime script generated with create/replace today and applies `extensions.aws.iceberg.table_properties`; add partition/scope-aware overwrite before claiming full production parity. |
| `upsert` | Spark SQL `MERGE INTO` against Iceberg | `SUPPORTED` | Runtime script generated with merge-key guards. If the target table does not exist, the job bootstraps it from the prepared dataframe and applies `extensions.aws.iceberg.table_properties` before future MERGE runs. Needs AWS integration test for concurrency and large upsert volumes. |
| `hash_diff_upsert` | Hash staging plus Iceberg merge | `SUPPORTED_WITH_WARNINGS` | Runtime script generated: merges on `merge_keys`, computes `row_hash` from `hash_keys` or `hash_strategy: all_columns_except`, excludes user-declared and generated columns, prefilters unchanged rows before Iceberg `MERGE`, and records no-change runs as `SKIPPED` / `no_hash_changes`. If the target table does not exist, the job bootstraps it from the prepared dataframe and applies `extensions.aws.iceberg.table_properties`. Performance/concurrency warning stays until validated on Glue. |
| `historical` | Iceberg merge/history pattern | `REVIEW_REQUIRED` | Feasible, but effective dating, deletes, late-arriving policy and concurrent writers need explicit AWS tests. |
| `snapshot_reconcile_soft_delete` | Full snapshot reconciliation plus Iceberg merge | `REVIEW_REQUIRED` | Feasible only when source completeness and target concurrency are proven. |
| `required_columns` | Glue Data Quality `ColumnExists` via `EvaluateDataQuality` | `SUPPORTED` | Evaluated natively in-job; `abort` severity fails the run, results persisted to `ctrl_ingestion_quality`. |
| `not_null` | Glue Data Quality `IsComplete` via `EvaluateDataQuality` | `SUPPORTED_WITH_WARNINGS` | Evaluated natively; `warn` rules record quality evidence and continue; row-level `quarantine` rules write offending rows to `ctrl_ingestion_quarantine`, drop them before the target write and update run quarantine counts. |
| `unique_key` | Glue Data Quality `IsUnique`/`IsPrimaryKey` via `EvaluateDataQuality` | `SUPPORTED` | Evaluated natively in-job; `abort` severity fails the run, results persisted to `ctrl_ingestion_quality`. |
| `accepted_values` | Glue Data Quality `ColumnValues ... in [...]` via `EvaluateDataQuality` | `SUPPORTED_WITH_WARNINGS` | Evaluated natively; non-abort outcomes record quality evidence. Row-level `quarantine` writes offending rows to `ctrl_ingestion_quarantine`, drops them before the target write and updates run quarantine counts. |
| `max_null_ratio` | Glue Data Quality `Completeness` threshold via `EvaluateDataQuality` | `SUPPORTED_WITH_WARNINGS` | Evaluated natively; `warn` outcomes recorded as quality evidence. |
| `expression` quality | Spark SQL DataFrame filter checks | `SUPPORTED_WITH_WARNINGS` | Runtime script generated outside DQDL because the expression dialect is Spark SQL. `abort` fails the run; `warn` records evidence; row-level `quarantine` writes offending rows and filters them before the target write. |
| `select_columns` | Spark DataFrame projection | `SUPPORTED` | Runtime script generated. |
| `column_mapping` | Spark DataFrame rename | `SUPPORTED` | Runtime script generated with collision checks. |
| `filter_expression` | Spark SQL/DataFrame filter | `SUPPORTED_WITH_WARNINGS` | Runtime script generated; expression dialect is Spark SQL, so complex cross-platform filters may need review. |
| `shape.parse_json` | Spark `from_json` and schema structs | `SUPPORTED_WITH_WARNINGS` | Runtime script generated for concrete schemas (and resolved `schema_ref`), with optional `cast_input: STRING` and `drop_source`. |
| `shape.arrays.explode` | Spark explode functions | `SUPPORTED_WITH_WARNINGS` | Runtime script generated for all modes (`size`/`to_json`/`first`/`explode`/`explode_outer`). `explode`/`explode_outer` are blocked in bronze unless `allow_cardinality_change_on_bronze`; sibling explodes under one parent need `allow_cartesian`. |
| `shape.zip_arrays` | Spark `arrays_zip` plus `transform` field renaming | `SUPPORTED_WITH_WARNINGS` | Runtime script generated with temporary array columns so nested paths keep deterministic struct field names. |
| `transform.cast` | Spark DataFrame casts | `SUPPORTED` | Implement in AWS renderer before broad transform support. |
| `transform.standardize` | Spark string functions | `SUPPORTED` | Implement trim/lower/upper/whitespace/null normalization. |
| `transform.derive` | Spark SQL expressions | `SUPPORTED_WITH_WARNINGS` | Feasible; expression dialect must be Spark SQL. |
| `transform.composite_keys` | Spark concat/coalesce functions | `SUPPORTED` | Uses Spark `concat_ws`/`coalesce` with the core contract's delimiter semantics. |
| `transform.deduplicate` | Spark window/grouping | `SUPPORTED_WITH_WARNINGS` | Runtime script generated: `Window.partitionBy(keys).orderBy(order_by)` + `row_number() == 1`. `order_by` is required by the core contract (deterministic); list-of-dicts and simple column-string clauses render, while unsafe free-form SQL strings become review-only. |
| `shape.flatten` | Spark schema introspection + select | `SUPPORTED_WITH_WARNINGS` | Renders a runtime `_cf_flatten` helper that expands struct fields to leaf columns with the contract's separator/include/exclude/max_depth (arrays kept intact). Glue native `Relationalize` is not used because it pivots arrays into separate frames with fixed naming. |
| `shape.columns` | Spark select projection | `SUPPORTED` | Runtime script generated: string shorthand maps a path to an alias; object form supports `expression` (Spark SQL), `cast` and `alias`. |
| `incremental_files` | Glue job bookmarks for selected S3 formats or evidence state | `SUPPORTED_WITH_WARNINGS` | Renders an S3 `create_dynamic_frame.from_options` bookmark read with `transformation_ctx` for JSON/CSV/Parquet/ORC/Avro/XML. Portable CSV options are translated to Glue DynamicFrame options (`header` -> `withHeader`, `delimiter` -> `separator`) and Spark-only options such as `inferSchema` are not passed to Glue bookmark reads. `enable_job_bookmark` wires `--job-bookmark-option`. Unsupported formats stay review-only. |
| JDBC incremental | Glue job bookmarks for JDBC bookmark keys | `SUPPORTED_WITH_WARNINGS` | Runtime script generated when `source.incremental.watermark_column` is a simple column and the JDBC URL/connector maps to a Glue JDBC connection type; otherwise it falls back to the Spark JDBC reader plus core watermark predicates/evidence state. |
| state evidence | Iceberg state tables in Glue Catalog | `SUPPORTED_WITH_WARNINGS` | Generated Glue jobs upsert `ctrl_ingestion_state` after committed writes with run id, status, rows written, Iceberg snapshot id and batch watermark candidates when the declared watermark column exists in the prepared DataFrame. Streaming checkpoint progress is tracked in `ctrl_ingestion_streams`. |
| schema-change evidence | Iceberg schema-change table in Glue Catalog | `SUPPORTED_WITH_WARNINGS` | Generated Glue jobs compare target table schema before/after the write, append added-column and type-change rows to `ctrl_ingestion_schema_changes`, and copy the summary into run evidence. Complex schema policy decisions still require review. |
| `kafka_bounded` / `eventhubs_bounded` | Spark bounded Kafka/Event Hubs read in Glue | `SUPPORTED_WITH_WARNINGS` | Runtime script generated; matching Spark connector jars must be supplied and offset/range semantics remain connector-owned. |
| `kafka_available_now` / `eventhubs_available_now` | Glue structured streaming with the availableNow trigger | `SUPPORTED_WITH_WARNINGS` | Renders a `readStream` + `writeStream.foreachBatch` job with `trigger(availableNow=True)` and the contract's `checkpoint_location`; preparation/quality/write run per micro-batch for append/merge modes. Per-batch evidence is written to `ctrl_ingestion_streams` and rolled into final run evidence. Validate offset/checkpoint progress before production. |
| row filters | Lake Formation data filters | `REVIEW_REQUIRED` | Renders a `CreateDataCellsFilter` scaffold (fail-closed `false` row expression) plus a `SELECT` grant on the filter; the row-filter *function* cannot be auto-translated to an LF `FilterExpression`, so a reviewer completes it. Planning stays `REVIEW_REQUIRED`. |
| column masks | Lake Formation column/cell filters | `REVIEW_REQUIRED` | Renders a data-cells-filter scaffold that excludes the masked column (column-level security); LF has no value-masking function, so a transformed value must come from the ingestion job or a consumer view. Planning stays `REVIEW_REQUIRED`. |
| access grants | Lake Formation grants and IAM policies | `SUPPORTED_WITH_WARNINGS` | `render_aws_lake_formation_plan` emits applyable `GrantPermissions` requests (`.lakeformation.json`), plus `ctrl_ingestion_access` evidence SQL. Write-side job-role permissions are separate from consumer grants. |
| annotations | AWS Glue Catalog table/column metadata | `SUPPORTED_WITH_WARNINGS` | Renders `.annotations.json` with planned `glue:UpdateTable` metadata changes and `.annotations_evidence.sql` for `ctrl_ingestion_annotations`. Application remains explicit because Glue table updates must preserve the full current `TableInput`. |
| operations metadata | Iceberg evidence table in Glue Catalog | `SUPPORTED` | Renders normalized `.operations.json` and `.operations.sql` for `ctrl_ingestion_operations`, preserving owners, groups, criticality, SLA, alert flags, runbook and tags. |
| source metadata / lineage | Glue JobRun, Spark schema metadata, optional OpenLineage export | `SUPPORTED_WITH_WARNINGS` | Generated Glue jobs persist source metadata, rows read, source column count and runtime source schema to `ctrl_ingestion_metadata`, then append OpenLineage-compatible events to `ctrl_ingestion_lineage`. Glue Catalog API enrichment remains adapter-owned future work. |
| cost signals | Glue `DPUSeconds`, worker type/count and job duration | `SUPPORTED` | Reconciliation maps Glue `DPUSeconds` into `ctrl_ingestion_cost`; `*.cost.sql` estimates USD only when an explicit DPU-hour rate is provided. |
| `http_file` (http_csv/json/text) | Driver-side bounded fetch + Spark in-memory parse | `SUPPORTED_WITH_WARNINGS` | Runtime `_cf_http_dataframe` helper validates the resolved host (rejects private/IMDS) and refuses redirects; auth secrets resolve via Secrets Manager. |
| `rest_api` | Shared core bounded REST client | `SUPPORTED_WITH_WARNINGS` | The Glue job calls `contractforge_core.connectors.read_rest_api_records` (pagination/auth/limits, implemented under `contractforge_core.connectors.api.rest`); requires `contractforge-core` on the job. The shared client validates API and OAuth token URLs, rejects unsupported schemes/private hosts by default and refuses redirects. Secrets resolve via Secrets Manager. |
| `delta_share` | Spark Delta Sharing reader | `SUPPORTED_WITH_WARNINGS` | `spark.read.format('deltaSharing')`; provide the delta-sharing-spark jar. |
| native passthrough | Glue native connectors, custom connectors, AppFlow/DMS patterns | `REVIEW_REQUIRED` | Renders `.native_passthrough.json` with AWS-native recommendations and review-only API-shaped candidates for AppFlow `CreateFlow`, DMS `CreateReplicationConfig` and Glue `CreateConnection`. Do not implement SaaS algorithms in ContractForge. |

## Recommended Implementation Order

1. **Preparation parity**
   - Keep `transform.cast`, `transform.standardize`, `transform.derive`, `transform.composite_keys` covered by AWS Glue script tests.
   - Add `transform.deduplicate` only with deterministic order validation. **Done:** runtime generation requires `keys` and `order_by`, then renders a Spark window and `row_number() == 1`.
   - Add `shape.parse_json` for concrete schemas before array explosion. **Done:** runtime generation supports concrete schemas/resolved `schema_ref`, optional `cast_input: STRING`, arrays, zip arrays, columns and flattening with guardrails.

2. **AWS-native quality**
   - Render DQDL artifacts for all portable quality rules with faithful DQDL equivalents. **Done:** `render_aws_quality_dqdl` emits a `Rules = [...]` ruleset (`.quality.dqdl` artifact) mapping `required_columns`/`not_null`/`unique_key`/`accepted_values`/`row_count_minimum`/`max_null_ratio`; `expression` rules are evaluated by Spark SQL runtime checks instead of DQDL.
   - Add a Glue Data Quality runtime path (`EvaluateDataQuality`). **Done:** the job evaluates the DQDL ruleset in-job, partitioned by severity — `abort` rules raise on failure, `warn`/`quarantine` rules continue.
   - Persist DQ results to ContractForge evidence tables. **Done:** one immutable row per rule is appended to `ctrl_ingestion_quality` (`_cf_persist_quality_evidence`) sharing the run's `_cf_run_id`.
   - Enable quarantine/warn runtime behavior. **Done for mapped row-level rules:** non-abort rules are recorded and never fail the run; `not_null` and `accepted_values` quarantine rules use `rowLevelOutcomes` to write offending rows to `ctrl_ingestion_quarantine` and filter them before the target write. Spark SQL expression quarantine rules use DataFrame filters for the same evidence behavior. Aggregate/schema quarantine rules remain recorded evidence only.

3. **Incremental ingestion**
   - Render Glue bookmark configuration for eligible S3/JDBC sources. **Done:** S3 incremental files and eligible JDBC incremental sources render DynamicFrame bookmark reads and enable the job bookmark deployment flag.
   - Record selected incremental strategy in state/evidence.
   - Fallback to ContractForge state tables when bookmarks cannot preserve semantics.

4. **Governance**
   - Generate Lake Formation data filter and grant artifacts. **Done:** `render_aws_lake_formation_plan` emits `GrantPermissions` requests and `CreateDataCellsFilter` scaffolds (`.lakeformation.json`).
   - Keep application behind explicit apply commands.
   - Record governance application evidence.

5. **Advanced write modes**
   - Implement `hash_diff_upsert` with adapter-owned staging. **Done:** runtime generation computes a core-compatible row hash and merges only changed rows.
   - Prototype `historical` and `snapshot_reconcile_soft_delete` in integration tests before changing planning status.

6. **Native passthrough**
   - Add Glue native connector artifacts for supported SaaS systems.
   - Add AppFlow/DMS review/apply artifacts where those services preserve the contract intent better than Glue code.

## Known AWS Constraints To Preserve

- Lake Formation filters apply to read access. They are not the same thing as write-time row rejection or engine-side table functions.
- Glue job bookmarks track source progress; they do not clean up or reconcile target data during rewind/reset.
- JDBC bookmarks depend on suitable bookmark keys and do not support case-sensitive bookmark columns.
- Glue Data Quality can evaluate rich rule sets, but ContractForge row-level quarantine is only enabled where Glue `rowLevelOutcomes` can identify offending rows without changing rule semantics.
- Iceberg support varies by Glue version. The adapter must keep Glue version in runtime configuration and evidence.
- AWS SDK dependencies stay outside the base adapter import path. Runtime helpers may use `contractforge-aws[runtime]` or caller-provided clients.

## Official References

- AWS Glue Iceberg support: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html
- AWS Glue job bookmarks: https://docs.aws.amazon.com/glue/latest/dg/monitor-continuations.html
- AWS Glue JDBC connections: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-connect-jdbc-home.html
- AWS Glue Data Quality: https://docs.aws.amazon.com/glue/latest/dg/glue-data-quality.html
- AWS Glue DQDL reference: https://docs.aws.amazon.com/glue/latest/dg/dqdl.html
- AWS Glue `EvaluateDataQuality`: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-crawler-pyspark-transforms-EvaluateDataQuality.html
- Lake Formation data filters: https://docs.aws.amazon.com/lake-formation/latest/dg/data-filtering.html
- AWS Glue connectors: https://docs.aws.amazon.com/glue/latest/dg/connectors-chapter.html
- AWS Glue native enterprise connectors announcement: https://aws.amazon.com/about-aws/whats-new/2024/11/aws-glue-connectivity-19-native-connectors-enterprise-applications/
