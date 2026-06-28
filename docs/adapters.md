# Adapters

Adapters are the platform implementation layer for ContractForge Core.

The core defines what the contract means. Adapters decide whether a platform can preserve that meaning and how to render or execute native artifacts.

## Adapter Responsibilities

An adapter owns:

- capability declaration;
- platform-specific planning warnings and blockers;
- native artifact rendering;
- runtime execution, when supported;
- evidence persistence;
- deployment ledger DDL and inserts in the platform-native control-table store;
- platform-specific CLI commands;
- canonical adapter CLI commands documented in [Adapter CLI](cli.md);
- platform documentation.

The core owns:

- contract vocabulary;
- semantic normalization;
- capability matching;
- abstract execution plans;
- neutral evidence model;
- deployment ledger schema, stable hashing rules and deployment row shape;
- public adapter protocol.

## Required Adapter Shape

```python
from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import PlanningResult, plan_contract
from contractforge_core.semantic import SemanticContract


class MyAdapter:
    name = "my-platform"

    def capabilities(self) -> PlatformCapabilities:
        ...

    def plan(self, contract: SemanticContract) -> PlanningResult:
        return plan_contract(contract, self.capabilities())

    def render_contract(self, contract: SemanticContract) -> RenderedArtifacts:
        ...
```

Production adapters usually add higher-level convenience functions, but those functions remain adapter-owned.

## Packaging

Each adapter gets its own distribution:

```text
contractforge-core
contractforge-databricks
contractforge-aws
contractforge-fabric
contractforge-gcp
contractforge-snowflake
```

Dependency direction:

```text
adapter -> contractforge-core
contractforge-core -> no adapter dependency
```

See [publication packaging](specs/publication-packaging.md).

## Package Delivery By Runtime

Every adapter is published as an independent PyPI package and wheel. Runtime
delivery is still platform-specific:

| Adapter | PyPI package | Runtime package delivery |
| --- | --- | --- |
| Databricks | `contractforge-core` + `contractforge-databricks` | Install from PyPI in the Databricks job, cluster, notebook environment or workspace package path when outbound access is allowed. Attach uploaded wheels when the workspace must use pinned CI artifacts or cannot reach PyPI. ZIP is not the normal Databricks path. |
| AWS Glue / Iceberg | `contractforge-core` + `contractforge-aws` | Use PyPI locally or in CI for deployment tooling. Glue jobs should normally receive S3-hosted wheels for the core and AWS adapter; public PyPI is only appropriate when the job has controlled outbound package access. ZIP is not the stable Glue path. |
| Snowflake | `contractforge-core` + `contractforge-snowflake` | Use PyPI locally or in CI for deployment tooling. SQL/task graph artifacts run natively in Snowflake. Hosted Snowpark procedures use staged ZIP imports built from the core and adapter libraries; authenticated REST sources bind Snowflake secrets through `parameters.snowflake.secrets`. |
| Fabric | `contractforge-core` + `contractforge-fabric` | Install from PyPI in the Fabric notebook/runtime environment when available. Attach or install wheels when PyPI is unavailable or the workspace must use CI-produced artifacts. ZIP is not the normal Fabric path. |
| GCP BigQuery / BigLake | `contractforge-core` + `contractforge-gcp` | Use PyPI where adapter commands run locally, in CI or in runner-side tooling. BigQuery SQL, load jobs and Workflows execute native artifacts; wheels are useful for private runners or pinned CI artifacts. ZIP is not part of the stable BigQuery/Workflows path. |

## Capability Rules

Capabilities must be conservative.

Do not set a capability to true because the platform has something similar. Set it to true only when the adapter can preserve the ContractForge semantics.

Examples:

- current-state requires merge/upsert semantics.
- historical requires merge plus history semantics.
- Snapshot soft delete requires complete-source reconciliation.
- Row filters require native row access controls or a reviewed equivalent.
- Column masks require native masking or a reviewed equivalent.

## Adapter Documentation

Every production adapter should document:

1. supported contract sections;
2. source support;
3. write-mode mapping;
4. governance/access mapping;
5. evidence persistence;
6. runtime prerequisites;
7. packaging and installation;
8. unsupported semantics;
9. review-required semantics;
10. examples for supported and review-required plans.

The full adapter contract is in [adapter authoring](specs/adapter-authoring.md).

## Current Adapters

