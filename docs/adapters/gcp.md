# GCP Adapter

`contractforge-gcp` starts with the `gcp_bigquery` subtarget.

The current surface is a stable-supported BigQuery render and smoke-execution surface:

- plan contracts against BigQuery capabilities;
- render BigQuery SQL for `append`, `overwrite` and `upsert`;
- render advanced write-mode review artifacts for `hash_diff_upsert`, `historical` and `snapshot_reconcile_soft_delete`;
- render GCS load-job JSON for CSV, JSON/JSONL/NDJSON, Parquet, Avro and ORC;
- render registered BigQuery/BigLake Iceberg table sources as normal BigQuery table reads;
- render redacted source-review JSON and Markdown artifacts with runtime path, prerequisites, graduation gates and non-JDBC source-family promotion paths;
- render source-family promotion-plan JSON for review-required raw Iceberg, Delta/Delta Sharing, undeclared/unsupported HTTP file variants and streaming sources;
- execute raw Iceberg BigLake registration and metadata readback through `source-promotion --execute --readback`;
- render authenticated REST/HTTP Secret Manager review artifacts and resolve placeholders at runtime when credentials use `{{ secret:scope/key }}`;
- render BigQuery evidence DDL for run and quality records;
- render BigQuery schema-policy planning artifacts and schema evidence DDL;
- optionally enforce schema policy for BigQuery table/view/SQL sources and declared-schema GCS load sources during smoke execution with `--enforce-schema-policy`;
- render Dataplex DataScan data-quality create and execution/readback planning artifacts from ContractForge quality rules;
- execute native Dataplex data-quality DataScans and read back BigQuery export rows through `dataplex-quality --execute --wait --readback`;
- render native Dataplex Data Lineage publication/readback plans and Dataplex aspect taxonomy/apply/readback plans from normal contracts;
- render or explicitly execute those native lineage/aspect plans through `dataplex-lineage-aspects`;
- render deterministic governance ledger/reconciliation artifacts, non-mutating governance reconciliation readback and governance evidence DDL;
- persist and read back governance evidence rows for declared governance intent during smoke execution;
- render query-only operational cost reports from BigQuery run evidence;
- render a deterministic deployment manifest that documents the single-contract BigQuery apply order;
- render dry-run project deployment manifests with per-contract BigQuery bundles, a Google Workflows source plan, an execution-plan artifact, an evidence-readback artifact, bounded BigQuery job polling, connector retry planning and an optional `bq` readback command path;
- persist run and quality evidence rows from BigQuery job results during executed smoke tests;
- persist neutral OpenLineage control-table evidence from executed load/write smoke operations;
- run project execution-order smokes sequentially through the same contract-only BigQuery runtime;
- apply, read back and enforce a BigQuery row access policy in the live governance smoke;
- create, attach, read back and enforce BigQuery/Data Catalog policy tags for column-level access;
- render, apply and read back BigQuery table/column descriptions for annotation contracts;
- classify unsupported or review-required sources, including canonical Delta, Delta Sharing, JDBC dialect, inline authenticated REST/HTTP credentials and streaming names, without pretending they are stable;
- dry-run or execute BigQuery contract smoke runs through `contractforge-gcp smoke`.

