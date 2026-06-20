# AWS Adapter Specification

## Purpose

The AWS adapter translates ContractForge semantic contracts into AWS-native planning, rendering and, in later phases, execution artifacts.

The implementation roadmap is informed by the researched AWS parity matrix in [AWS capability parity](aws-capability-parity.md). That matrix should be updated whenever AWS-native Glue, Iceberg, Lake Formation, Data Quality or connector capabilities change.

Runtime stabilization is governed by [AWS stabilization matrix](aws-stabilization-matrix.md). That matrix is the release gate for real AWS projects, failure-path evidence, control-table audits and production-hardening checks.

The initial adapter target is `aws_glue_iceberg`:

- runtime: AWS Glue Spark;
- table format: Apache Iceberg on Amazon S3;
- catalog: AWS Glue Data Catalog;
- governance: AWS Lake Formation;
- evidence: Iceberg evidence tables, with S3 JSON artifacts as a future fallback/export.

The adapter starts with planning and rendering, but now includes bounded runtime
helpers for artifact publication, Glue job registration, Glue job start/status
inspection and cost-gated smoke validation. Default Glue deployments use a
stable AWS library runner script that receives contract/environment artifact
URIs as Glue arguments. The runner loads the published contract inside Glue,
uses the adapter renderer as the compatibility base, and executes the rendered
Glue/Spark body in the Glue process. The base import path remains SDK-free; AWS
API helpers require the optional runtime extra or caller-provided clients.

## Design Principles

- The core does not import `boto3`, AWS SDKs or Glue libraries.
- The base AWS adapter package does not require `boto3`; AWS API helpers live behind an optional runtime extra.
- AWS-specific choices are expressed through adapter capabilities, diagnostics and artifacts.
- AWS subtargets are explicit. There is no generic "AWS can do everything" capability declaration.
- Glue job bookmarks are adapter implementation details, not core semantics.
- Lake Formation mappings start conservative because consumer engines, IAM and LF grants affect behavior.
- Evidence must preserve the core evidence model even when AWS persists it differently from other platforms.

## Subtargets

| Subtarget | Status | Purpose |
| --- | --- | --- |
| `aws_glue_iceberg` | Initial target | Glue Spark jobs writing Apache Iceberg tables in S3 with Glue Catalog metadata. |
| `aws_athena_iceberg` | Future | SQL-oriented rendering and diagnostics for Athena/Iceberg workloads. Not a general executor. |
| `aws_emr_serverless_iceberg` | Future | Advanced Spark runtime for jobs that need more runtime control than Glue. |
| `aws_native_passthrough` | Future | AWS-native ingestion services such as AppFlow, DMS or managed connectors. |

## Initial Capabilities: `aws_glue_iceberg`

The current core capability model uses conservative booleans. The first AWS adapter maps the richer AWS target into `PlatformCapabilities` as follows:

```python
PlatformCapabilities(
    platform="aws_glue_iceberg",
    supports_append=True,
    supports_overwrite=True,
    supports_merge=True,
    supports_hash_diff=True,
    supports_scd2=True,
    supports_snapshot_reconcile_soft_delete=True,
    supports_schema_evolution=True,
    supports_row_filters=True,
    supports_column_masks=True,
    supports_available_now_streaming=True,
    supports_required_columns_quality=True,
    supports_unique_key_quality=True,
    supports_max_null_ratio_quality=True,
    supports_expression_quality=True,  # Spark SQL runtime checks, with dialect warning
    supports_shape=True,
    supports_transform=True,
    evidence_stores=("iceberg_table",),
    review_required_semantics=(
        "historical",
        "snapshot_reconcile_soft_delete",
        "row_filters",
        "column_masks",
        "source.native_passthrough",
    ),
)
```

Some booleans are set to `True` so the core planner can return `REVIEW_REQUIRED` instead of `UNSUPPORTED` for semantics that AWS can plausibly implement but that require review. This is the same distinction as: "the platform has primitives, but the adapter is not allowed to claim semantic equivalence automatically." Expression quality is supported by Spark SQL runtime checks and returns `SUPPORTED_WITH_WARNINGS` because expression dialect portability must still be reviewed.

## Write Mode Mapping

