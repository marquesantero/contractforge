# contractforge-fabric

`contractforge-fabric` is the Microsoft Fabric adapter package for
ContractForge.

The stable supported surface is intentionally conservative. It plans contracts
against a Fabric Lakehouse target, renders review artifacts, publishes a
machine-readable source-support catalog and documents the runtime boundaries for
the notebook-first Fabric claim.

The public planning/rendering flow remains conservative. The package also
includes Fabric REST primitives and smoke commands for workspace preflight,
Notebook deployment, Notebook run submission and terminal job classification.
A first public REST/GeoJSON bronze-to-gold workflow plus HTTP JSON,
authenticated REST Basic/bearer/API-key/OAuth, authenticated HTTP JSON
Basic/bearer/API-key, authenticated HTTP CSV Basic/bearer/API-key,
Lakehouse text/ORC/Avro/XML files, internal OneLake shortcut reads, public HTTP CSV/text, endpoint-enforced HTTP text Basic/bearer/API-key, SQL Server JDBC, PostgreSQL
JDBC, Azure Blob, external Amazon S3 and S3-compatible shortcuts, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcuts, Confluent Kafka and Event Hubs Kafka-compatible source-expansion smokes, including direct private Azure Blob with Key Vault
credential resolution and available-now catch-up, have been validated on
Fabric. Data Factory pipelines, Git integration and non-notebook-first source
families remain outside the stable-final claim unless separately certified.

## Install

```bash
pip install contractforge-core contractforge-fabric
```

## Use

```python
from contractforge_fabric import plan_fabric_contract, render_fabric_contract

contract = {
    "source": {"type": "parquet", "path": "Files/orders"},
    "target": {"catalog": "workspace", "schema": "bronze", "table": "orders"},
    "mode": "overwrite",
}

planning = plan_fabric_contract(contract)
artifacts = render_fabric_contract(contract)
```

CLI:

```bash
contractforge-fabric plan contracts/orders.ingestion.yaml
contractforge-fabric render contracts/orders.ingestion.yaml
contractforge-fabric sources
contractforge-fabric stabilization-report
contractforge-fabric preflight --environment fabric.env.yaml --require-lakehouse --check-spark-settings
contractforge-fabric preflight --environment fabric.env.yaml --require-notebook --check-notebook-jobs
contractforge-fabric smoke contracts/orders.ingestion.yaml --environment fabric.env.yaml --no-wait
contractforge-fabric smoke-project examples/real-world/usgs-earthquake-rest-medallion/project.yaml --environment-key fabric
contractforge-fabric smoke-project examples/stable-surface/fabric/project.yaml --environment-key fabric --start-at quality_abort_failure
```

Read-only Fabric REST discovery can be done from Python with an Azure CLI token:

```python
from contractforge_fabric.runtime import AzureCliFabricTokenProvider, FabricRestClient

client = FabricRestClient(
    workspace_id="bootstrap",
    token_provider=AzureCliFabricTokenProvider(tenant_id="00000000-0000-0000-0000-000000000000"),
)
workspaces = client.list_workspaces()
```

The contract smoke workflow combines preflight, Notebook deployment, run
submission and terminal job classification:

```python
from contractforge_fabric.runtime import run_fabric_contract_smoke

result = run_fabric_contract_smoke(contract, environment)
evidence = result.to_dict()
```

Project smoke runs the Fabric entries from a ContractForge `project.yaml`
`execution_order` sequentially, using split contract bundles when present:

```python
from contractforge_fabric.runtime import run_fabric_project_smoke

result = run_fabric_project_smoke("examples/real-world/usgs-earthquake-rest-medallion/project.yaml")
evidence = result.to_dict()
```

## Current scope

