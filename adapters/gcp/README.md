# contractforge-gcp

`contractforge-gcp` is the Google Cloud adapter package for ContractForge.

The first implemented subtarget is `gcp_bigquery`. It renders BigQuery SQL,
GCS load-job configuration, schema-policy planning artifacts, an opt-in
schema-policy runtime hook for table sources, advanced write-mode review
artifacts, Dataplex data-quality create/execution/readback planning artifacts,
native Dataplex lineage/aspect command-path execution/readback evidence,
governance ledger/reconciliation artifacts, evidence DDL, source-support
review artifacts, deterministic deployment manifests, a Google Workflows
project-runner plan, execution-plan artifact and evidence-readback artifact for
review.
It also executes a single-contract BigQuery smoke that can persist run and
quality evidence, plus a compact bronze-to-gold BigQuery smoke. The documented
BigQuery batch surface is stable-final; direct raw Iceberg path execution without
registration, advanced write modes, tag-based masking, broad streaming, automatic type widening/mutation, automatic
native Dataplex lineage/aspect emission, governance auto-repair/delete and non-Workflows
deployment runners are explicit exclusions from that scoped claim.

Install:

```bash
pip install contractforge-core contractforge-gcp
```

Use:

```bash
contractforge-gcp --help
contractforge-gcp plan path/to/contract.ingestion.yaml
contractforge-gcp render path/to/contract.ingestion.yaml --environment path/to/environment.yaml
contractforge-gcp render path/to/contract.ingestion.yaml --environment path/to/environment.yaml --output-dir .tmp/gcp-bundle
contractforge-gcp deploy-project path/to/project.yaml --dry-run --summary-only --output-dir .tmp/gcp-project-bundle
contractforge-gcp deploy-project path/to/project.yaml --deploy-orchestration --run-orchestration --wait-orchestration --readback-orchestration --readback-location us-east1
contractforge-gcp deploy-project path/to/project.yaml --reset-orchestration-data --deploy-orchestration --run-orchestration --wait-orchestration --readback-orchestration --readback-location us-east1
contractforge-gcp deploy-project path/to/project.yaml --cleanup-orchestration
contractforge-gcp deploy-project path/to/project.yaml --cleanup-orchestration-data --readback-location us-east1
contractforge-gcp sources
contractforge-gcp stabilization-report
contractforge-gcp source-promotion path/to/raw-iceberg-contract.yaml --environment path/to/environment.yaml --execute --readback
contractforge-gcp smoke path/to/contract.ingestion.yaml --environment path/to/environment.yaml
contractforge-gcp smoke path/to/contract.ingestion.yaml --environment path/to/environment.yaml --execute --enforce-schema-policy
contractforge-gcp run-project path/to/project.yaml --report .tmp/gcp-project-smoke.json
contractforge-gcp cost-report --environment path/to/environment.yaml --group-by target_table
```

Supported first slice:

- BigQuery table, view and SQL sources.
- GCS files with BigQuery load formats: CSV, JSON/JSONL/NDJSON, Parquet, Avro and ORC.
- Registered BigQuery/BigLake Iceberg table sources.
- Live GCS file-format smoke for CSV, NDJSON, Parquet, Avro and ORC.
- Live bronze-to-gold BigQuery smoke using GCS bronze, SQL silver and SQL gold contracts.
- Live BigQuery row access policy smoke with apply, readback and restricted-principal enforcement.
- Live BigQuery direct column data masking smoke with V2 data policy attachment and restricted-principal enforcement.
- Live BigQuery/Data Catalog policy-tag column-access smoke with deny-before-grant and allow-after-grant validation.
- Live BigLake managed Iceberg smoke with create, append, MERGE, query and storage-layout readback.
- Raw Iceberg BigLake registration command surface through `source-promotion --execute --readback`, validated with explicit schema, provider metadata readback and registered-table query readback.
- Authenticated REST/HTTP credentials with `{{ secret:scope/key }}` placeholders resolve through Google Secret Manager at runtime; a live authenticated REST smoke validated the core reader plus BigQuery local load path.
- Streaming scope decision: Confluent/Dataflow `kafka_available_now` provider parity is validated with row ingestion, zero-DLQ reconciliation and no-input replay; broader Kafka/Event Hubs/Dataflow/Pub/Sub streaming remains review-scoped outside the first stable surface.
- Write-mode scope decision: stable GCP writes are `append`, `overwrite` and explicit-column `upsert`; advanced write-mode review artifacts are generated for `hash_diff_upsert`, `historical` and `snapshot_reconcile_soft_delete`. The hash-diff production parity decision is accepted, while historical and snapshot remain review-gated until cross-adapter production parity is accepted.
- Schema-policy planning artifacts for `strict`, `additive_only` and `permissive`.
- Opt-in schema-policy runtime enforcement for BigQuery table/view/SQL sources and declared-schema GCS load sources through `--enforce-schema-policy`; it reads source and target schemas, applies additive nullable columns for `additive_only` and `permissive`, blocks strict drift and writes schema evidence.
- Live additive nullable schema-policy smoke with target schema and evidence readback.
- Live strict negative schema-policy smoke with failed schema evidence readback.
- Live permissive nullable schema-policy smoke with target schema and evidence readback.
- Live destructive type-change schema-policy smoke with failed schema evidence readback.
- Live SQL-source schema-policy smoke with probe cleanup, target schema and evidence readback.
- Live GCS/load-source schema-policy smoke with declared source columns, probe cleanup, target schema and evidence readback.
- Schema-policy type-mutation decision: automatic BigQuery type widening or mutation is review-required outside the stable runtime path.
- Certified Workflows project-runner support for ordered project contracts, including command metadata, connector retry planning, runner-side run/quality/schema evidence writes, failed write/load run evidence, quality failed-row evidence semantics, execution-scoped evidence ids, broad or execution-scoped evidence-readback queries through `bq`, pre-run target/evidence reset through explicit `--reset-orchestration-data`, workflow-resource cleanup through `gcloud workflows delete`, post-run target/evidence cleanup through explicit `--cleanup-orchestration-data` and repeated full-project rerun execution/readback; `--readback-location` can override stale BigQuery readback/cleanup location at execution time.
- Deployment/orchestration scope decision: Google Workflows is certified for the stable BigQuery surface; non-Workflows runners are excluded from the first stable surface.
- Dataplex data-quality create and execution/readback planning artifacts for ContractForge quality rules.
- Live Dataplex data-quality execution/readback smoke: a native DataScan job scanned 10,000 BigQuery rows and exported seven rule-result rows.
- Dataplex lineage/aspects scope decision: explicit `dataplex-lineage-aspects --execute --readback` command-path validation passed for native lineage events and Knowledge Catalog/Dataplex aspect modifyEntry/readback; automatic emission during every contract run remains excluded.
- Governance stable-scope decision: validated row policies, direct masking, policy-tag column access, descriptions, deterministic governance ledger/reconciliation artifacts, non-mutating reconciliation readback and governance evidence write/readback are in scope; automatic repair/delete and overwrite-retention are excluded.
- Stable-surface evidence manifest: `docs/reports/gcp-stable-surface-evidence.json`.
- Future promotion gates are machine-readable in `contractforge-gcp stabilization-report` and documented in `docs/specs/gcp-capability-parity.md`.
- Live BigQuery annotation smoke for table and column descriptions.
- Live failed-run evidence smoke proving that native BigQuery errors persist to run evidence.
- Write modes: `append`, `overwrite` and explicit-column `upsert` render paths.
- BigQuery run, quality, schema, annotation and governance evidence table DDL.
- Neutral OpenLineage control-table evidence for executed load/write smoke operations.
- Query-only operational cost reports over run evidence; estimates require operator-supplied rates.
- Deterministic deployment manifests that document single-contract BigQuery apply order.
- Dry-run project deployment planning that renders per-contract BigQuery bundles, a project deployment manifest, a Google Workflows source plan, execution plan and evidence-readback plan.
- Dry-run and executed smoke planning for BigQuery contracts; real execution requires `--execute`.
- Sequential project smoke execution through the same contract-only BigQuery runtime; real execution requires `--execute`.
- Run, quality and annotation evidence inserts during executed smoke tests.
- Lineage evidence inserts during executed load/write smoke tests.

Review-required areas:

- `historical` and `snapshot_reconcile_soft_delete`; these are excluded from the first stable GCP surface until cross-adapter production parity contracts pass. `hash_diff_upsert` production parity is accepted but remains review-gated by default until the stable execution surface is explicitly widened.
- Direct raw Iceberg path execution without registration, Delta/Delta Sharing, JDBC dialects, inline authenticated REST/HTTP credentials and streaming sources. Public/no-auth bounded REST/HTTP and placeholder-backed authenticated REST/HTTP sources are materialized through core readers plus BigQuery local load jobs.
- Idempotent upsert replay remains open until broader platform parity runs pass; executable `MERGE` rendering requires `select_columns` or `source.read.columns`.
- Automatic BigQuery type widening or type mutation.
- Tag-based masking, policy-tag-backed masking, governance auto-repair/delete and overwrite-retention governance.
- Mutating IAM/governance repair beyond non-mutating readback and comparison.
- Automatic Dataplex/Data Catalog lineage and Knowledge Catalog aspect emission during every contract run.
- Cloud Run Jobs, Composer DAGs and scheduled-query deployment runners; Google Workflows is the certified deployment runner for the stable BigQuery batch surface.

Runtime smoke execution uses the `bq` CLI when available, or the official
BigQuery Python client:

```bash
pip install "contractforge-gcp[runtime]"
contractforge-gcp smoke contract.ingestion.yaml --environment environment.yaml --execute --runtime auto
```