| ContractForge mode | Initial status | AWS mapping | Notes |
| --- | --- | --- | --- |
| `append` | `SUPPORTED` | Glue Spark append into Iceberg table | Generated Glue script creates the Iceberg table on first run when it does not exist, then appends on later runs. |
| `overwrite` | `SUPPORTED` | Glue Spark create/replace into Iceberg table | First-pass Glue script is rendered; partition replacement rules are future detailed behavior. |
| `upsert` | `SUPPORTED` | Iceberg `MERGE INTO` from Glue Spark | First-pass Glue script is rendered with missing-key, null-key and duplicate-key guards. |
| `hash_diff_upsert` | `SUPPORTED_WITH_WARNINGS` | Hash diff staging plus Iceberg merge | Runtime script is rendered; warning remains until Glue/Iceberg performance and concurrency are validated. |
| `historical` | `REVIEW_REQUIRED` | Iceberg merge/history implementation | Requires review of late-arriving, deletes and effective dating. |
| `snapshot_reconcile_soft_delete` | `REVIEW_REQUIRED` | Full snapshot reconciliation in Iceberg | Requires source completeness proof and concurrency review. |

The renderer generates Glue Spark scripts for `append`, `overwrite`, `upsert` and `hash_diff_upsert` when preparation and quality sections can be preserved. It also renders available-now streaming jobs for supported Kafka/Event Hubs sources and supported write modes. historical and snapshot modes remain review-only until their native implementation is validated.

## Preparation Runtime Mapping

The first AWS runtime renderer supports only preparation semantics that can be expressed directly and deterministically in a Glue Spark DataFrame before quality checks and writes:

| Contract field | First runtime behavior | Notes |
| --- | --- | --- |
| `select_columns` | Rendered in Glue job | Fails before write if a selected column is missing. |
| `column_mapping` | Rendered in Glue job | Fails on missing source columns, duplicate targets, reserved control columns or target collisions. |
| `filter_expression` | Rendered in Glue job | Applied as a Spark SQL filter expression. |
| `transform.cast` | Rendered in Glue job | Uses Spark casts and fails on missing source columns. |
| `transform.standardize` | Rendered in Glue job | Uses Spark string functions for trim, lower, upper, whitespace normalization and empty-as-null. |
| `transform.derive` | Rendered in Glue job | Uses Spark SQL expressions; complex cross-platform SQL remains caller responsibility. |
| `transform.composite_keys` | Rendered in Glue job | Uses Spark `concat_ws` and null-to-empty behavior per the core contract's composite-key semantics. |
| `shape.parse_json` | Rendered in Glue job | Requires a concrete schema or resolved `schema_ref`; optional `cast_input: STRING` is supported. |
| `shape.arrays` | Rendered in Glue job | Supports `size`, `to_json`, `first`, `explode` and `explode_outer`; cardinality-changing bronze explodes require explicit allowance. |
| `shape.columns` | Rendered in Glue job | Supports column paths, aliases, casts and Spark SQL expressions. |
| `shape.flatten` | Rendered in Glue job | Uses a runtime schema-introspection helper and keeps arrays intact. |
| `transform.deduplicate` | Rendered in Glue job | Requires deterministic `keys` and `order_by`; renders a Spark window with `row_number() == 1`. |

The adapter must not render a runnable Glue job that skips `shape` or `transform`. If unsupported sections are present, the renderer emits a `.glue_job.todo.md` artifact.

## Quality Runtime Mapping

AWS planning can acknowledge broad quality capability because Spark, Glue Data Quality and Iceberg can express the checks. Runtime rendering preserves the enforcement policy when the adapter can map the rule faithfully:

| Quality rule | First runtime behavior | Notes |
| --- | --- | --- |
| `required_columns` with severity `abort` | Rendered in Glue job | Evaluated with Glue Data Quality and fails the run on failure. |
| `unique_key` with severity `abort` | Rendered in Glue job | Evaluated with Glue Data Quality and fails the run on duplicate keys. |
| `row_count_minimum` with severity `abort` | Rendered in Glue job | Evaluated with Glue Data Quality and fails the run below the threshold. |
| `not_null` with severity `quarantine` | Rendered in Glue job | Row-level Glue Data Quality outcomes are written to `ctrl_ingestion_quarantine`; failed rows are removed before write. |
| `accepted_values` with severity `quarantine` | Rendered in Glue job | Row-level Glue Data Quality outcomes are written to `ctrl_ingestion_quarantine`; failed rows are removed before write. |
| `max_null_ratio` with severity `warn` | Rendered in Glue job | Results are written to `ctrl_ingestion_quality`; the run continues. |
| `expression` | Rendered in Glue job with warning | Evaluated as Spark SQL filters; abort fails the run, warn records quality evidence, and quarantine records failed rows then filters them before write. Dialect portability remains `SUPPORTED_WITH_WARNINGS`. |

