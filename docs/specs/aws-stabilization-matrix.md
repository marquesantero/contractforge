# AWS Stabilization Matrix

## Purpose

This spec defines the release gate for stabilizing the `contractforge-aws`
adapter. It is not a roadmap of possible AWS features. It is the checklist that
decides whether the first AWS adapter can be called stable for the supported
surface.

The target is `aws_glue_iceberg`:

- AWS Glue Spark runtime;
- Apache Iceberg tables on Amazon S3;
- AWS Glue Data Catalog metadata;
- optional Lake Formation review artifacts;
- ContractForge evidence tables persisted as Iceberg tables.

The adapter must preserve core semantics. If an AWS runtime cannot preserve a
contract behavior, the planner or renderer must return `REVIEW_REQUIRED`,
`SUPPORTED_WITH_WARNINGS` or `UNSUPPORTED`. It must not silently downgrade the
contract.

## Stabilization Scope

The stable candidate scope is intentionally smaller than the full AWS thesis.

| Area | Stable candidate scope | Out of scope for stable candidate |
| --- | --- | --- |
| Sources | `s3`, portable file formats, `rest_api`, `http_file`, `jdbc`/Postgres, `incremental_files` | AppFlow, DMS, proprietary SaaS connectors, continuous streaming |
| Write modes | `append`, `overwrite`, `upsert`, `hash_diff_upsert` | historical equivalence, snapshot soft delete |
| Quality | abort, warn, row-level quarantine for supported rules, expression quality with warning | engine-specific quality dialect guarantees |
| Preparation | shape parsing, arrays, columns, flattening, casts, standardization, derived columns, composite keys, deduplication | unsupported shape operations such as unsafe bronze array explosions |
| Evidence | runs, errors, quality, quarantine, schema changes, metadata, lineage, state, cost, operations | alternate evidence stores other than Iceberg |
| Governance | Glue Catalog annotations and conservative Lake Formation review/apply helpers | automatic certification of row filters and column masks across all consumers |
| Deployment | local project dry-run, render, publish artifacts to S3, create/update Glue job, start/wait job, project-level deploy/start/wait in `project.yaml` order | full scheduler/orchestrator behavior |
| Artifact size | deployment manifest reports per-artifact bytes/lines, runtime script bytes and a non-blocking 256 KiB runtime warning threshold | hard blocking size limits are a future release gate after runtime benchmarks |

## Required Test Projects

The AWS adapter cannot be stabilized from renderer tests alone. These projects
must run in a real AWS account using only contracts, environment files and
ContractForge commands. The generated Glue scripts may be inspected, but no
manual Glue Studio edits are allowed.

| Project | Source | Main purpose | Required result |
| --- | --- | --- | --- |
| `aws_supabase_jdbc_medallion` | Supabase/Postgres JDBC | JDBC, secrets, partitioned reads, current-state/hash diff, quality quarantine, medallion dependencies | Bronze, silver and gold Iceberg tables created with matching control evidence |
| `aws_usgs_rest_medallion` | USGS GeoJSON REST API | REST connector, JSON shape parsing, flattening, medallion promotion | API response lands and transforms without Python workaround code |
| `aws_s3_file_medallion` | S3 CSV files | Portable file formats, schema policy, Glue bookmarks, current-state/hash diff, quality quarantine and SQL promotion | First run processes seed files, rerun preserves deterministic counts, new files are picked up by bookmarks |
| `aws_incremental_files` | S3 incremental files | Dedicated bookmark/state stress test over multiple upload waves and no-new-input reruns | Second run skips already processed files; new files are picked up; no-new-input rerun records `SKIPPED` without duplicating rows |
| `aws_failure_paths` | Controlled bad contracts and runtime failures | Error evidence, failed run evidence, redaction | Glue run fails natively and writes redacted ContractForge evidence |
| `aws_eventhubs_kafka_available_now` | Azure Event Hubs Kafka endpoint | Glue Structured Streaming `availableNow`, checkpoint progress, quality quarantine and stream evidence | First run consumes messages, no-input rerun writes zero rows, invalid batch quarantines rows, later valid batch resumes from checkpoint |

Hash-diff scenarios must declare `merge_keys` and a hash strategy. `merge_keys`
are the durable row identity used in the Iceberg `MERGE ON` clause. For
governed tables, prefer `hash_keys` as the explicit content columns used to
compute `row_hash`. For wide tables, use `hash_strategy: all_columns_except`
with `hash_exclude_columns`. The AWS adapter always excludes user-declared and
ContractForge/framework-generated columns from hashing and blocks
`hash_diff_upsert` without `merge_keys` with
`AWS_HASH_DIFF_MERGE_KEYS_REQUIRED`.

## Deployment Flow Gate

Every real test project must use the same operator flow:

```text
contractforge-aws plan
  -> contractforge-aws render
  -> contractforge-aws publish-s3
  -> contractforge-aws deploy
  -> contractforge-aws start
  -> contractforge-aws wait
```

`deploy` may combine render, publish and job registration when
`environment.artifacts.uri` is declared. That shortcut is valid only when the
same rendered artifacts and job definition are observable in S3.

Acceptance criteria:

- the environment contract owns the artifact S3 URI;
- generated scripts, manifests, normalized contracts and original split
  contracts are published to S3;
- Glue job definitions use the published `ScriptLocation`;
- project execution retries `ConcurrentRunsExceededException` within the
  declared wait budget instead of crashing with a raw AWS SDK stack;
- no user code is required inside Glue Studio;
- all platform-specific defaults come from `environment.parameters.aws` or
  reviewed `extensions.aws.*`;
- the core package remains free of AWS SDK imports.

## Runtime Success Gate

Each success scenario must prove:

- the target Iceberg table is created when missing;
- the target table is written through the selected write engine;
- rows read, written and quarantined are correct;
- schema changes are recorded when columns are added or type changes are
  detected;
- quality evidence is written for abort, warn and quarantine rules;
- quarantine rules remove failed rows before the target write;
- `ctrl_ingestion_runs.status = SUCCESS` is written only after `job.commit()`;
- `write_committed` is true for successful committed runs;
- source metadata, lineage, state and cost evidence are populated where
  available.
- a Glue bookmark run with no new input records `ctrl_ingestion_runs.status =
  SKIPPED`, `quality_status = SKIPPED`, `skip_reason = no_new_input`,
  `rows_read = 0`, `rows_written = 0`, `write_committed = false`, and does not
  run preparation/write logic that depends on source columns.

## Failure Gate

The failure matrix must include at least these cases:

| Failure case | Expected behavior |
| --- | --- |
| invalid JDBC secret | Glue job fails; `ctrl_ingestion_errors` redacts the secret; `ctrl_ingestion_runs.status = FAILED` |
| missing S3 source path | Glue job fails; source path is recorded without credentials |
| blocked REST URL or invalid scheme | adapter/runtime rejects before fetching |
| quality abort violation | Glue job fails; quality evidence records the failed rule |
| invalid merge key | renderer or runtime fails before unsafe write |
| target permission failure | Glue job fails; error evidence is best effort and redacted |

Failure evidence must preserve the original exception. If writing error evidence
fails, the generated job may log that secondary failure, but it must re-raise
the original runtime exception.

## Control Table Audit

Every real run must be audited through the canonical evidence tables rendered
from `contractforge_core.evidence`.

Required tables:

- `ctrl_ingestion_runs`
- `ctrl_ingestion_errors`
- `ctrl_ingestion_quality`
- `ctrl_ingestion_quarantine`
- `ctrl_ingestion_schema_changes`
- `ctrl_ingestion_metadata`
- `ctrl_ingestion_lineage`
- `ctrl_ingestion_access`
- `ctrl_ingestion_operations`
- `ctrl_ingestion_cost`
- `ctrl_ingestion_state`
- `ctrl_ingestion_locks`

Minimum Athena validation queries:

```sql
SELECT status, count(*) AS runs
FROM "<evidence_database>"."ctrl_ingestion_runs"
GROUP BY status;

SELECT quality_status, count(*) AS runs
FROM "<evidence_database>"."ctrl_ingestion_runs"
GROUP BY quality_status;

SELECT target_table, count(*) AS quality_rows
FROM "<evidence_database>"."ctrl_ingestion_quality"
GROUP BY target_table;

SELECT target_table, count(*) AS quarantined_rows
FROM "<evidence_database>"."ctrl_ingestion_quarantine"
GROUP BY target_table;

SELECT target_table, count(*) AS errors
FROM "<evidence_database>"."ctrl_ingestion_errors"
GROUP BY target_table;

SELECT cost.target_table, count(*) AS cost_rows, sum(cost.signal_value) AS glue_dpu_seconds
FROM "<evidence_database>"."ctrl_ingestion_cost" cost
INNER JOIN "<evidence_database>"."ctrl_ingestion_runs" runs
  ON runs.run_id = cost.run_id
 AND runs.target_table = cost.target_table
WHERE cost.signal_name = 'glue_dpu_seconds'
GROUP BY cost.target_table;
```

The audit must compare AWS evidence with the Databricks parity project when the
same contract intent is tested on both adapters.

The supported operator command for this audit is:

```powershell
uv run contractforge-aws audit-evidence `
  --database <evidence_database> `
  --athena-output-location s3://<bucket>/athena-results/
```

The command runs the standard query set above through `AthenaSqlRunner` and
returns the row groups as JSON, including cost rows when they have been
reconciled. It is a read-only validation helper; it does not create evidence
tables or mutate runtime state.

