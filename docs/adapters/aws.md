# AWS Adapter

The AWS adapter is the second ContractForge adapter family. Its first target is `aws_glue_iceberg`: AWS Glue Spark jobs writing Apache Iceberg tables in Amazon S3, cataloged in AWS Glue Data Catalog and governed by AWS Lake Formation.

The adapter is not a generic AWS abstraction. It is a set of explicit AWS subtargets, each with its own capabilities and review boundaries.

Current status: stable supported surface for the documented
`aws_glue_iceberg` target. Supabase JDBC, USGS REST, S3 file medallion,
dedicated incremental files, controlled failure paths and the validated
available-now streaming path have completed real AWS runtime validation through
ContractForge commands and the stable library runner. Reference hash-diff and
Lake Formation consumer-engine validation are now part of release evidence.
historical and snapshot soft delete are explicitly excluded from stable-final, while
non-MSK streaming-provider compatibility claims and contract-specific
governance expressions remain explicit review or validation areas.

The release gate for calling this adapter stable is tracked in
[AWS stable-surface criteria](../specs/aws-ga-criteria.md), with the detailed
evidence matrix in
[AWS stabilization matrix](../specs/aws-stabilization-matrix.md). Runtime
behavior should be described as supported only when it has passed those gates,
not just because the renderer can produce an artifact.

Every render includes a `*.deployment_manifest.json` artifact. The manifest
records per-artifact `bytes` and `lines`, an `artifact_summary`, and an
`artifact_size_budget` that marks generated Glue scripts `WARN` above 256 KiB,
so reviews can track generated Glue job growth before publishing to S3.

The default deployed Glue job uses the ContractForge AWS library runner. The
job script is the stable `runtime/contractforge_aws_runner.py` artifact; the
contract and environment are published as runtime JSON artifacts and passed as
Glue arguments. The runner loads those runtime artifacts inside Glue, renders
the reviewed Glue/Spark body with the same adapter renderer, and executes it in
the Glue process. The generated `<target>.glue_job.py` remains part of every
render for review and syntax validation only; AWS Glue deployment always points
to the stable library runner.

Contracts with runtime-sensitive write modes, currently `hash_diff_upsert`, also
render `*.performance_profile.json` and `*.performance.sql` artifacts. The
profile is the required measurement plan; the SQL is an Athena-compatible report
over `ctrl_ingestion_runs` and `ctrl_ingestion_cost` for the benchmark runs.
Neither is a benchmark result by itself. They define the evidence needed to
promote the AWS mapping from `SUPPORTED_WITH_WARNINGS` to a stronger production
claim.

The generated `*.iam_policy.json` is a review template, not an auto-applied
policy. It derives Glue Catalog, CloudWatch Logs, source S3, Iceberg warehouse,
artifact S3, Glue script and dependency file permissions from the contract and
environment. Dependency files and explicit script paths are rendered as exact
S3 object ARNs; source, artifact and warehouse locations remain prefix-scoped
where the runtime must read or write multiple objects.

Runtime evidence captured on 2026-06-02:

| Project | Result | Evidence |
| --- | --- | --- |
| Supabase JDBC medallion | `PASS` | Contract-only AWS project completed through adapter CLI and the stable `runtime/contractforge_aws_runner.py` with five successful Glue jobs. Latest run wrote cost evidence for all five targets, retained bronze quarantine behavior, and audit shows no error rows. |
| USGS REST medallion | `PASS` | REST/GeoJSON medallion completed through `deploy-project --run --wait --record-cost-evidence --audit-evidence` using the stable runner. Latest audit shows all historical runs successful, all quality status `PASSED`, no quarantine rows, no error rows, and joined DPU-second cost rows for all four targets. |
| S3 file medallion | `PASS` | Three Glue jobs ran through the stable runner, target rows remained bronze=7, silver=7, gold=3, and audit records success, quality, quarantine and cost evidence. |
| Incremental files | `PASS` | Incremental-file project ran through the stable runner and recorded a successful existing-bookmark run with cost/audit evidence; historical runs preserve wave 1, wave 2 and no-new-input `SKIPPED` evidence. |
| Failure paths | `PASS` | `ensure-evidence-tables` created Athena Iceberg evidence/state tables, then two expected Glue failures ran through the stable runner with `EXPECTED_FAILURE`, failed-run rows, error evidence, abort-quality evidence and DPU-second cost evidence for both targets. |
| Available-now streaming | `PASS` | Azure Event Hubs and AWS MSK Kafka available-now jobs ran through the stable runner with checkpointed Glue streaming, success status, cost evidence and Athena audit over run, quality, quarantine, error and cost tables. |