The adapter must not silently convert quarantine or warning rules into abort-only behavior. Row-level quarantine is only applied to rules where Glue Data Quality returns row outcomes that identify offending rows (`not_null` and `accepted_values` today). Quarantine-severity aggregate rules are recorded as quality evidence and do not filter rows. If unsupported quality semantics are present, the renderer emits a `.glue_job.todo.md` artifact instead of a runnable Glue job.

## Source Mapping

| Source intent | Initial AWS target behavior |
| --- | --- |
| `table`, `view`, `sql` | Glue Catalog/Athena/Iceberg source references in rendered plans. |
| file formats: `csv`, `json`, `parquet`, `orc`, `text`, `avro` | S3/Spark readers in Glue job script. |
| `s3`, `object_storage`, `blob` with provider `s3` | Glue Spark reads from S3. |
| `incremental_files` | Glue bookmarks or ContractForge evidence state, depending on source format and target rules. |
| `jdbc`, `postgres`, `mysql`, `sqlserver`, `oracle`, `redshift`, `db2` | Glue JDBC source with driver/network prerequisites. |
| `http_file`, `http_csv`, `http_json`, `http_text` | Bounded driver-side fetch or S3 landing pattern; runtime is adapter-owned. |
| `kafka_bounded`, `eventhubs_bounded` | Spark bounded Kafka/Event Hubs read in Glue; connector jars and offset semantics remain adapter-owned. |
| Databricks `autoloader` | `UNSUPPORTED`; use `incremental_files` for portability. |
| `native_passthrough` | Review/apply handoff to AppFlow, DMS, Glue native/custom connectors or partner connectors. The artifact recommends concrete AWS paths and review inputs but remains non-executable. |

## Incremental Tracking

Glue job bookmarks are an AWS adapter optimization. The core sees only source intent, watermarks and evidence requirements.

Initial policy:

- JDBC sources may map core incremental intent to Glue bookmark keys when the configured key is monotonic and supported.
- S3 source incremental behavior may use Glue bookmarks for supported formats or ContractForge evidence state.
- The adapter must record which strategy was selected in rendered review output and evidence.

Generated Glue jobs compare the target Iceberg table schema before and after the committed write. Added columns and detected type changes are appended to `ctrl_ingestion_schema_changes`, and the same summary is copied into `ctrl_ingestion_runs.schema_changes_json`.

## Governance Mapping

Lake Formation data filters can express column-level, row-level and cell-level controls. The initial adapter marks row filters and column masks as `REVIEW_REQUIRED` because behavior depends on:

- Lake Formation administrator setup;
- Data Catalog registration;
- IAM and LF grants;
- consumer engine support;
- supported expression and datatype limits.

The renderer should generate a review artifact describing required Lake Formation data filters, grants and assumptions before any apply command exists.

Annotations and operations are contract sections, not Lake Formation-only concerns. The AWS adapter maps them separately:

- `annotations.table.description` becomes a planned Glue Catalog table description update.
- `annotations.table.tags`, aliases and deprecation metadata become planned Glue table parameters.
- `annotations.columns.*.description` becomes planned Glue column comments.
- `annotations.columns.*.tags`, PII and deprecation metadata become planned Glue column parameters.
- `operations` metadata is persisted to the canonical `ctrl_ingestion_operations` evidence table.

Annotation application is intentionally not automatic yet. Glue `UpdateTable` requires preserving the current table definition and sending a full `TableInput`, so the first adapter surface emits an explicit plan and matching evidence SQL instead of applying partial metadata blindly.

## Evidence Mapping

The first production evidence target is Iceberg tables registered in AWS Glue Catalog. The AWS adapter must render these tables from `contractforge_core.evidence`; it must not fork or redefine the control-table schema.