- Subtarget: `fabric_lakehouse`.
- Runtime status: preflight and Notebook smoke workflow available; one public
  REST/GeoJSON bronze-to-gold path, HTTP JSON, authenticated REST
  Basic/bearer/API-key/OAuth, authenticated HTTP JSON Basic/bearer/API-key,
  Lakehouse text/ORC/Avro/XML files, internal OneLake shortcut reads, public HTTP CSV/text, authenticated HTTP CSV Basic/bearer/API-key, endpoint-enforced HTTP text
  Basic/bearer/API-key, SQL Server JDBC, PostgreSQL JDBC, Azure Blob, external Amazon S3 and S3-compatible shortcuts, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcuts, bounded Confluent Kafka,
  Confluent Kafka available-now and Event Hubs Kafka-compatible available-now source-expansion paths have live
  Fabric evidence, including direct private Azure Blob with Key Vault-backed
  storage account key resolution, and a SQL-source stable-surface smoke suite has live Fabric
  evidence for the core write modes and failure-path control-table evidence.
- REST primitives: Azure CLI token provider, workspace discovery, Notebook
  create/update/get-definition request shapes, async definition export result
  polling, Lakehouse creation, capacity listing, Spark pool/settings
  management, item job-instance listing and LRO polling.
- Capacity note: small trial capacities can fail Notebook public API runs with
  `TooManyRequestsForCapacity` when the default Starter Pool uses Medium nodes.
  In the validated workspace, creating a `Small` single-node custom Spark pool
  and setting it as the workspace default allowed the smoke notebook to run.
- Spark settings preflight: `contractforge-fabric preflight
  --check-spark-settings` resolves the capacity SKU, current default Spark pool
  and Starter Pool shape, then warns when FTL4 is paired with Starter Pool
  Medium.
- Notebook job preflight: `contractforge-fabric preflight
  --check-notebook-jobs` resolves the configured Notebook and lists recent job
  instances, warning when active runs can consume Spark capacity before a smoke
  run starts.
- Smoke workflow: preflight, Notebook deployment, run submission, job wait and
  normalized execution outcome, owned by the `smoke` package.
- Project smoke workflow: reads `project.yaml`, resolves the Fabric environment
  and executes each Fabric contract in `execution_order` sequentially, producing
  per-step JSON evidence for bronze-to-gold validation. Use `--start-at` to
  resume long project smoke suites from a named step.
- Notebook deployment: generated definitions are fingerprinted before update;
  unchanged existing notebooks are skipped instead of rewritten. Existing
  notebooks are not updated unless `update_existing=True`, and smoke execution
  stops if Fabric cannot read the current definition before an update.
- Project deployment: `contractforge-fabric deploy-project` renders a
  deterministic deploy-only manifest and can create or update all generated
  Notebook item definitions in project order without submitting runs. This is
  the adapter-owned deployment path. It also renders the shared
  `ctrl_deployment_versions` ledger DDL and per-step inserts, with one unique
  `deployment_id` per deploy command and content hashes for the contract,
  environment, manifest and deployment row. Fabric deployment pipelines have live
  read, lifecycle and stage-to-stage Notebook promotion evidence with cleanup.
  Fabric Git integration and Data Factory lifecycle promotion remain outside
  the notebook-first stable scope.
- Write modes: Notebook rendering for `append`, `overwrite`, `upsert`,
  `hash_diff_upsert`, `historical` and `snapshot_reconcile_soft_delete`, owned by the
  `write_modes` package. Hash-diff and snapshot rendering compute deterministic
  `row_hash` values; historical mode expires current rows and inserts new
  versions, while snapshot mode reconciles a declared complete source and
  soft-deletes missing active rows. The SQL-source stable-surface suite has live
  Fabric evidence for these modes; broader connector parity remains outside
  the stable-final claim unless separately certified.
- Evidence DDL/runtime: review bundle renders Fabric Lakehouse Delta DDL for the
  core ContractForge evidence and state tables. Generated notebooks now record
  run, error, source metadata, schema-policy, observed-schema, operations
  metadata, review-only annotation/access intent and best-effort Spark explain
  evidence rows to the shared control-table schema. Notebooks bootstrap the
  evidence and state Delta tables by default before execution; set
  `extensions.fabric.bootstrap_evidence_tables: false` to skip DDL in managed
  environments. Project deployment uses the same control-table model for
  deployment versioning through `ctrl_deployment_versions`.