The adapter is stable-final for this documented surface. Direct raw Iceberg path execution without registration,
streaming, JDBC/Dataflow, inline authenticated REST/HTTP credentials,
historical/snapshot advanced write modes, non-Workflows deployment
runners, automatic type widening/mutation, automatic native Dataplex
lineage/aspect emission during every contract run, live governance-ledger reconciliation and tag-based masking
remain explicit exclusions from the scoped stable claim. The generated
Workflows source plan includes bounded BigQuery job polling and one generated
runner has passed live deploy/execute/readback. A second command-path smoke
validated `--deploy-orchestration --run-orchestration --wait-orchestration
--readback-orchestration` with a `bq` evidence readback. A third smoke validated
runner-side run and quality evidence persistence for generated Workflows. A
fourth smoke validated quality failed-row semantics through generated
Workflows: zero failed rows persist PASSED evidence, non-zero failed rows persist
FAILED evidence and then fail the Workflows execution. A fifth smoke validated
execution-scoped evidence ids based on the native Workflows execution id. A
sixth smoke validated schema evidence persistence from the generated schema
policy plan with execution-scoped evidence ids. A seventh smoke validated the
workflow-resource cleanup command path and missing-workflow idempotency. An
eighth smoke validated failed write/load run evidence before a generated
Workflows execution raises. A ninth smoke validated scoped target/evidence
cleanup through `--cleanup-orchestration-data`. The command surface also exposes
`--reset-orchestration-data` to run the same generated target/evidence cleanup
before deployment/execution when an operator wants a deterministic rerun.
The certified runner smoke ran the same ordered project twice through
`--reset-orchestration-data --deploy-orchestration --run-orchestration
--wait-orchestration --readback-orchestration`, with execution-scoped run,
quality and schema evidence readback for both executions.
`deploy-project` now exposes
explicit Workflows orchestration flags, generated YAML includes Workflows retry
blocks for BigQuery job submission and polling, and `--readback-orchestration`
can run the generated target/evidence queries through `bq`; when a workflow
execution id is available, run/quality/schema evidence readback is scoped to
that execution id. The Google Workflows deployment runner is certified for the
stable BigQuery batch surface; Cloud Run Jobs, Composer DAGs and scheduled
queries remain excluded until separately validated through the
adapter-owned command path.

Deployment manifests expose `execution_ready: true` only for supported planning
results. Review-required or blocked contracts still include deterministic
review artifacts and boundaries, but their `apply_order` is empty so generated
manifests do not imply executable BigQuery steps.

BigQuery `upsert` rendering is executable only when the contract declares
source columns through `select_columns` or `source.read.columns`. BigQuery MERGE
requires explicit update assignments, so the adapter emits a review-required SQL
comment instead of an invalid placeholder when columns are unknown.

Schema-policy planning artifacts are emitted for every rendered contract.
`strict` plans require a source/target preflight match. `additive_only` and
`permissive` plans document BigQuery nullable field-addition options and
`ALTER TABLE ADD COLUMN` review hints. The smoke runner also has an explicit
`--enforce-schema-policy` mode for BigQuery table/view/SQL sources and
declared-schema GCS load sources: it reads source and target schemas through
`INFORMATION_SCHEMA.COLUMNS`, applies additive nullable columns for
`additive_only` and `permissive`, blocks strict drift and writes
`contractforge_schema_evidence`. The additive nullable path passed live
validation in [GCP BigQuery schema-policy smoke](../reports/gcp-bigquery-schema-policy-smoke.json).
The strict negative path passed live validation in
[GCP BigQuery schema-policy strict smoke](../reports/gcp-bigquery-schema-policy-strict-smoke.json).
The permissive nullable path passed live validation in
[GCP BigQuery schema-policy permissive smoke](../reports/gcp-bigquery-schema-policy-permissive-smoke.json).
The destructive type-change path passed live validation in
[GCP BigQuery schema-policy type-change smoke](../reports/gcp-bigquery-schema-policy-type-change-smoke.json).
The SQL-source path passed live validation in
[GCP BigQuery schema-policy SQL source smoke](../reports/gcp-bigquery-schema-policy-sql-source-smoke.json).
The GCS/load-source path passed live validation in
[GCP BigQuery schema-policy GCS source smoke](../reports/gcp-bigquery-schema-policy-gcs-source-smoke.json).
Automatic BigQuery type widening or mutation is an explicit review-required
non-claim outside the stable schema-policy path, recorded in
[GCP schema-policy type mutation decision](../reports/gcp-schema-policy-type-mutation-decision.json).

Detailed parity tracking is in [GCP capability parity](../specs/gcp-capability-parity.md).
The stable-surface evidence manifest is [GCP stable-surface evidence](../reports/gcp-stable-surface-evidence.json).
Future promotion gates are exposed by `contractforge-gcp stabilization-report`
and mirrored in the stable-surface evidence manifest.