| Evidence concept | AWS persistence target |
| --- | --- |
| run | Iceberg table in evidence database |
| error | Iceberg table in evidence database |
| quality result | Iceberg table in evidence database |
| quarantined row reference | Iceberg table or S3 object reference |
| schema change | Iceberg table in evidence database; generated Glue jobs append added-column and type-change rows after committed writes |
| lineage event | Iceberg table plus optional OpenLineage export |
| source metadata | run/evidence JSON fields |
| governance application | Iceberg audit table |
| cost signal | Glue job run metrics and estimated DPU cost |

S3 JSON artifacts may be generated for review and archival, but they are not the default evidence store. Generated Glue jobs create missing state and evidence tables before writing them. Success paths call Glue `job.commit()` before appending final success evidence, then update `ctrl_ingestion_state` and append to `ctrl_ingestion_runs`, `ctrl_ingestion_metadata` and `ctrl_ingestion_lineage`; available-now streaming jobs also append per-batch rows to `ctrl_ingestion_streams`. Run evidence includes contract description, owner, domain, tags, SLA, runtime parameters, ownership, operations metadata, Glue job/run identity and idempotency/run-group identifiers when declared. Batch jobs capture `rows_read` before quality/quarantine filters mutate the dataframe, so quarantined rows do not disappear from read metrics. Failure paths append redacted error evidence to `ctrl_ingestion_errors`, append a `FAILED` row to `ctrl_ingestion_runs` with `write_committed = false`, and re-raise so the native Glue run still fails. Error evidence writes are best-effort: if control-table persistence fails, the generated job logs the secondary failure and preserves the original exception.

## Environment Binding

The AWS adapter can consume the core `environment` contract.

- `environment.adapter` must be `aws`.
- `environment.evidence.database` controls the Glue Catalog database used for evidence, state, cost, metadata, lineage and governance evidence artifacts.
- `environment.evidence.schema` is accepted as a compatibility alias for the same AWS evidence database concept because the generic environment contract is cross-platform.
- `environment.artifacts.uri` controls the S3 prefix used for rendered scripts, manifests, original split contracts and normalized contract snapshots.
- `environment.parameters.aws` is exposed to the adapter as AWS-owned native defaults. These parameters must not change ingestion semantics.

The environment contract does not alter source, target table, write mode, annotations, operations or access semantics.

Generated Glue job scripts, CloudFormation scaffolds, Terraform scaffolds, IAM policy review artifacts, evidence DDL, state DDL, cost SQL and deployment manifests must use the same resolved evidence database. A plan rendered with `environment.evidence.database: cf_ops_prod` must not write runtime evidence to the fallback `<target>_ops` database.

Deployment defaults may be declared under `environment.parameters.aws.glue_job`, `environment.parameters.aws.job_bookmarks` and `environment.parameters.aws.dependencies`. These defaults feed deployment artifacts such as Glue job definitions, CloudFormation and Terraform, while `extensions.aws.*` on the contract remains the per-contract override. Adapter-owned Glue arguments such as `--datalake-formats`, `--enable-glue-datacatalog`, `--job-bookmark-option` and generated dependency arguments remain reserved.

Public evidence helper functions accept the same environment contract. When both `database=` and `environment=` are passed, the explicit `database` argument wins because it is an intentional caller override at the helper boundary.

AWS CLI planning and rendering must honor the same boundary. `contractforge-aws plan`, `contractforge-aws render`, `contractforge-aws publish-s3` and `contractforge-aws deploy` load an adjacent split-bundle `.environment.yaml` automatically when the contract path is a split section. The explicit `--environment` argument overrides that bundle environment. Runtime-only apply commands may continue to receive concrete runtime arguments such as catalog id, Athena output location or Lake Formation account id because those commands operate after rendering, not during semantic planning.

The renderer emits:

- `<target>.evidence.sql`: non-executing table mapping notes;
- `<target>.evidence_ddl.sql`: Iceberg DDL for canonical evidence tables such as `ctrl_ingestion_runs`, `ctrl_ingestion_quality`, `ctrl_ingestion_errors` and governance/cost/lineage tables;
- `<target>.state_ddl.sql`: Iceberg DDL for canonical state tables such as `ctrl_ingestion_state` and `ctrl_ingestion_locks`.