- Schema policy: generated notebooks validate `strict`, `additive_only` and
  `permissive` policy semantics before writes when the target schema is readable
  through Spark. `extensions.fabric.allow_type_widening` enables compatible
  widening checks. If Fabric cannot expose the target schema, the notebook
  records a schema lookup warning instead of comparing unknown columns.
- Transforms: generated notebooks render portable Spark transforms for
  `transform.cast`, `transform.standardize`, `transform.derive`,
  `transform.composite_keys` and deterministic `transform.deduplicate` ordering.
  Non-portable deduplicate order expressions remain review-only.
- Shape: generated notebooks render portable Spark shape steps for
  `shape.parse_json`, single-step `shape.arrays` with `explode` or
  `explode_outer`, `shape.columns` and `shape.flatten`. Cartesian/zip-array
  semantics remain review-only until validated on Fabric.
- Lakehouse file sources: generated notebooks can read `csv`, `json`, `jsonl`,
  `ndjson`, `parquet`, `delta`, `text`, `orc`, `avro` and `xml` files from
  Lakehouse `Files` paths. The `text` reader materializes Spark's standard
  single `value` column; ORC, Avro and XML readers have live Fabric
  source-expansion evidence, with XML using contract-declared parser options
  such as `rowTag`.
- Public bounded HTTP/REST sources: generated notebooks can call the shared
  ContractForge core readers for public/no-auth `http_json`, `http_csv`,
  `http_text`, `http_file` and `rest_api` sources. Public/no-auth `rest_api`,
  `http_json`, `http_csv` and `http_text` now have live Fabric E2E evidence. Authenticated REST Basic,
  bearer token, API-key and OAuth plus authenticated `http_json` and
  `http_csv` Basic, bearer token and API-key with
  `{{ secret:scope/key }}` placeholders have live Fabric E2E evidence through
  Azure Key Vault runtime resolution. Endpoint-enforced Basic, bearer and
  API-key auth are validated for `http_text`. OAuth is not currently part of
  the HTTP-file source vocabulary.
- JDBC: generated notebooks can read Azure SQL/SQL Server and PostgreSQL
  sources through Spark JDBC when Basic auth credentials use `{{ secret:scope/key }}`
  placeholders and the Fabric environment maps those scopes to Azure Key Vault.
  SQL Server JDBC and PostgreSQL JDBC now have live Fabric E2E evidence; other
  JDBC dialects remain review-required until their drivers and network paths
  are validated.
- Azure Blob object storage: generated notebooks can read `azure_blob` CSV
  sources when `extensions.fabric.source_runtime_path` points to a Fabric
  Spark-readable object-store URI, Lakehouse file path or reviewed shortcut
  path. Public Azure Blob CSV and direct private Azure Blob CSV with
  `extensions.fabric.storage_account_key_secret` Key Vault placeholder
  resolution now have live Fabric E2E evidence; internal OneLake shortcut reads
  and external Azure Blob shortcut reads through a Fabric AzureBlobs cloud
  connection now have live evidence. External ADLS Gen2 shortcut reads through
  a Fabric AzureDataLakeStorage cloud connection with Key credentials now have
  live evidence. External Google Cloud Storage shortcut reads through a Fabric
  GoogleCloudStorage cloud connection with Basic HMAC credentials now have live
  evidence. External Amazon S3 shortcut reads through a Fabric AmazonS3
  cloud connection with Basic IAM user credentials also have live evidence.
  External S3-compatible shortcut reads through a Fabric AmazonS3Compatible
  cloud connection with Basic IAM user credentials now have live evidence.
  ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads
  through Fabric Iceberg-to-Delta virtualization also have live evidence for
  `source.type: iceberg_table`. ADLS managed identity/OAuth,
  private-network shortcut variants, Delta Sharing and direct-catalog Iceberg
  variants remain review-required and are excluded from stable-final until
  source-specific evidence exists.