The first real smoke evidence is [GCP BigQuery CSV smoke](../reports/gcp-bigquery-csv-smoke.json):
one GCS CSV contract loaded three rows into BigQuery, ran evidence DDL, and
validated a not-null quality rule with `failed_rows = 0`. The current smoke also
persists run and quality evidence rows into the GCP evidence tables.

The file-format smoke is [GCP BigQuery file formats smoke](../reports/gcp-bigquery-file-formats-smoke.json):
CSV, NDJSON, Parquet, Avro and ORC fixtures loaded from GCS into BigQuery, each
with three rows, zero not-null failures and persisted run/quality evidence rows.

The upsert smoke is [GCP BigQuery upsert smoke](../reports/gcp-bigquery-upsert-smoke.json):
an explicit-column `MERGE` updated one row, inserted one row, preserved three
target rows, produced zero not-null failures and persisted run/quality evidence.

The bronze-to-gold smoke is [GCP BigQuery bronze-to-gold smoke](../reports/gcp-bigquery-bronze-to-gold-smoke.json):
bronze loads the GCS CSV fixture, silver reads bronze through a SQL contract,
and gold aggregates silver by status. The run validated row counts, quality
checks and run evidence rows for every layer.

The governance smoke is [GCP BigQuery row access policy smoke](../reports/gcp-bigquery-row-access-policy-smoke.json):
the adapter test applied a BigQuery row access policy to the silver table,
read it back through `bq ls --row_access_policies`, and queried as an
impersonated reader service account. The restricted principal saw only the two
`paid` rows allowed by the policy.

The failed-run evidence smoke is [GCP BigQuery error evidence smoke](../reports/gcp-bigquery-error-evidence-smoke.json):
a normal SQL-source contract intentionally referenced a missing BigQuery table.
The write failed as expected, and the adapter persisted a `FAILED` run evidence
row with the native error message after escaping multi-line BigQuery text for
SQL insertion.

The canonical `cost-report` command renders a BigQuery SQL report over
`contractforge_run_evidence`, grouped by adapter, contract, statement, status or
target table. The adapter does not hard-code rates; estimated values are present
only when the operator supplies bytes-processed and/or slot-hour rates.

The direct column data masking smoke is [GCP BigQuery data masking smoke](../reports/gcp-bigquery-data-masking-smoke.json):
the adapter maturity run created a BigQuery V2 data masking policy, attached it
directly to a column, granted fine-grained read to a restricted service account,
and queried through impersonation. The protected `amount` column returned
`NULL` under the `ALWAYS_NULL` masking rule. The earlier non-organization
project blocker remains documented in [GCP BigQuery data masking blocker](../reports/gcp-bigquery-data-masking-blocker.json).

The policy-tag smoke is [GCP BigQuery policy tags smoke](../reports/gcp-bigquery-policy-tags-smoke.json):
the adapter maturity run created a regional Data Catalog taxonomy and policy
tag, attached the policy tag to a BigQuery column, read it back through
`INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`, verified denied protected-column access
before fine-grained access was granted, then verified access after granting
`roles/datacatalog.categoryFineGrainedReader`. This validates policy tags as a
column-level access surface, not as a substitute for direct masking policies.

The BigLake Iceberg smoke is [GCP BigLake Iceberg smoke](../reports/gcp-biglake-iceberg-smoke.json):
the adapter maturity run created a BigLake managed Iceberg table backed by a
dedicated Cloud Storage prefix and BigQuery Cloud Resource connection, appended
rows, ran a `MERGE`, queried the final rows, read back `biglakeConfiguration`,
and observed Iceberg `metadata/` plus Parquet `data/` objects. The supported
adapter surface is registered BigQuery/BigLake Iceberg table references.
For raw `source.type: iceberg_table` contracts with a `gs://` `path`, rendered
bundles include a deterministic BigLake registration plan with the required
Cloud Resource connection, connection service-account storage role, `bq mk`
flags (`--managed_table_type=BIGLAKE`, `--table_format=ICEBERG`,
`--file_format=PARQUET`, `--storage_uri`) and the post-registration
`source.type: iceberg_table` table reference that should replace the raw path
after readback passes. The raw registration command is validated in
[GCP raw Iceberg registration smoke](../reports/gcp-raw-iceberg-registration-smoke.json):
`contractforge-gcp source-promotion --execute --readback` creates a BigLake
Iceberg table from a declared `gs://` prefix with explicit schema, reads back
`biglakeConfiguration` and verifies the registered table is queryable. Direct
raw-path query execution without registration remains excluded.

