# Usage Guide

This guide explains how a team uses ContractForge Core with one or more platform adapters.

## Workflow

The recommended workflow is:

```text
write contract
  -> validate with core
  -> normalize to semantic model
  -> match against adapter capabilities
  -> inspect planning status
  -> render adapter artifacts
  -> execute through adapter-owned runtime path when supported
  -> persist evidence through adapter-owned storage
```

Core owns validation, semantic intent and planning. Adapters own native artifacts, runtime execution and persistence details.

## Planning Statuses

| Status | Meaning |
| --- | --- |
| `SUPPORTED` | The adapter can preserve the declared semantics. |
| `SUPPORTED_WITH_WARNINGS` | The adapter can run the contract, but there are non-breaking caveats. |
| `REVIEW_REQUIRED` | A human/platform design decision is required before execution. |
| `UNSUPPORTED` | Required semantics cannot be preserved. |

Adapters must not turn `REVIEW_REQUIRED` into execution unless the caller explicitly accepts that risk.

## Core CLI

The core `contractforge` CLI is for platform-neutral work:

- contract validation;
- bundle composition;
- source portability inspection;
- generic schema/spec information;
- semantic planning where no platform runtime is needed.

Adapter CLIs are separate. For example, `contractforge-databricks` owns Databricks rendering, dashboard, governance preview and adapter-specific utilities.

AWS uses `contractforge-aws` for render, S3 artifact publication, Glue job
registration and optional Glue job run helpers. The shortcut command
`contractforge-aws deploy <contract> --environment <environment.yaml>` renders,
publishes and creates or updates the Glue job in one adapter-owned flow.

## Project Scheduling

Use `project.yaml.defaults` for values that are true for the whole project and
should not be repeated in every contract:

```yaml
defaults:
  catalog: workspace
  schemas:
    bronze: cf_bronze
    silver: cf_silver
    gold: cf_gold
    tmp: cf_tmp
  schema_policy: additive_only
  operations:
    technical_owner: data-platform
    criticality: medium
    expected_frequency: daily
  annotations:
    table:
      tags:
        domain: customer_analytics
```

The core applies these defaults when loading split bundles and records every
added value in `defaults.decisions[]`. Existing contract values always win. Use
`contractforge resolve-bundle <path>` to inspect the effective contract before
adapter deployment.

Use `defaults.adapters.<adapter>` for catalog/schema bindings that differ by
platform. Contracts under `contracts/databricks/...`, `contracts/aws/...`,
`contracts/snowflake/...`, `contracts/fabric/...` or `contracts/gcp/...` receive
the matching adapter defaults after the shared defaults.

Use `project.yaml` for job wiring that spans multiple contracts:

```yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false
  max_concurrent_runs: 1
  queue: true
  adapters:
    databricks:
      pause_status: PAUSED
    aws:
      state: DISABLED

execution_order:
  - name: bronze_orders
    contracts:
      databricks: contracts/databricks/bronze_orders.ingestion.yaml
      aws: contracts/aws/bronze_orders.ingestion.yaml
  - name: silver_orders
    depends_on: [bronze_orders]
    contracts:
      databricks: contracts/databricks/silver_orders.ingestion.yaml
      aws: contracts/aws/silver_orders.ingestion.yaml
```

`execution_order[].depends_on` is portable project metadata. Databricks maps it
to job task dependencies in a Databricks Asset Bundle. AWS can map the same
dependency graph to Step Functions and EventBridge Scheduler. `schedule.cron`
and `schedule.timezone` are core-owned project metadata. Adapters render native
scheduler syntax from the same schedule intent. The ingestion contract remains
unchanged.

See [Project YAML](project-yaml.md) for the full field reference, reusable
connection pattern, adapter deployment blocks and command examples.

## Core-Only Use

Use core-only when you want to:

- validate contract syntax and semantics;
- classify source portability;
- evaluate a contract against synthetic or stored platform capabilities;
- build tooling around review workflows;
- develop a new adapter.

Core-only use never executes Spark, Delta, boto3, Fabric or Snowflake code.

## Core Plus Adapter Use

Use core plus adapter when you want native output:

- Databricks SQL, Unity Catalog SQL, Delta DDL and Asset Bundle YAML;
- AWS Glue/Iceberg artifacts, review reports, evidence DDL and optional runtime helper flows through `contractforge-aws`;
- Fabric pipeline or Lakehouse artifacts in a future Fabric adapter;
- Snowflake SQL/tasks/policies in a future Snowflake adapter.

The adapter may expose both dry rendering and runtime execution APIs. Runtime execution should accept injected clients or runners instead of relying on hidden global sessions.

For AWS, contracts are interpreted before deployment. Generated Glue jobs run
native Python/Spark artifacts from S3; they do not parse the YAML contract at
runtime.

## Split Contracts

ContractForge keeps ownership clear by splitting contracts:

| File | Owner | Purpose |
| --- | --- | --- |
| `*.ingestion.yaml` | Data engineering | Source, target, write mode, schema policy, quality, watermarks and transforms. |
| `*.annotations.yaml` | Data governance/catalog owners | Descriptions, tags, aliases, PII and lifecycle metadata. |
| `*.operations.yaml` | Platform/operations teams | Owners, criticality, SLA, runbook and support metadata. |
| `*.access.yaml` | Security/data governance | Grants, row filters, column masks and drift policy. |
| `*.environment.yaml` | Platform team | Adapter, evidence location, runtime/deployment hints and adapter parameters. |

The `environment` contract must not contain ingestion semantics. It selects where and how a contract will run.

Use `source.ref` or SQL `{{ table_ref:layer.table }}` placeholders when a
downstream contract reads a table produced by another ContractForge contract.
The core keeps this as a neutral `layer.table` reference and adapters render
the platform-qualified name.

## Write Modes

Portable write modes are semantic, not implementation names:

- `append`
- `overwrite`
- `upsert`
- `hash_diff_upsert`
- `historical`
- `snapshot_reconcile_soft_delete`
- `custom:<name>`

Adapters decide how to implement them. A platform may support a mode directly, support it with warnings, require review or reject it.

## Evidence

Evidence is a core concept. Storage is adapter-owned.

Examples:

- Databricks: Delta control tables.
- AWS: Iceberg/Glue tables or S3 audit artifacts.
- Fabric: Lakehouse tables.
- Snowflake: audit tables.
- GCP: BigQuery evidence tables.

Do not describe evidence in core docs as "Delta control tables" unless the text is specifically about the Databricks adapter.

## Deployment Versioning

ContractForge tracks deployments in the core-owned
`ctrl_deployment_versions` ledger. The core defines the columns and hash
rules; each adapter creates and writes the table in its own platform-native
storage.

One deploy command creates one unique `deployment_id`. Every contract step or
native artifact written by that deploy creates a row with content-derived
hashes:

| Field | Purpose |
| --- | --- |
| `deployment_hash` | Identifies the exact deploy row after stable normalization. |
| `contract_hash` | Identifies the contract payload deployed for the step. |
| `environment_hash` | Identifies the resolved environment payload. |
| `manifest_hash` | Identifies the adapter manifest payload used to render native artifacts. |

This makes repeated deploys auditable across adapters without forcing the core
to know Databricks Delta, AWS Iceberg, Snowflake SQL, Fabric Lakehouse or
BigQuery storage syntax.