Core control-table column names such as `delta_version_before`, `delta_version_after` and `last_delta_version` are preserved for parity. AWS fills their neutral replacements with Iceberg snapshot identifiers where applicable, or leaves legacy fields null with the platform version marker in `operation_metrics_json`.

## Initial Artifact Types

The renderer emits:

- `<target>.review.md`: planning status, warnings, blockers and expected AWS mapping;
- `<target>.deployment_manifest.json`: deterministic manifest over the generated AWS artifacts, including artifact categories, apply order, review boundaries and optional runtime helper names;
- `<target>.capabilities.json`: the adapter capability declaration used for planning, including AWS source-support metadata;
- `<target>.evidence.sql`: evidence table mapping notes;
- `<target>.evidence_ddl.sql`: Iceberg DDL for canonical evidence/control tables;
- `<target>.state_ddl.sql`: Iceberg DDL for state/lock tables;
- `<target>.cost.sql`: query-only operational cost report over `ctrl_ingestion_runs` and `ctrl_ingestion_cost`;
- `<target>.iam_policy.json`: review IAM policy template for the generated Glue job role, including Glue Catalog, CloudWatch Logs, S3, Secrets Manager and RDS IAM permissions when required;
- `<target>.write_mode_review.md`: specific review checklist for review-required write modes such as `historical` and `snapshot_reconcile_soft_delete`;
- `<target>.annotations.json`: Glue Catalog annotation update plan for table descriptions, table parameters, column comments and column parameters, when `annotations` is declared;
- `<target>.annotations_evidence.sql`: canonical `ctrl_ingestion_annotations` evidence inserts for the annotation plan;
- `<target>.operations.json`: normalized operations metadata, when `operations` is declared;
- `<target>.operations.sql`: canonical `ctrl_ingestion_operations` evidence insert for operations metadata;
- `<target>.native_passthrough.json`: AWS-native service handoff plan for `source.type: native_passthrough`, when declared;
- `<target>.lakeformation_evidence.sql`: governance evidence inserts for Lake Formation grants and review-required data-filter scaffolds, when `access` is declared;
- `<target>.performance_profile.json`: benchmark checklist for runtime-sensitive mappings such as `hash_diff_upsert`;
- `runtime/contractforge_aws_runner.py`: stable Glue runner used by default deployments;
- `<target>.glue_job.py`: generated Glue Spark/Iceberg script for `append`, `overwrite`, `upsert`, `hash_diff_upsert` and supported available-now streaming jobs;
- `<target>.glue_job_definition.json`: deterministic AWS Glue create/update payload for the generated script, including Iceberg arguments, bookmark enablement and dependency hints;
- `<target>.cloudformation.json`: parameterized CloudFormation scaffold for the Glue job and Glue databases;
- `<target>.terraform.tf`: parameterized Terraform scaffold for the Glue job and Glue databases;
- `<target>.glue_job.todo.md`: explanation for modes that are planned but not yet renderable.

Runtime execution is adapter-owned and optional. AWS API submission helpers are
available behind `contractforge-aws[runtime]`; the default Glue job points to
the stable library runner and passes the published contract URI. Generated
Glue scripts remain review and syntax-validation artifacts only. AWS Glue
deployment always points to `runtime/contractforge_aws_runner.py`; the
`generated_script` runtime mode is intentionally unsupported. Generated scripts
themselves remain plain Glue/Spark code and contain no boto3 calls.

## Optional Runtime Helpers

The base adapter package remains importable without AWS SDK dependencies. Runtime helpers that call AWS APIs live under `contractforge_aws.runtime` and require either:

- a caller-provided AWS client object; or
- `contractforge-aws[runtime]`, which installs `boto3` and `botocore`.

The first runtime helpers publish rendered artifacts to S3, register/update Glue job definitions, start Glue job runs, inspect status, map Glue `JobRun` metadata into core evidence records and render explicit Iceberg evidence `INSERT` statements:

```python
from contractforge_aws import render_aws_deployment_manifest

manifest_json = render_aws_deployment_manifest(contract)
```

```python
from contractforge_aws import render_aws_glue_job_definition

payload_json = render_aws_glue_job_definition(contract)
```