The authenticated REST Secret Manager smoke is
[GCP authenticated REST Secret Manager smoke](../reports/gcp-authenticated-rest-secret-manager-smoke.json):
the adapter resolved a `{{ secret:scope/key }}` credential through Google
Secret Manager at runtime, used the shared core REST reader and loaded the
materialized records into BigQuery without writing the secret value to evidence.

The streaming scope decision is [GCP streaming scope decision](../reports/gcp-streaming-scope-decision.json):
Confluent/Dataflow `kafka_available_now` provider parity is validated with a
contract-owned Dataflow Kafka-to-BigQuery run, BigQuery row ingestion, zero-DLQ
reconciliation and a same-consumer-group no-input replay. Direct Pub/Sub
BigQuery subscriptions are native, but they are not equivalent to ContractForge
`kafka_available_now`; broader Pub/Sub, Event Hubs and production streaming
operations remain review-scoped outside the first stable GCP surface. Rendered
promotion plans for Kafka/Event Hubs sources include the Google-provided
Dataflow Kafka-to-BigQuery template parameters, Secret Manager auth hooks,
consumer group, checkpoint location, offset evidence requirements and explicit
non-claims for continuous streaming.

Delta and Delta Sharing contracts remain review-required on GCP. Their
promotion plans now describe the Dataproc Serverless Spark materialization
track: dependency set, landing prefix, credential boundary, post-materialization
BigQuery table source and the version/snapshot, row-count and failure evidence
needed before execution can be promoted.

The write-mode scope decision is [GCP write-mode scope decision](../reports/gcp-write-mode-scope-decision.json):
the first stable GCP surface is limited to `append`, `overwrite` and
explicit-column `upsert`. `hash_diff_upsert` production parity is accepted in
[GCP hash-diff cross-adapter production parity](../reports/gcp-hashdiff-cross-adapter-production-parity.json)
using GCP, AWS, Snowflake and Fabric evidence, but it remains review-gated by
default until the stable execution surface is explicitly widened. `historical`
and `snapshot_reconcile_soft_delete` stay review-required until cross-adapter
production contracts prove validity windows and tombstone semantics. Rendered
bundles now include deterministic advanced
write-mode review artifacts with candidate BigQuery SQL, blockers and promotion
evidence requirements; deployment manifests still keep execution blocked.