| Adapter | Package | Current state | Primary runtime path |
| --- | --- | --- | --- |
| Databricks | `contractforge-databricks` | Stable supported reference surface | Direct workspace execution, Databricks SQL/Python artifacts, Databricks Asset Bundle deploy/run automation and checkpointed available-now contract runtime for the documented `databricks_serverless_delta` surface. |
| AWS | `contractforge-aws` | Stable supported surface | Render/publish artifacts to S3, create or update Glue jobs, run Glue Spark against Iceberg tables and write Iceberg evidence tables for the documented `aws_glue_iceberg` surface. |
| Fabric | `contractforge-fabric` | Stable supported surface | Fabric REST preflight, generated Notebook deployment/run, deploy-only project manifests, deployment pipeline stage-to-stage Notebook promotion, Lakehouse Delta writes, Lakehouse text/ORC/Avro/XML files, internal OneLake shortcut reads, public/no-auth REST, public/no-auth HTTP JSON/CSV/text, authenticated REST Basic/bearer/API-key/OAuth, authenticated HTTP JSON Basic/bearer/API-key, authenticated HTTP CSV Basic/bearer/API-key, endpoint-enforced HTTP text Basic/bearer/API-key, SQL Server JDBC, PostgreSQL JDBC, public and direct private Azure Blob CSV, external Azure Blob, ADLS Gen2, Google Cloud Storage, Amazon S3 and S3-compatible shortcut reads, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads, bounded Confluent Kafka, Confluent Kafka available-now, Event Hubs Kafka-compatible available-now, core write modes, control-table evidence, explicit workspace role assignment, sensitivity-label and OneLake data access role apply helpers including live row/column policy apply for the documented `fabric_lakehouse` surface. Private-network shortcuts, managed identity/OAuth object-storage access, Delta Sharing, direct-catalog Iceberg, native Fabric Real-Time/Eventstream and Data Factory/Git promotion are excluded from stable-final unless separately certified. See [Fabric adapter guide](adapters/fabric.md). |
| Snowflake | `contractforge-snowflake` | Stable supported surface | SQL warehouse runtime, hosted Snowpark procedure library runner with staged ZIP imports, table/SQL/bounded REST/staged-file sources, Snowflake-scoped secret aliases for authenticated REST, append/overwrite/upsert/hash-diff writes, quality, schema policy, governance, evidence/control tables, lineage, cost reconciliation and live task graph project deployment for the documented `snowflake_sql_warehouse` surface. See [Snowflake adapter guide](adapters/snowflake.md). |
| GCP | `contractforge-gcp` | Stable supported surface | BigQuery table/view/SQL sources, GCS CSV/NDJSON/Parquet/Avro/ORC load jobs, public/no-auth bounded REST/HTTP JSON/CSV materialization and declared `http_file` Avro/ORC/Parquet materialization through core readers plus BigQuery local load jobs, authenticated REST/HTTP Secret Manager review/runtime resolution for `{{ secret:scope/key }}` placeholders, registered BigLake Iceberg table reads, raw Iceberg BigLake registration command/readback, append/overwrite/explicit-column upsert, advanced write-mode review artifacts with accepted cross-adapter `hash_diff_upsert` production parity, SQL quality checks, run/quality/schema/annotation/governance/failed-run evidence DDL, bronze-to-gold execution, row access policies, direct column data masking, policy-tag column access, BigQuery descriptions, schema-policy planning plus validated table/SQL/GCS-source runtime enforcement, Dataplex data-quality create and execution/readback planning, explicit Dataplex lineage/aspect execution/readback command surface, governance ledger/reconciliation planning, non-mutating governance reconciliation readback, governance evidence write/readback for declared governance intent and a certified Google Workflows deployment runner for the documented `gcp_bigquery` surface. Workflows evidence covers deploy/execute, command-path readback, runner-side run/quality/schema evidence, quality failed-row semantics, execution-scoped evidence ids, workflow cleanup, write-failure evidence, target/evidence cleanup/reset and repeated full-project rerun execution/readback. Streaming, historical/snapshot advanced write modes, automatic BigQuery type widening/mutation, non-Workflows deployment runners, automatic native Dataplex lineage/aspect emission during every contract run, direct raw Iceberg path execution without registration, JDBC/Delta Sharing, inline authenticated REST/HTTP credentials, governance auto-repair/delete and overwrite-retention certification are excluded from stable-final unless separately certified. See [GCP adapter guide](adapters/gcp.md). |

The Databricks adapter remains the reference implementation, and now exposes a
machine-readable stable-surface report through
`contractforge-databricks stabilization-report --strict-final`. Its scoped
`STABLE_SUPPORTED_SURFACE` claim and evidence are documented in the
[Databricks adapter guide](databricks.md) and
[Databricks stable-surface evidence](reports/databricks-stable-surface-evidence.json).
This is separate from the broader Databricks 1.0 GA gate.