- Kafka streams: generated notebooks can read bounded Confluent Kafka with
  Spark's batch Kafka reader and checkpointed Confluent Kafka available-now
  catch-up with Spark Structured Streaming `trigger(availableNow=True)`.
  Available-now materializes the stream to Delta under the declared checkpoint
  path, then reads it back into the standard quality/write/evidence path.
  Azure Event Hubs through the Kafka-compatible endpoint now has live
  available-now evidence with the same Spark Kafka reader shape. Native
  `eventhubs_available_now` and Fabric Real-Time/Eventstream routing remain
  review-required until source-specific evidence exists.
- Source review artifacts: every rendered contract includes redacted
  `.fabric.source_review.json` and `.fabric.source_review.md` artifacts with
  the selected Fabric runtime path, source-specific prerequisites and
  graduation gates. These artifacts do not make review-only sources executable.
- Project setup: `smoke-project` can run declarative
  `fabric_setup.shortcuts` entries before contract execution. This is intended
  for native Fabric shortcut creation, using environment-resolved connection IDs
  such as `{{ parameter:fabric.connections.azure_blob_shortcut_connection_id }}`
  or `{{ parameter:fabric.connections.amazon_s3_shortcut_connection_id }}`.
  Data loading still happens only through the declared contracts.
- State tables: state/lock table naming and DDL are owned by the `state`
  package. Generated notebooks append successful-run state rows, including a
  watermark candidate when a single watermark column is declared. Generated
  notebooks also render opt-in Delta lock acquire/release logic from
  `extensions.fabric.lock_enabled`; real concurrent execution semantics still
  require capacity-stable Fabric validation.
- Quality gates: notebook rendering for core Spark quality checks is owned by
  the `quality` package; generated notebooks write per-rule quality evidence
  rows to `ctrl_ingestion_quality` and failed-row quarantine evidence for
  row-predicate quarantine rules.
- Lineage: OpenLineage-compatible event rendering is owned by the `lineage`
  package; generated notebooks write runtime lineage rows to
  `ctrl_ingestion_lineage`.
- Operations: ownership, SLA and alert-intent metadata rendering is owned by
  the `operations` package. Generated notebooks write declared operations
  metadata to `ctrl_ingestion_operations`; live Fabric monitoring integration is
  still pending.
- Annotations: table and column description/tag/PII/deprecation metadata render
  as review-only catalog plans and evidence SQL through the `annotations`
  package. Generated notebooks record validated review evidence to
  `ctrl_ingestion_annotations`, but do not apply Fabric catalog metadata.
- Access: grants, row filters and column masks render as review governance
  plans and access evidence SQL through the `access` package. Explicit
  `extensions.fabric.access_apply` declarations can apply Fabric workspace role
  assignments and item sensitivity labels when the contract supplies native
  Fabric IDs. Table grants, row filters, column masks and broader
  Fabric/Purview policy application remain review-only until those semantics
  are live-certified. Generated notebooks record validated review evidence to
  `ctrl_ingestion_access`.
- Native concepts: Fabric Workspace, Lakehouse, Warehouse, OneLake, shortcuts,
  notebooks and Data Factory pipelines.
- Evidence store target: Fabric Lakehouse Delta tables; DDL rendering exists,
  and generated notebooks include idempotent evidence/state table bootstrap plus
  runtime evidence writes for runs, errors, source metadata, schema changes,
  operations, annotation/access review intent, quality, quarantine and lineage.
  The stable-surface smoke suite validates run, error, quality, schema, source
  metadata, lineage, explain, state, operations, annotations and access review
  evidence through a final control-table probe. Public/no-auth REST and HTTP
  JSON, Key Vault-backed authenticated REST/HTTP subsets, SQL Server JDBC,
  Lakehouse text/ORC/Avro/XML, internal OneLake shortcut reads, external Azure Blob shortcut reads, external Amazon S3 shortcut reads, S3-compatible shortcut reads, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads, PostgreSQL JDBC, public/direct private Azure Blob CSV,
  bounded Confluent Kafka, Confluent Kafka available-now and Event Hubs Kafka-compatible available-now have live source-expansion evidence. Full adapter-wide source parity and Data Factory/Git promotion
  certification are excluded from stable-final unless separately certified.

The adapter returns `REVIEW_REQUIRED` for semantics that need a concrete Fabric
runtime design before execution can be claimed.