The deployment/orchestration scope decision is [GCP deployment/orchestration scope decision](../reports/gcp-deployment-orchestration-scope-decision.json):
single-contract smoke execution is available, and `deploy-project` now
materializes per-contract bundles, a project deployment manifest and a generated
Google Workflows source plan with bounded BigQuery job polling. It also exposes
`--render-orchestration`, `--deploy-orchestration`, `--run-orchestration`,
`--wait-orchestration`, `--readback-orchestration` and
`--reset-orchestration-data`, `--cleanup-orchestration` and
`--cleanup-orchestration-data` for the generated
Workflows runner. The generated YAML
uses `http.default_retry_predicate_non_idempotent` for BigQuery job submission
and `http.default_retry_predicate` for job polling, and emits a
`gcp_workflows_evidence_readback.json` artifact with target-count,
run-evidence, quality-evidence, schema-evidence and evidence-table presence
queries, execution-scoped readback templates plus a
`gcp_workflows_cleanup_plan.json` artifact with scoped target and
evidence cleanup statements. `--readback-orchestration` executes those queries with `bq` after the
runner path, and `--readback-location` can override a stale environment
location for the readback or cleanup queries. One generated runner
passed live deploy/execute/readback in
[GCP Workflows runner smoke](../reports/gcp-workflows-runner-smoke.json), and
the adapter-owned command path passed
[GCP Workflows command readback smoke](../reports/gcp-workflows-command-readback-smoke.json),
and runner-side run/quality evidence persistence passed
[GCP Workflows runner evidence smoke](../reports/gcp-workflows-runner-evidence-smoke.json).
Quality failed-row semantics passed
[GCP Workflows quality semantics smoke](../reports/gcp-workflows-quality-semantics-smoke.json).
Execution-scoped evidence ids passed
[GCP Workflows execution run-id smoke](../reports/gcp-workflows-execution-runid-smoke.json).
Schema evidence persistence passed
[GCP Workflows schema evidence smoke](../reports/gcp-workflows-schema-evidence-smoke.json).
Workflow cleanup command validation passed
[GCP Workflows cleanup command smoke](../reports/gcp-workflows-cleanup-command-smoke.json). A
controlled write-failure path passed
[GCP Workflows write-failure evidence smoke](../reports/gcp-workflows-write-failure-evidence-smoke.json). A
scoped target/evidence cleanup path passed
[GCP Workflows target/evidence cleanup smoke](../reports/gcp-workflows-target-evidence-cleanup-smoke.json). The
certified Workflows runner passed
[GCP Workflows certified runner smoke](../reports/gcp-workflows-certified-runner-smoke.json).
Cloud Run Jobs, Composer DAGs and BigQuery scheduled-query runners remain
outside this stable claim until separately certified.

The canonical `run-project` command executes the project `execution_order`
sequentially through the same contract-only smoke runtime used by
`smoke`. This is validation workflow support, not a native
Composer, Cloud Run Jobs or scheduled-query deployment runner.

The Dataplex lineage and data-quality scope decision is [GCP Dataplex lineage and DQ scope decision](../reports/gcp-dataplex-lineage-dq-scope-decision.json):
SQL quality checks and BigQuery control-table evidence, including neutral
OpenLineage event payloads, are in scope. Rendered bundles now include
deterministic Dataplex DataScan create-request JSON plus command/readback
metadata, native Dataplex Data Lineage publication/readback plans and Dataplex
aspect taxonomy/apply/readback plans for review. The `dataplex-lineage-aspects`
command is non-mutating by default and only publishes lineage or applies aspects
when `--execute` is set; `--readback` requests native API readback. The adapter-owned Dataplex
quality command passed a live native DataScan run over a 10,000-row BigQuery
target and read back seven exported rule-result rows. The adapter-owned
`dataplex-lineage-aspects --execute --readback` command passed native lineage
event readback and Knowledge Catalog/Dataplex aspect `modifyEntry` readback in
[GCP Dataplex lineage/aspects smoke](../reports/gcp-dataplex-lineage-aspects-smoke.json).
Automatic native lineage/aspect emission during every contract run remains
outside the scoped stable claim.

The governance stable-scope decision is [GCP governance stable-scope decision](../reports/gcp-governance-stable-scope-decision.json):
validated row access policies, direct column data policies, policy-tag column
access, table/column descriptions, deterministic governance ledger planning,
non-mutating governance reconciliation readback, governance evidence
write/readback for declared governance intent and core evidence writes are in
scope.
Tag-based masking, policy-tag-backed masking, automatic governance repair/delete
and overwrite-retention behavior remain excluded from the first stable GCP
surface.

The annotation smoke is [GCP BigQuery annotations smoke](../reports/gcp-bigquery-annotations-smoke.json):
the adapter maturity run applied a table description and a column description
with native BigQuery `OPTIONS(description)`, then read them back through
`INFORMATION_SCHEMA.TABLE_OPTIONS` and `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`.
It also persisted two annotation audit rows to `contractforge_annotation_evidence`.
Aliases, tags, PII metadata and operations metadata render Dataplex aspect
plans, and explicit command-path AspectType creation, `modifyEntry` execution
and aspect readback are validated in the Dataplex lineage/aspects smoke.