```python
from contractforge_aws import render_aws_glue_job_cloudformation

template_json = render_aws_glue_job_cloudformation(contract)
```

```python
from contractforge_aws import render_aws_glue_job_terraform

terraform_hcl = render_aws_glue_job_terraform(contract)
```

```python
from contractforge_aws import publish_aws_contract_artifacts_to_s3

publish_aws_contract_artifacts_to_s3(contract, bucket="contractforge-artifacts", prefix="dev/orders")
```

If `environment.artifacts.uri` is declared, callers may omit `bucket` and
`prefix`; the adapter resolves them from the environment.

```python
from contractforge_aws import deploy_aws_contract_to_glue

deployment = deploy_aws_contract_to_glue(contract, environment=environment_contract)
```

`deploy_aws_contract_to_glue` is the composed AWS path: render, publish to S3,
materialize the Glue job definition with final artifact URIs, then create or
update the Glue job. It is adapter-owned deployment, not core execution.

```python
from contractforge_aws import register_aws_glue_job

register_aws_glue_job(
    job_name="cf-orders",
    role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
    script_s3_uri="s3://contractforge-artifacts/dev/orders/glue_bronze_orders.glue_job.py",
    enable_job_bookmark=True,
)
```

```python
from contractforge_aws import register_aws_glue_job_definition_payload

registered = register_aws_glue_job_definition_payload(job_payload, glue_client=my_glue_client)
```

```python
from contractforge_aws import apply_aws_lake_formation_contract

result = apply_aws_lake_formation_contract(contract, lakeformation_client=my_lf_client)
```

```python
from contractforge_aws import apply_aws_annotations_contract

result = apply_aws_annotations_contract(contract, glue_client=my_glue_client)
```

```python
from contractforge_aws import record_aws_operations_contract

result = record_aws_operations_contract(runner=my_sql_runner, contract=contract, run_id="run-123")
```

```python
from contractforge_aws import ensure_aws_evidence_tables

result = ensure_aws_evidence_tables(
    runner=my_sql_runner,
    database="contractforge_ops",
    dialect="athena",
    warehouse_uri="s3://contractforge-lakehouse/evidence/",
)
```

```python
from contractforge_aws import AthenaSqlRunner

runner = AthenaSqlRunner(database="contractforge_ops", output_location="s3://query-results/")
```

```python
from contractforge_aws import get_aws_glue_job_run_status, start_aws_glue_job_run

run = start_aws_glue_job_run(job_name="cf-orders", arguments={"--contractforge-run-id": "run-123"})
status = get_aws_glue_job_run_status(job_name="cf-orders", run_id=run.run_id)
```

```python
from contractforge_aws import wait_aws_glue_job_run

status = wait_aws_glue_job_run(job_name="cf-orders", run_id=run.run_id)
```

```python
from contractforge_aws import reconcile_aws_glue_job_run_evidence

evidence = reconcile_aws_glue_job_run_evidence(
    job_name="cf-orders",
    run_id=run.run_id,
    target_table="glue.bronze.orders",
    mode="append",
)
```

```python
from contractforge_aws import render_aws_glue_job_run_evidence_sql

sql = render_aws_glue_job_run_evidence_sql(
    job_name="cf-orders",
    run_id=run.run_id,
    target_table="glue.bronze.orders",
    mode="append",
    database="contractforge_ops",
)
```

This is deliberately not full ContractForge orchestration yet. It stages review
artifacts, DDL, generated Glue scripts, runtime contract snapshots and the
stable library runner; registers the job definition with an explicit IAM role
and script URI; can trigger/check a Glue run; and can convert Glue `JobRun`
fields such as `StartedOn`, `CompletedOn`, `JobRunState`, `ExecutionTime` and
`DPUSeconds` into core evidence record objects. Glue jobs persist their own run
and quality evidence to Iceberg control tables for supported runtime paths; the
post-run reconciliation helpers remain explicit review/apply helpers for
supplemental run and cost evidence.

Glue job registration can be driven by explicit parameters or by the rendered `.glue_job_definition.json` payload. The payload helper removes review-only fields such as `contractforge_review_notes` before calling Glue and validates the required `Name`, `Role` and S3 script location.