Cost evidence is an explicit post-run reconciliation step because Glue `JobRun`
DPU seconds are available from the AWS API after the job reaches a terminal
state, not from inside the generated Glue script. Project runs can opt in with:

```powershell
uv run contractforge-aws deploy-project <project.yaml> `
  --run `
  --wait `
  --record-cost-evidence `
  --athena-output-location s3://<bucket>/athena-results/
```

This writes only `ctrl_ingestion_cost` rows. It does not duplicate
`ctrl_ingestion_runs`; the generated Glue job remains the owner of run evidence.
The reconciliation stores the cost row under the canonical ContractForge run id
(`job_name:glue_run_id`) and preserves the raw Glue run id in the payload so
audit and benchmark queries can join cost to run evidence without counting
orphan platform records.

## IAM And Security Gate

The AWS adapter stable candidate must pass these checks:

- no AWS SDK import from `contractforge_core`;
- no eager `boto3` import from the base `contractforge_aws` import path;
- no plaintext secret in rendered artifacts;
- secret references resolve through environment/runtime secret mechanisms;
- generated jobs redact exception messages and stack traces before evidence
  writes;
- REST and HTTP fetchers reject unsupported schemes, unsafe hosts and redirects;
- Glue job IAM policy artifacts are least-privilege review templates, not
  blanket `*` policies;
- IAM artifacts include source, warehouse, artifact, script and dependency S3
  boundaries derived from the contract/environment;
- Lake Formation row filters and column masks remain `REVIEW_REQUIRED` unless
  the adapter has a tested consumer-engine guarantee.

## Performance Gate

For the supported scope, capture at least:

- Glue version;
- worker type and worker count;
- DPU seconds or equivalent job cost signal;
- source row count;
- target written row count;
- quarantined row count;
- merge key cardinality;
- Iceberg snapshot before and after write;
- job duration;
- generated job script size.

The renderer must include `*.performance_profile.json` and `*.performance.sql`
artifacts for runtime-sensitive write modes. The profile defines the metrics
and benchmark cases to capture. The SQL reports those runs from
`ctrl_ingestion_runs` and `ctrl_ingestion_cost`. These artifacts do not replace
a real AWS benchmark.

`hash_diff_upsert` remains `SUPPORTED_WITH_WARNINGS` until Glue/Iceberg merge
performance is validated under a representative update volume and concurrent
write risk is documented.

## Release Gates

| Gate | Requirement | Status values |
| --- | --- | --- |
| G0 local suite | Unit and render tests pass | `PASS`, `FAIL` |
| G1 render compile | All real projects render and generated Python compiles | `PASS`, `FAIL` |
| G2 deploy flow | Artifacts publish to S3 and Glue jobs register/update | `PASS`, `FAIL` |
| G3 success runtime | Required real projects complete successfully | `PASS`, `FAIL` |
| G4 failure runtime | Failure matrix writes redacted error and failed-run evidence | `PASS`, `FAIL` |
| G5 control audit | Evidence tables match expected counts and statuses | `PASS`, `FAIL` |
| G6 parity | Databricks/AWS/Snowflake contract differences relevant to the AWS stable surface are documented and minimal | `PASS`, `REVIEW_REQUIRED`, `FAIL` |
| G7 docs | AWS user docs, specs and site reflect tested behavior | `PASS`, `FAIL` |
| G8 lifecycle | Real-test cloud resources have a documented, non-destructive cleanup plan | `PASS`, `FAIL` |

The adapter is not stable until all gates are `PASS` except explicitly accepted
`REVIEW_REQUIRED` parity items.

The machine-readable status command is:

```powershell
uv run contractforge-aws stabilization-report
```

The intended release classification is `STABLE_SUPPORTED_SURFACE` with
`supported_surface_ready: true` and `stable_final: true` for the documented
AWS Glue/Iceberg claim. The reference hash-diff production benchmark is
validated, while workload-specific SLA claims still require attached evidence.
Non-MSK Kafka compatibility, arbitrary Lake Formation expressions and
historical/snapshot soft delete are explicit exclusions from stable-final unless
separately certified. CI jobs can run `stabilization-report --strict-final`,
which exits zero while this documented stable-final claim remains satisfied.

## Stabilization Tracker