## Initial Target

| Area | Decision |
| --- | --- |
| Subtarget | `aws_glue_iceberg` |
| Runtime | AWS Glue Spark |
| Table format | Apache Iceberg |
| Storage | Amazon S3 |
| Catalog | AWS Glue Data Catalog |
| Governance | AWS Lake Formation |
| Evidence | Iceberg evidence tables |

## Why Glue + Iceberg First

This path gives ContractForge a managed Spark runtime, an open table format with ACID semantics, a catalog API, and a governance layer that can express row and column controls.

It also keeps the AWS adapter aligned with the core thesis:

```text
same contract intent
same planning model
different native runtime artifacts
same evidence concepts
```

## Supported Surface

The adapter feeds the public core API without AWS SDK dependencies in the base package. It renders Glue Spark/Iceberg scripts, review artifacts and deployment scaffolds for the supported surface below.

| Feature | Planning result | Runtime rendering |
| --- | --- | --- |
| `append` | `SUPPORTED` | Glue Spark script with Iceberg append |
| `overwrite` | `SUPPORTED` | Glue Spark script with Iceberg create/replace |
| `upsert` | `SUPPORTED` | Glue Spark script with Iceberg `MERGE INTO` and key guards |
| `hash_diff_upsert` | `SUPPORTED_WITH_WARNINGS` when `merge_keys` plus `hash_keys` or `hash_strategy: all_columns_except` are declared; `UNSUPPORTED` without `merge_keys` | Glue Spark script with row hash calculation and Iceberg `MERGE INTO`; `merge_keys` define row identity and hash strategy defines compared content; performance/concurrency still needs AWS validation |
| `historical` | `REVIEW_REQUIRED` | Review artifact only |
| `snapshot_reconcile_soft_delete` | `REVIEW_REQUIRED` | Review artifact only |
| row filters | `REVIEW_REQUIRED` | Lake Formation review only |
| column masks | `REVIEW_REQUIRED` | Lake Formation review only |
| available-now streaming | `SUPPORTED` for validated AWS MSK and Azure Event Hubs Kafka paths; `SUPPORTED_WITH_WARNINGS` for other compatibility providers | Glue structured-streaming job with `readStream`, `trigger(availableNow=True)` and `foreachBatch` for append/merge modes when `checkpoint_location` is declared |
| `incremental_files` | `SUPPORTED_WITH_WARNINGS` | Glue DynamicFrame read with job bookmarks for eligible S3 formats; no-new-input bookmark runs record `SKIPPED` evidence without executing column-dependent preparation/write logic |
| JDBC incremental | `SUPPORTED_WITH_WARNINGS` | Glue DynamicFrame read with `jobBookmarkKeys` when a simple watermark column maps to a Glue JDBC connection type |
| Databricks `autoloader` | `UNSUPPORTED`; use `incremental_files` | None |
| `native_passthrough` | `REVIEW_REQUIRED` | Review handoff artifact with AWS path recommendations such as AppFlow, DMS, Glue native/custom connectors or partner connectors |

Runtime quality rendering preserves the ContractForge enforcement policy for mapped Glue Data Quality rules. Abortive `required_columns`, `unique_key` and `row_count_minimum` checks fail the run. Warning rules such as `max_null_ratio` write `ctrl_ingestion_quality` evidence and continue. Row-level quarantine is implemented for `not_null` and `accepted_values`: failed rows are written to `ctrl_ingestion_quarantine`, removed from the dataframe before the target write, and counted in run evidence. Expression rules are evaluated as Spark SQL runtime checks with `SUPPORTED_WITH_WARNINGS`: abort fails the run, warn records evidence, and quarantine writes failed rows to `ctrl_ingestion_quarantine` before filtering them out. The warning remains because expression dialect portability must be reviewed.