Glue run waiting is a thin `GetJobRun` polling helper. It returns the final `GlueJobRunStatus` for `SUCCEEDED` runs and raises for failed terminal states such as `FAILED`, `STOPPED`, `TIMEOUT` or `ERROR`. It does not retry, restart or reconcile evidence automatically.

Lake Formation runtime helpers preserve the review boundary. Table grants can be applied from the rendered plan. Data cell filters are skipped by default and require `allow_data_cells_filters=True` plus a concrete AWS `account_id`, because row-filter and column-mask semantics still require review before being trusted.

Glue Catalog annotation helpers preserve the current table definition before calling `UpdateTable`. They read `GetTable`, apply only planned table descriptions, table parameters, column comments and column parameters, and submit a full `TableInput` so storage descriptors, partition keys and existing parameters are retained.

Operations helpers use a caller-owned SQL runner to insert the normalized operations metadata into the canonical `ctrl_ingestion_operations` evidence table. The helper reports `RECORDED`, `FAILED` or `NOT_CONFIGURED` and does not own scheduling or query-engine lifecycle.

Evidence setup helpers use a caller-owned SQL runner to apply the same Iceberg DDL rendered from the core evidence schema. They can create evidence tables and state tables outside a generated Glue job while preserving the adapter boundary. Because the DDL is ordered, evidence setup requires a waiting SQL runner; asynchronous submission is reserved for single-statement helpers such as operations recording.

When the runner is Athena, evidence setup uses Athena-native Iceberg DDL and
requires an explicit S3 `warehouse_uri` for table locations. Generated Glue jobs
continue to use Spark Iceberg DDL with `glue_catalog` because that catalog is a
Spark runtime catalog, not an Athena catalog name.

Athena evidence setup uses Athena's non-CTAS Iceberg form:
`CREATE TABLE ... [PARTITIONED BY (...)] LOCATION ... TBLPROPERTIES
('table_type'='ICEBERG', 'format'='parquet')`. It intentionally drops
Spark-only column constraints such as `NOT NULL` from the setup DDL while
preserving the canonical evidence column names and types. Runtime evidence
records still follow `contractforge_core.evidence`; the adapter only changes
the table-creation dialect.

`AthenaSqlRunner` is an optional convenience runner for these SQL helper surfaces. It calls Athena only when explicitly instantiated and used, supports caller-provided clients for testability/session ownership, and can either wait for terminal query state or submit without waiting.

Native passthrough artifacts preserve the same boundary. They classify likely AWS service paths:

- Amazon AppFlow for managed SaaS extraction when the application/object and trigger model are supported;
- AWS DMS for database full-load or CDC replication when portable JDBC is insufficient;
- AWS Glue native, custom or partner connectors for proprietary APIs or connector-owned extraction.

The rendered artifact includes `recommended_aws_paths`, `review_only_apply_candidates`, `review_required_inputs`, `contract_mapping`, `evidence_strategy` and `unsupported_claims`. `review_only_apply_candidates` uses AWS API-shaped skeletons for `appflow:CreateFlow`, `dms:CreateReplicationConfig` and `glue:CreateConnection` so reviewers can see the intended native boundary, but it does not call AppFlow, DMS or Glue connector APIs.

## Known Limitations

- No AWS SDK calls in the base adapter package.
- Lake Formation data cell filters require explicit reviewed opt-in before application.
- Terraform and CloudFormation are emitted as review scaffolds, not automatically applied.
- No full orchestrator-owned post-run control-table reconciliation in the first runtime helpers; generated Glue jobs persist supported run, quality, schema, state, metadata, stream and lineage evidence in-job.
- No EMR Serverless execution in the first runtime helpers.
- No native AppFlow/DMS execution in the first adapter phase.
- Native passthrough is rendered as review/apply handoff only; it does not call AppFlow, DMS or Glue connector APIs automatically.
- historical and snapshot soft delete are review-required until real Glue/Iceberg tests prove semantics and performance.

## Future Core Evolution

AWS will likely need a richer capability model over time:

- subtarget metadata;
- per-feature status instead of booleans;
- performance profiles;
- consumer-engine compatibility for governance;
- selected incremental tracking strategy.

Do not add those abstractions until the AWS adapter proves the need through tests and docs.