The AWS adapter intentionally does not make the core import `boto3`. Optional
runtime helpers import AWS SDKs lazily or accept caller-provided clients. Its
stable supported surface and remaining production-certification boundaries are
defined in [AWS stable-surface criteria](specs/aws-ga-criteria.md) and
[AWS stabilization matrix](specs/aws-stabilization-matrix.md).
The Fabric adapter stable claim is intentionally scoped to the notebook-first
Lakehouse surface. Its validated subset and explicit stable-final exclusions are documented
in the [Fabric adapter guide](adapters/fabric.md),
[Fabric USGS REST E2E smoke](reports/fabric-usgs-rest-e2e-smoke.json),
[Fabric stable-surface evidence](reports/fabric-stable-surface-evidence.json),
[Fabric source-expansion stable-scope decision](reports/fabric-source-expansion-stable-scope-decision.json),
[Fabric project deploy-only smoke](reports/fabric-project-deploy-smoke.json)
and [Fabric OneLake data access role smoke](reports/fabric-onelake-data-access-role-smoke.json),
row/column policy evidence in [Fabric OneLake row/column policy smoke](reports/fabric-onelake-row-column-policy-smoke.json),
plus read-only [Fabric deployment pipeline probe](reports/fabric-deployment-pipeline-read-probe.json)
and [Fabric deployment pipeline lifecycle smoke](reports/fabric-deployment-pipeline-lifecycle-smoke.json),
with live stage promotion in [Fabric deployment pipeline stage promotion smoke](reports/fabric-deployment-pipeline-stage-promotion-smoke.json),
and shortcut evidence for [external Azure Blob](reports/fabric-external-azure-blob-shortcut-source-smoke.json),
[ADLS Gen2](reports/fabric-adls-shortcut-source-smoke.json),
[GCS](reports/fabric-gcs-shortcut-source-smoke.json)
and [external Amazon S3](reports/fabric-external-s3-shortcut-source-smoke.json),
plus [S3-compatible](reports/fabric-s3-compatible-shortcut-source-smoke.json)
shortcut evidence and Iceberg table shortcut evidence for [Amazon S3](reports/fabric-iceberg-table-shortcut-source-smoke.json),
[ADLS Gen2](reports/fabric-adls-iceberg-table-shortcut-source-smoke.json)
and [GCS](reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json).
The full Snowflake parity status is documented in
[Snowflake capability and evidence parity](specs/snowflake-capability-parity.md),
the [Snowflake adapter operations guide](adapters/snowflake.md) and the
[Snowflake stabilization matrix](specs/snowflake-stabilization-matrix.md).
Its stable supported surface and remaining production-certification boundaries
are defined in [Snowflake stable-surface criteria](specs/snowflake-ga-criteria.md)
and [Snowflake stable-surface waiver registry](specs/snowflake-ga-waivers.md).
The GCP adapter stable claim is scoped to the BigQuery batch surface. Its
validated subset and explicit stable-final exclusions are documented in the
[GCP adapter guide](adapters/gcp.md), [GCP capability parity](specs/gcp-capability-parity.md)
and [GCP stable-surface evidence](reports/gcp-stable-surface-evidence.json).

## Artifact And Deployment Pattern

Adapters may support different degrees of execution:

| Pattern | Example | Notes |
| --- | --- | --- |
| Render-only | Review Markdown, SQL, Python, Terraform, CloudFormation | Safe for CI and pull-request review. |
| Publish artifacts | AWS S3 artifact URI, Databricks workspace/DAB sync path | Moves rendered files to platform storage without running data movement. |
| Register runtime job | AWS Glue job definition, Databricks job/DAB | Creates or updates native jobs. |
| Execute | Databricks `ingest_databricks_bundle`, AWS Glue job run | Adapter-owned runtime path; core remains execution-free. |

Adapter command names and common flags are standardized in [Adapter CLI](cli.md).
Adapter-specific deployment options are allowed only under that canonical
command vocabulary. For example, Databricks may invoke Asset Bundles, AWS may
register Glue jobs and Step Functions, Fabric may submit generated notebooks,
GCP may execute BigQuery smoke plans and Snowflake may publish staged procedure
artifacts. None of those platform actions change the ingestion contract
semantics.

Use `project.yaml.execution_order[].depends_on` for portable project task
dependencies. Use top-level `project.yaml.schedule` for core-owned schedule
intent such as cron, timezone, queueing and max concurrent runs. Adapter blocks
under `schedule.adapters.<adapter>` should contain only platform-specific
overrides. The ingestion contract still describes dataset semantics; project
scheduling describes how native jobs are wired.

## Deployment Ledger

Deployment versioning is a shared control-plane contract. The core owns the
`ctrl_deployment_versions` schema and the deterministic hash rules; adapters
own where that table lives and how it is created or written on each platform.

Each deploy command must create one unique `deployment_id`. Each deployed
contract step or native artifact creates one ledger row with:

- `deployment_step_id`: deterministic id for the step inside the deployment;
- `deployment_hash`: stable hash of the deployment row, excluding mutable
  result metadata;
- `contract_hash`: stable hash of the contract payload used for that step;
- `environment_hash`: stable hash of the resolved environment payload;
- `manifest_hash`: stable hash of the adapter deployment manifest payload.

The adapter persistence targets are native:

| Adapter | Ledger storage |
| --- | --- |
| Databricks | Delta table in the configured evidence catalog/schema. |
| AWS | Iceberg table registered in Glue Catalog. |
| Snowflake | SQL table in the configured evidence database/schema. |
| Fabric | Lakehouse Delta table in the configured evidence schema. |
| GCP | BigQuery table in the configured evidence dataset. |

The ledger does not change ingestion semantics. It records which contract
payload, environment payload, platform artifact and runtime package versions
were deployed in a specific deploy command, so repeated deploys can be compared
without relying on file names or platform timestamps.