For `hash_diff_upsert`, do not use `hash_keys` as business keys. The AWS adapter
requires `merge_keys` for row identity. Use `hash_keys` for explicit content
columns on governed tables, or `hash_strategy: all_columns_except` plus
`hash_exclude_columns` for wide tables. The renderer automatically excludes
ContractForge/framework-generated columns such as `row_hash`,
`source_loaded_at_utc`, SCD control columns and outputs from `transform.derive`
or `transform.composite_keys`. It also prefilters unchanged rows before Iceberg
`MERGE` and records no-change writes as `SKIPPED` with
`skip_reason=no_hash_changes`. Iceberg snapshot summaries report physical
file rewrite counters such as `added-records` and `deleted-records`; for
hash-diff observability, ContractForge also writes
`hash_diff_candidate_rows` and `hash_input_columns` into
`operation_metrics_json`. Dashboards should use `hash_diff_candidate_rows` for
business change volume and Iceberg counters for storage/write amplification.

Runtime preparation rendering preserves portable `shape.parse_json`, `shape.arrays`, `shape.columns`, `shape.flatten`, `transform.cast`, `transform.standardize`, `transform.derive`, `transform.composite_keys` and deterministic `transform.deduplicate`. The adapter still blocks unsupported shape/transform semantics, such as `shape.zip_arrays` and bronze-layer array explosion without an explicit cardinality allowance, so it does not silently skip parsing, array explosion or deduplication semantics.

The dedicated incremental-files fixture lives at
`examples/real-world/aws-incremental-files`. It uses only contracts and an AWS
environment file to validate `incremental_files` planning, Glue bookmark
configuration, Iceberg rendering and generated Python compilation before the
upload-wave runtime test is executed in AWS. The real AWS test covers wave 1,
wave 2 and a no-new-input rerun; the last run must preserve the target row
count and write `SKIPPED` evidence with `skip_reason = no_new_input`.

Available-now streaming jobs record per-micro-batch rows in
`ctrl_ingestion_streams` and copy aggregate stream totals into final
`ctrl_ingestion_runs.operation_metrics_json` as `stream_batches`,
`stream_rows_read`, `stream_rows_written` and `stream_rows_quarantined`. Final
run, state and lineage rows-written evidence prefer the ContractForge stream
total because the latest Iceberg snapshot may only represent the last
micro-batch. The AWS MSK and Azure Event Hubs Kafka paths have been validated in
AWS Glue with checkpoint progression, no-input reruns, quarantine or target
writes and cost evidence. MSK is the AWS-native Kafka maturity provider. Other
Kafka/Event Hubs compatibility providers still return a provider-review warning
until their connector/runtime semantics are tested.

## Project Deployment

AWS follows the standardized adapter command vocabulary in
[Adapter CLI](../cli.md). For real ingestion repositories, use project-level
commands: `deploy-project` loads `project.yaml`, resolves `environments.aws`
and deploys contracts in `execution_order`; `run-project` starts the same
project graph. Dry runs perform project loading, contract planning, artifact
rendering and Python syntax compilation for generated Glue scripts without AWS
API calls.

`--summary-only` keeps deployment, run, wait, cost status, artifact counts and
bytes, but omits verbose per-artifact S3 lists.

When AWS Glue temporarily rejects a project step with
`ConcurrentRunsExceededException`, `deploy-project` retries start within the
same `--max-wait-seconds` budget using `--poll-interval-seconds`. This keeps the
operator path deterministic under account-level or job-level concurrency
limits without requiring manual Glue Studio intervention.

### Native project orchestration

AWS project orchestration is adapter-owned and Step Functions based. The
contract YAMLs are planned and rendered before deployment, then published with
the stable AWS library runner. Glue runs that stable runner by default and
receives the contract URI as an argument. When native orchestration is
requested, the adapter maps
`project.yaml.execution_order` into a Step Functions state machine that starts
the registered Glue jobs with the Glue `.sync` integration. Steps in the same
dependency wave are emitted as a `Parallel` state.

If `project.yaml.schedule` is declared, the orchestration payload
also includes an EventBridge Scheduler target for the state machine. Real
deployment requires AWS-owned roles:

- `parameters.aws.step_functions.role_arn` for the state machine;
- `parameters.aws.scheduler.role_arn` for EventBridge Scheduler when schedules
  are deployed.

This is the AWS equivalent of the Databricks DAB project path, but in native AWS
terms: Databricks creates one multi-task Job; AWS creates per-contract Glue jobs
plus a Step Functions state machine that orchestrates them.

Use standard cron syntax in the project file and an IANA timezone name. The AWS
adapter renders the EventBridge Scheduler expression internally:

```yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false
  adapters:
    aws:
      state: DISABLED
```

The example above becomes `cron(0 6 * * ? *)` for AWS. Only AWS-native
overrides such as `state`, `flexible_time_window`, or `expression` belong under
`schedule.adapters.aws`.

Direct Glue execution flags (`--run` / `--wait`) are intentionally mutually
exclusive with Step Functions execution flags (`--run-orchestration` /
`--wait-orchestration`) to avoid running the same contracts twice.

Failure-path projects can declare `expected_result: failed` on a step and run
with `--accept-expected-failures`. This is intended for observability tests
that prove `ctrl_ingestion_errors` and failed `ctrl_ingestion_runs` without
manually editing generated Glue code.

The AWS-specific `audit-evidence` command runs the standard control-table checks from the stabilization
matrix: runs by status, runs by quality status, quality rows by target,
quarantine rows by target, error rows by target and reconciled Glue DPU-second
cost rows by target. Cost rollups join `ctrl_ingestion_cost` to
`ctrl_ingestion_runs` on `run_id` and `target_table`, so orphan platform cost
records are not counted.

Glue `JobRun` cost signals are reconciled after a terminal run because
`DPUSeconds` is available from the AWS API, not inside the generated Glue job.
Use `--record-cost-evidence` with waited project runs to append
`ctrl_ingestion_cost` rows without duplicating `ctrl_ingestion_runs`. The
adapter records cost under the canonical ContractForge run id
(`job_name:glue_run_id`) and keeps the raw Glue run id in the payload.

For a Glue run that already completed, record cost evidence without rerunning
the ingestion job with the AWS-specific `record-glue-cost` helper.

The command uses the same idempotent cost writer as `deploy-project
--record-cost-evidence`. If the contract is not adjacent to its
`.environment.yaml`, pass `--environment` explicitly so the command writes to
the intended evidence database.

For runtime-sensitive contracts such as `hash_diff_upsert`, use the canonical
`performance-report` command to render the benchmark SQL locally or execute it
through Athena after benchmark runs.

`cleanup-project` does not delete anything. It reads the same project and
environment contracts, renders the expected Glue job names, artifact S3 prefix,
warehouse S3 prefix, evidence database and any declared external cleanup
resources. The Event Hubs streaming example declares the Azure resource group
used by the Kafka-compatible Event Hubs namespace, so the cleanup output includes
the reviewed `az group delete` command without executing it.

Release readiness is reported through the canonical `stabilization-report`
command.

The report separates two claims. `supported_surface_ready: true` and
`classification: STABLE_SUPPORTED_SURFACE` mean the documented AWS Glue/Iceberg
surface has passed the real-project gates. `stable_final: true` means all
production-certification concerns inside that documented claim are certified or
explicitly excluded. Broader claims such as non-MSK Kafka compatibility,
contract-specific hash-diff SLAs, arbitrary Lake Formation expressions, historical
and snapshot soft delete remain outside stable-final unless separate evidence is
attached.
The machine-readable evidence manifest is published at
`docs/reports/aws-stable-surface-evidence.json`.
Use `--strict-final` in CI to enforce the documented stable-final claim.

## Package Boundary

The package is published independently:

```text
contractforge-core
contractforge-aws
```

Dependency direction:

```text
contractforge-aws -> contractforge-core
contractforge-core -> no AWS dependency
```

The base package must not import `boto3`, Lake Formation clients or AWS SDKs. AWS API execution helpers belong behind the optional `runtime` extra:

```text
contractforge-aws[runtime]
```

Rendered Glue scripts may import Glue runtime modules because those imports live inside generated artifacts, not inside the adapter package import path.

## Public Entry Points

Core planning/rendering and optional AWS runtime helpers:

```python
from contractforge_aws import (
    AthenaSqlRunner,
    AWSAdapter,
    deploy_aws_contract_to_glue,
    plan_aws_contract,
    publish_aws_contract_artifacts_to_s3,
    register_aws_glue_job,
    register_aws_glue_job_definition_payload,
    apply_aws_lake_formation_contract,
    apply_aws_annotations_contract,
    ensure_aws_evidence_tables,
    record_aws_operations_contract,
    render_aws_contract,
    render_aws_deployment_manifest,
    render_aws_glue_job_cloudformation,
    render_aws_glue_job_definition,
    render_aws_glue_job_iam_policy,
    render_aws_glue_job_terraform,
    start_aws_glue_job_run,
    wait_aws_glue_job_run,
)
from contractforge_aws.capabilities import glue_iceberg_capabilities

result = plan_aws_contract(contract, subtarget="aws_glue_iceberg")
artifacts = render_aws_contract(contract)
manifest = render_aws_deployment_manifest(contract)
job_payload = render_aws_glue_job_definition(contract)
cloudformation = render_aws_glue_job_cloudformation(contract)
terraform = render_aws_glue_job_terraform(contract)
sql_runner = AthenaSqlRunner(database="contractforge_ops", output_location="s3://query-results/")

published = publish_aws_contract_artifacts_to_s3(contract, bucket="contractforge-artifacts", prefix="dev/orders")
deployment = deploy_aws_contract_to_glue(contract, environment=environment_contract)
registered = register_aws_glue_job(
    job_name="cf-orders",
    role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
    script_s3_uri="s3://contractforge-artifacts/dev/orders/glue_bronze_orders.glue_job.py",
    enable_job_bookmark=True,
)
registered_from_payload = register_aws_glue_job_definition_payload(job_payload, glue_client=my_glue_client)
run = start_aws_glue_job_run(job_name="cf-orders", arguments={"--contractforge-run-id": "run-123"})
status = wait_aws_glue_job_run(job_name="cf-orders", run_id=run.run_id)
lf_result = apply_aws_lake_formation_contract(contract, lakeformation_client=my_lf_client)
annotation_result = apply_aws_annotations_contract(contract, glue_client=my_glue_client)
setup_result = ensure_aws_evidence_tables(runner=my_sql_runner, database="contractforge_ops")
operations_result = record_aws_operations_contract(runner=my_sql_runner, contract=contract, run_id="run-123")
```

The CLI accepts the same environment contract used by the Python API. When the input path is a split bundle such as `orders.ingestion.yaml`, the adjacent `orders.environment.yaml` is loaded automatically. An explicit `--environment path/to/prod.environment.yaml` overrides the bundle environment for `plan`, `render` and `publish-s3`.

```bash
contractforge-aws plan contracts/orders.ingestion.yaml
contractforge-aws render contracts/orders.ingestion.yaml --environment environments/prod.aws.yaml
contractforge-aws publish-s3 contracts/orders.ingestion.yaml --environment environments/prod.aws.yaml
contractforge-aws deploy contracts/orders.ingestion.yaml --environment environments/prod.aws.yaml
```

The resolved `environment.evidence.database` is used consistently by generated Glue jobs, evidence/state DDL, operational-cost SQL, IAM policy review resources, CloudFormation, Terraform and the deployment manifest. The environment file selects evidence/control-table location; ingestion semantics still come only from the ingestion, annotations, operations and access contracts.

`environment.parameters.aws.glue_job`, `environment.parameters.aws.job_bookmarks` and `environment.parameters.aws.dependencies` can provide environment-level deployment defaults. Contract-level `extensions.aws.*` override those defaults for a specific ingestion.

The adapter already defaults Glue version `4.0`, worker type `G.1X`, two
workers, 60 minute timeout, zero retries, library-runner mode and bookmark
enablement from source semantics. Declare those fields only when the project
needs to override the defaults.

`environment.artifacts.uri` can provide the S3 destination for generated Glue
scripts, manifests, runtime contract files and optional original/normalized
contract snapshots:

```yaml
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/prod/orders/
  include_contract_bundle: true
  include_normalized_contract: true
parameters:
  aws:
    iceberg:
      warehouse: s3://contractforge-warehouse/prod/
    dependencies:
      extra_py_files:
        - s3://contractforge-artifacts/libs/contractforge_aws.whl
    glue_job:
      role_arn: arn:aws:iam::123456789012:role/ContractForgeGlueRole
```

When `artifacts.uri` is declared, `publish-s3` and `deploy` do not need a
separate bucket/prefix argument. The adapter parses the destination, publishes
the rendered artifacts and materializes the Glue job definition with the final
published `ScriptLocation`.

`deploy` is the operational shortcut for the AWS path:

```text
load bundle
  -> plan/render
  -> publish artifacts to S3
  -> materialize Glue job definition
  -> create or update Glue job
```

The platform still executes native Glue jobs. The core never imports AWS SDKs;
runtime contract loading is owned by `contractforge-aws` inside Glue.

