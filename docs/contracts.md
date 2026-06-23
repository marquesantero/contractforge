# Contracts

ContractForge Core keeps the complete ContractForge contract vocabulary while removing Databricks-specific assumptions from the core.

## Contract Sections

| Section | Purpose | Platform-neutral? |
| --- | --- | --- |
| `ingestion` | Source, target, write mode, schema policy, quality, shape, transform, watermarks and execution intent. | Yes. |
| `annotations` | Table/column descriptions, aliases, tags, PII and lifecycle metadata. | Yes, with adapter mapping. |
| `operations` | Owners, support groups, criticality, frequency, SLA and runbook. | Yes. |
| `access` | Grants, row filters, column masks and drift policy. | Partly portable; adapter capability dependent. |
| `environment` | Adapter selection, evidence location, runtime/deployment hints and adapter-owned parameters. | Yes, but adapter parameter blocks are platform-owned. |

## Ingestion Contract

Minimal example:

```yaml
source:
  type: table
  table: main.raw.orders

target:
  catalog: main
  schema: silver
  table: orders

layer: silver
mode: upsert
merge_keys: [order_id]
schema_policy: additive_only

quality_rules:
  not_null: [order_id]
  unique_key: [order_id]
```

When `project.yaml` declares `defaults`, the same intent can be shorter:

```yaml
source:
  type: table
  ref: bronze.orders

target:
  table: orders

layer: silver
mode: upsert
merge_keys: [order_id]
```

The core resolves project defaults before semantic validation. It can fill
target catalog/schema, schema policy, common operations metadata and common
annotation tags. For identity-based write modes, `merge_keys` can also seed
`quality_rules.unique_key` and missing `not_null` checks. The resolver records
every default or inference in a decision ledger; inspect it with:

```bash
contractforge resolve-bundle contracts/silver/orders/orders.ingestion.yaml
```

Defaults reduce YAML volume but do not guess the source, target table, secrets,
access rules or merge keys.

For cross-platform projects, catalog and schema usually live under
`project.yaml.defaults.adapters.<adapter>`. A contract under
`contracts/aws/...` receives AWS defaults; the equivalent contract under
`contracts/databricks/...` receives Databricks defaults. The resolved contract
is what adapters plan and execute.

The write mode is semantic. It does not prescribe Delta MERGE, Iceberg MERGE, Snowflake MERGE or Fabric pipeline behavior. The adapter decides whether equivalent behavior is available.

The ingestion contract may also inherit common connection settings from a reusable YAML file without losing the ability to declare a complete inline source:

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: public.orders
```

The bundle loader resolves `project://` paths from the nearest `project.yaml`
root and deep-merges the connection YAML with dataset-specific fields. Same
bundle relative paths are also allowed when they do not contain `..`. The
adapter receives a concrete resolved source such as `type: connector`, not
`type: connection`.

Downstream medallion contracts can reference outputs from earlier contracts
without hard-coding platform table qualifiers:

```yaml
source:
  type: table
  ref: bronze.b_products_jdbc
```

SQL sources can use the same neutral reference form:

```sql
FROM {{ table_ref:silver.s_product_tags }}
```

The core validates the `layer.table` reference. Adapters resolve it to the
native catalog/table name for Databricks, AWS, Snowflake, Fabric or another
runtime.

For cross-platform planning, a source can separate the concrete source family from the ingestion intent:

```yaml
source:
  type: s3
  intent: file_stream
  path: s3://landing/orders/
  format: json
  discovery:
    strategy: file_listing
    tracking: modification_time
  state:
    storage: external
    location:
      type: object_storage
      path: s3://state/orders/
```

`type` still tells adapters what kind of source is being read. `intent`, `discovery` and `state` tell adapters which semantics must be preserved. A Databricks adapter may render Auto Loader for this intent; an AWS adapter may use Glue bookmarks or evidence state; another adapter may return `REVIEW_REQUIRED`.

Targets may include a neutral catalog type when the catalog name is logical:

```yaml
target:
  catalog: primary
  catalog_type: metastore
  schema: bronze
  table: orders
```

Adapters map logical catalogs through environment configuration or platform-specific parameters. Do not put platform product names such as Unity Catalog or Glue Catalog into core semantics unless that is intentionally a logical name in your environment.

Execution intent can be declared without naming a platform runtime:

```yaml
execution:
  freshness: near_real_time
  latency_target: 5 minutes
  preferred: continuous
  fallback: batch_incremental
```

Adapters decide whether this can be rendered as available-now processing, continuous streaming, scheduled incremental jobs or a review-required plan.

## Annotations Contract

```yaml
table:
  description: Current customer orders.
  tags:
    domain: sales
    layer: silver

columns:
  order_id:
    description: Stable order identifier.
  customer_email:
    pii: true
    tags:
      sensitivity: confidential
```

Adapters map these to catalog comments, tags, labels, classifications or review artifacts.

## Operations Contract

```yaml
owner:
  business: sales-ops
  technical: data-platform

criticality: high
frequency: hourly
freshness_sla_minutes: 90
runbook_url: https://example.internal/runbooks/orders
```

Operations metadata should become evidence even if the platform has no first-class operations catalog.

## Access Contract

```yaml
grants:
  - principal: data_scientists
    privileges: [SELECT]

row_filters:
  - name: region_filter
    expression: region = current_user_region()

column_masks:
  - column: customer_email
    expression: mask_email(customer_email)
```

Access behavior is highly platform-dependent. Adapters must return `REVIEW_REQUIRED` when native row filter, masking or permission semantics differ from the contract intent.

## Environment Contract

```yaml
environment:
  name: prod
  adapter: databricks
  evidence:
    catalog: main
    schema: ops
  runtime:
    kind: serverless
  parameters:
    databricks:
      workspace_path: /Shared/contractforge
      bundle_target: prod
```

Environment selects the adapter and execution context. It must not contain source, target, write mode, quality or access semantics.

## Complete Bundle

Recommended file layout:

```text
contracts/silver/orders.ingestion.yaml
contracts/silver/orders.annotations.yaml
contracts/silver/orders.operations.yaml
contracts/silver/orders.access.yaml
contracts/environments/prod.databricks.yaml
```

The ingestion contract owns the canonical target. Companion contracts normally inherit that target.