| Item | Current status | Notes |
| --- | --- | --- |
| Local AWS adapter unit tests | `PASS` | Renderer and helper tests pass locally. |
| Project render/compile dry-run | `PASS` | `deploy-project --dry-run --summary-only` validates planning, rendering and Python compilation for Supabase, USGS, S3 file, incremental-files and failure-path projects without AWS API calls. Each runnable step now compiles the stable library runner plus the generated review script. |
| AWS library runner runtime | `PASS` | Completed on 2026-06-02 across S3 file, incremental-files, USGS REST, Supabase JDBC, failure-path and available-now streaming projects. All registered Glue job definitions pointed to `runtime/contractforge_aws_runner.py`; generated `<target>.glue_job.py` artifacts remained review/fallback artifacts. |
| Real Supabase JDBC AWS project | `PASS` | Completed on 2026-06-02 through `deploy-project --run --wait --record-cost-evidence --audit-evidence`, using contracts, environment and adapter CLI only. All five Glue jobs succeeded through the stable runner, bronze quality statuses remained `QUARANTINED`, downstream quality statuses remained `PASSED`, audit showed no error rows, and cost evidence was recorded for every target. |
| Real USGS REST AWS project | `PASS` | Completed on 2026-06-02 through `deploy-project --run --wait --record-cost-evidence --audit-evidence`. All four Glue jobs succeeded through the stable runner, audit showed all historical runs successful, all quality status `PASSED`, no quarantine rows, no error rows, and joined DPU-second cost rows for all four targets. |
| S3 file project | `PASS` | Completed on 2026-06-02 through `deploy-project --run --wait --record-cost-evidence --audit-evidence`. All three Glue jobs succeeded through the stable runner; target counts remained bronze=7, silver=7, gold=3; audit records success, quality, quarantine and cost evidence. |
| Incremental files project | `PASS` | Completed on 2026-06-02 through `deploy-project --run --wait --record-cost-evidence --audit-evidence`. The latest run succeeded through the stable runner against existing bookmark state and recorded cost/audit evidence; historical evidence preserves wave 1, wave 2 and no-new-input `SKIPPED` runs. |
| Failure-path project | `PASS` | Completed on 2026-06-02 after `ensure-evidence-tables` created Athena Iceberg evidence/state tables. `deploy-project --run --wait --accept-expected-failures --record-cost-evidence --audit-evidence` produced two `EXPECTED_FAILURE` Glue runs through the stable runner, failed-run rows, error evidence for both targets, abort-quality evidence for `quality_abort_orders`, and DPU-second cost evidence for both targets. |
| Available-now streaming evidence | `PASS` | Real Azure Event Hubs through Kafka protocol validation completed on 2026-06-02 using `examples/real-world/aws-eventhubs-kafka-available-now`; AWS MSK Serverless validation completed on 2026-06-10 and is recorded in `docs/reports/aws-kafka-provider-matrix.json`. Both paths used ContractForge commands and the stable runner, retained checkpointed stream evidence, recorded DPU-second cost evidence and passed Athena audit over run, quality, quarantine, error and cost tables. MSK is the AWS-native Kafka maturity provider; non-MSK compatibility providers still require provider-specific review before broader compatibility claims. |
| Control-table audit | `PASS` | Supabase, USGS, S3 file, incremental-files, failure-path and available-now streaming projects were audited through Athena using ContractForge evidence tables. |
| IAM/security review | `PARTIAL_PASS` | IAM templates derive source, warehouse, artifact, script and dependency S3 boundaries from contract/environment; runtime jobs executed under the configured Glue role, but least-privilege policy application remains review-owned. |
| Performance profile | `PARTIAL_READY` | Planner warns on `hash_diff_upsert`; render emits a benchmark profile and deployment manifest exposes generated artifact size. Project CLI reconciled Glue `DPUSeconds` into `ctrl_ingestion_cost` for the incremental-files AWS benchmark set: initial load `278.0`, changed subset `290.0`, skipped reruns `184.0`, `234.0`, `242.0`; audit rollup joins five canonical run ids for `1228.0` DPU seconds. Supabase JDBC benchmark evidence exposed and fixed the hash-diff key split: `merge_keys` now drive row identity, explicit `hash_keys` or `hash_strategy: all_columns_except` drive content comparison, and generated columns are excluded automatically. Real bronze products reruns on 2026-06-01 validated both paths: no-change returned `status=SKIPPED`, `skip_reason=no_hash_changes`, `rows_written=0`, unchanged Iceberg snapshot id and `hash_diff_candidate_rows=0`; a 10-row source mutation returned `status=SUCCESS`, a new Iceberg snapshot id and `hash_diff_candidate_rows=10`. Iceberg physical file rewrite counters remain separate from business candidate counts. Concurrency benchmarks still need broader production-volume evidence. |
| Cleanup lifecycle | `PASS` | `contractforge-aws cleanup-project` renders a non-destructive cleanup plan from `project.yaml`, including Glue job names, artifact and warehouse S3 prefixes, evidence database and declared external resources. The Event Hubs streaming project declares the Azure resource group used by the Kafka-compatible Event Hubs namespace. |
| Docs/site update | `PASS` | Runtime evidence is recorded in this matrix, AWS adapter docs and the documentation site. |