Public evidence helpers also accept `environment=`. If a helper receives both `database=` and `environment=`, the explicit `database` wins.

Rendering produces review artifacts, a stable AWS library runner and Glue Spark job bodies for `append`, `overwrite`, `upsert` and `hash_diff_upsert` when the contract does not contain semantics that would require unsupported runtime behavior. Available-now Kafka/Event Hubs sources render as structured-streaming Glue jobs for append and merge-compatible write modes when checkpoint semantics are explicit. Glue job definitions include the adapter-owned Iceberg Spark extension `--conf`; callers may add reviewed Spark configuration through `extensions.aws.glue_job.spark_conf`, but cannot override adapter-owned Iceberg settings.

Renderable contracts also receive:

- `.deployment_manifest.json`: deterministic manifest listing generated artifacts, apply order, review boundaries, optional runtime helpers and generated artifact sizes;
- `runtime/contractforge_aws_runner.py`: stable Glue runner used by default deployments;
- `.glue_job_definition.json`: deterministic Glue create/update payload;
- `.cloudformation.json`: parameterized CloudFormation scaffold for Glue databases and job;
- `.terraform.tf`: parameterized Terraform scaffold for Glue databases and job;
- `.iam_policy.json`: review IAM policy template for the generated job role.
- `.performance.sql`: benchmark evidence query for runtime-sensitive mappings
  such as `hash_diff_upsert`.

The deployment manifest includes a non-blocking runtime script size budget. It
reports both the stable runner and generated Glue job bytes, and marks the
runtime artifact budget `WARN` above 256 KiB so large generated jobs are
visible during review before they become operational risk.

Every render also includes Iceberg DDL for canonical ContractForge evidence/control tables. Those schemas come from `contractforge_core.evidence`; the AWS adapter only maps them to Glue Catalog/Iceberg DDL. Generated Glue jobs create the needed evidence tables, record state as append-only AWS observations, and append final successful run evidence only after Glue `job.commit()` and after state, metadata and lineage evidence have completed. Failure paths write redacted `ctrl_ingestion_errors` evidence and a `FAILED` row in `ctrl_ingestion_runs` with `write_committed = false`; if evidence writing itself fails, the job logs that secondary failure and re-raises the original exception.

The first optional runtime helpers publish rendered artifacts to S3, register/update AWS Glue job definitions, start Glue job runs, inspect run status and map Glue `JobRun` metadata into core evidence record objects. They import `boto3` lazily only when the caller does not provide an AWS client, so planning/rendering remains SDK-free.

Glue job registration can use either explicit parameters or the deterministic `.glue_job_definition.json` payload rendered by the adapter. Payload registration strips review-only fields before calling Glue.

Lake Formation apply helpers are intentionally conservative. Table grants are directly applyable from the rendered plan. Data cell filters are skipped by default and require both `allow_data_cells_filters=True` and a concrete `account_id`, because row filters and column masks remain review-required semantics.

Glue Catalog annotation apply helpers read the current table definition and submit a preserved full `TableInput` through `UpdateTable`; they do not issue partial metadata updates that could drop storage descriptor, partition or table properties.

Operations recording helpers accept a caller-owned SQL runner and execute the canonical `ctrl_ingestion_operations` insert rendered by the adapter. They are runtime helpers, not scheduler/orchestrator behavior.

Evidence setup helpers accept a caller-owned SQL runner and execute the same Iceberg DDL rendered from `contractforge_core.evidence` for runs, errors, quality, quarantine, schema, metadata, lineage, access, operations, cost and state tables. Evidence setup requires a waiting SQL runner because the database and table DDL statements are ordered.

`AthenaSqlRunner` is provided as optional runtime plumbing for these SQL-runner helpers. It starts Athena queries through a caller-provided or lazily-created AWS client. Single-statement helpers may submit asynchronously, but evidence setup waits for completion.

Native passthrough stays review-only. The AWS artifact recommends concrete service paths and required review inputs, but it does not execute AppFlow, DMS or Glue connector APIs and does not certify proprietary source semantics.

Starting a Glue job through the optional runtime helper is not yet full ContractForge orchestration. Generated jobs persist their own run and quality evidence in Iceberg control tables, while post-run AWS `JobRun` reconciliation remains an explicit helper for supplemental run/cost evidence review.

Glue run waiting is available as a thin helper over `GetJobRun`; it returns on `SUCCEEDED` and raises on failed terminal states. It does not retry, restart or reconcile evidence automatically.

The same runtime helpers are exposed through the package CLI for operators who prefer shell-driven deployment:

```bash
contractforge-aws register-glue-job-payload .contractforge/orders.glue_job_definition.json

contractforge-aws wait-glue-job \
  --job-name cf-orders \
  --run-id jr_123 \
  --max-wait-seconds 3600

contractforge-aws register-glue-job \
  --job-name cf-orders \
  --role-arn arn:aws:iam::123456789012:role/ContractForgeGlueRole \
  --script-s3-uri s3://contractforge-artifacts/dev/orders.glue_job.py \
  --enable-job-bookmark

contractforge-aws ensure-evidence-tables \
  --database contractforge_ops \
  --athena-output-location s3://contractforge-query-results/athena/ \
  --warehouse-uri s3://contractforge-lakehouse/evidence/

contractforge-aws audit-evidence \
  --database contractforge_ops \
  --athena-output-location s3://contractforge-query-results/athena/

contractforge-aws apply-annotations contracts/customers.yaml --catalog-id 123456789012

contractforge-aws apply-lakeformation contracts/customers.yaml --account-id 123456789012

contractforge-aws record-operations contracts/customers.yaml \
  --database contractforge_ops \
  --run-id run-123 \
  --athena-output-location s3://contractforge-query-results/athena/
```

The adapter also exposes a manual, cost-gated minimal smoke runner:

```bash
contractforge-aws smoke \
  --account-id 123456789012 \
  --bucket contractforge-aws-smoke-123456789012-us-east-1 \
  --max-estimated-cost-usd 1.00 \
  --execute \
  --wait
```

Without `--execute`, the command is a dry run and prints the generated contract, expected S3 paths and timeout-based cost ceiling. This command is intentionally not part of normal CI.

## Development Phases

### Phase 1: Planning Skeleton

- Add docs and ADR.
- Add `contractforge-aws` package skeleton.
- Add `aws_glue_iceberg` capabilities.
- Add adapter API and review rendering.
- Add tests for supported, warning, review-required and unsupported behavior.

### Phase 2: Rendering

- Render Glue Spark scripts for append, overwrite, current-state upsert and hash-diff.
- Render portable preparation: select, rename, filter, casts, standardization, derived columns, composite keys, deterministic deduplication, JSON parsing, arrays, columns and flattening.
- Render mapped quality checks with ContractForge enforcement semantics: abort, warn evidence and row-level quarantine.
- Render Iceberg evidence/state DDL from the core control-table schema.
- Render Lake Formation review/apply scaffolds.
- Render IAM, Glue job definition, CloudFormation and Terraform deployment scaffolds as review artifacts.

### Phase 3: Runtime Prototype

- Publish rendered artifacts to S3 through `contractforge-aws[runtime]`.
- Register/update Glue job definitions with an explicit IAM role and published script URI.
- Start Glue job runs and inspect status without automatic evidence reconciliation.
- Map Glue `JobRun` metadata into core `RunEvidenceRecord` and `CostEvidenceRecord` objects.
- Render Iceberg `INSERT` SQL for reconciled run/cost evidence without applying it automatically.
- Execute append, overwrite and current-state upsert Glue/Iceberg paths in a controlled AWS account.
- Validate S3, JDBC, HTTP, REST, bounded stream, available-now stream and Delta Sharing source paths.
- Write Iceberg evidence tables.
- Validate quality and schema policy behavior.

### Phase 4: Merge And Hash Diff

- Validate Iceberg `MERGE INTO` through Glue Spark under production-sized data and concurrency.
- Keep hash-diff implementation aligned with core hash semantics.
- Add performance and concurrency diagnostics.

### Phase 5: Governance And Advanced Modes

- Validate Lake Formation data filters for Athena and other consumers.
- Evaluate historical and snapshot soft delete.
- Add native passthrough design for AppFlow/DMS.

## Documentation

Architecture contract: [AWS adapter spec](../specs/aws-adapter.md)

Researched capability matrix: [AWS capability parity](../specs/aws-capability-parity.md)

Decision record: [ADR-007 AWS Glue Iceberg Adapter](../adrs/ADR-007-aws-glue-iceberg-adapter.md)
