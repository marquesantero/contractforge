# Supabase JDBC Medallion Contract Parity

This document compares the Databricks and AWS contract YAMLs for the Supabase
JDBC medallion example.

The goal of this example is to keep ingestion intent portable while allowing
small platform-specific differences where native runtimes require different
deployment settings or optional optimization hints.

## Summary

The Databricks and AWS contracts are semantically equivalent.

The shared semantics are identical for:

- Source connection inheritance through `source.type: connection`.
- JDBC table names and partitioned read settings for bronze contracts.
- Logical downstream table references through `source.ref` and `{{ table_ref:... }}`.
- Write modes.
- Schema policy.
- Merge keys and hash keys.
- Transform logic.
- Quality rules and enforcement.
- Annotations.
- Operations metadata.
- Execution order.

The only intentional YAML differences are:

- `target.catalog`
- Databricks-only `extensions.databricks`
- environment-level deployment and artifact settings

There are no `access` YAMLs in this example for either platform.

## Shared Connection

Both platforms use the same connection YAML:

```yaml
source:
  type: connector
  connector: postgres
  system: supabase_inventory_demo
  name: supabase_postgres_shared_connection
  url: "{{ secret:contractforge-secrets/supabase-jdbc-url }}"
  auth:
    type: basic
    username: "{{ secret:contractforge-secrets/supabase-user }}"
    password: "{{ secret:contractforge-secrets/supabase-password }}"
  options:
    driver: org.postgresql.Driver
    fetchsize: "10000"
  read:
    source_complete: true
```

The secret placeholders are the same in the contract. Each adapter resolves
them with its own runtime secret provider:

- Databricks: Databricks Secrets
- AWS: AWS Secrets Manager

No secret value is materialized into generated artifacts.

## Environment Differences

| Area | Databricks | AWS | Reason |
|---|---|---|---|
| Adapter | `databricks` | `aws` | Selects native adapter implementation. |
| Runtime | `serverless` | `aws_glue_spark` | Different execution engines. |
| Deployment artifact | Databricks Asset Bundle | Glue job definition + S3 artifacts | Native deployment shape differs. |
| Evidence location | `catalog: workspace`, `schema: cf_supabase_jdbc_e2e_v2_ops` | `database: contractforge_cf_supabase_jdbc_e2e_v2_ops` | Databricks uses catalog/schema; AWS Glue uses databases. |
| Artifact storage | DAB/workspace paths | `artifacts.uri: s3://.../contractforge-supabase-jdbc-v2/` | AWS needs generated job scripts and manifests in S3. |
| Table warehouse | Delta-managed by Databricks | `parameters.aws.iceberg.warehouse: s3://.../warehouse/supabase-jdbc-v2/` | AWS Iceberg tables need an S3 warehouse root. |
| Dependencies | DAB environment dependencies | Glue `extra_py_files`, `extra_jars`, Python modules | Glue needs the core wheel, AWS adapter wheel and PostgreSQL JDBC driver supplied explicitly. |
| Job compute | Serverless task environment | Glue role, worker type, workers, timeout, retries | AWS Glue job registration requires these fields. |

## Logical Table References

Downstream silver/gold contracts read tables already produced by earlier
contracts through portable logical references.

Table source:

```yaml
source:
  type: table
  ref: bronze.b_products_jdbc
```

SQL source:

```sql
FROM {{ table_ref:bronze.b_product_movements_jdbc }}
```

The core validates/parses the neutral `layer.table` reference. Each adapter
owns native qualification:

| Logical ref | Databricks | AWS |
|---|---|---|
| `bronze.b_products_jdbc` | `workspace.cf_supabase_jdbc_e2e_v2_bronze.b_products_jdbc` | `glue_catalog.contractforge_cf_supabase_jdbc_e2e_v2_bronze.b_products_jdbc` |
| `bronze.b_product_movements_jdbc` | `workspace.cf_supabase_jdbc_e2e_v2_bronze.b_product_movements_jdbc` | `glue_catalog.contractforge_cf_supabase_jdbc_e2e_v2_bronze.b_product_movements_jdbc` |
| `silver.s_product_tags` | `workspace.cf_supabase_jdbc_e2e_v2_silver.s_product_tags` | `glue_catalog.contractforge_cf_supabase_jdbc_e2e_v2_silver.s_product_tags` |
| `silver.s_movements_current` | `workspace.cf_supabase_jdbc_e2e_v2_silver.s_movements_current` | `glue_catalog.contractforge_cf_supabase_jdbc_e2e_v2_silver.s_movements_current` |

## Contract Difference Matrix

### `bronze_supabase_products`

Identical sections:

- `annotations`
- `operations`

Ingestion differences:

| Field | Databricks | AWS | Reason |
|---|---|---|---|
| `target.catalog` | `workspace` | `contractforge` | Logical catalog names differ per adapter. AWS uses Glue database names derived from catalog + schema. |
| `extensions.databricks.delta_properties.delta.enableChangeDataFeed` | `true` | not present | Delta Change Data Feed is Databricks/Delta-specific. |
| `extensions.databricks.cluster_columns` | `[brand, price_band]` | not present | Databricks clustering optimization; not portable to Glue/Iceberg in this contract. |

No semantic differences:

- Source table: `cf_supabase_newcore_demo.products`
- Read partitioning: `product_id`, `1..100000`, `8` partitions, `fetchsize: 10000`
- Mode: `hash_diff_upsert`
- Schema policy: `additive_only`
- Keys: `merge_keys: [product_id]`, hash keys over product attributes
- Quality: product required fields, unique key, accepted price bands, quarantine negative prices

### `bronze_supabase_movements`

Identical sections:

- `annotations`
- `operations`

Ingestion differences:

| Field | Databricks | AWS | Reason |
|---|---|---|---|
| `target.catalog` | `workspace` | `contractforge` | Logical catalog names differ per adapter. |
| `extensions.databricks.delta_properties.delta.enableChangeDataFeed` | `true` | not present | Delta CDF is Databricks-specific. |
| `extensions.databricks.cluster_columns` | `[movement_date, movement_type]` | not present | Databricks clustering optimization. |

No semantic differences:

- Source table: `cf_supabase_newcore_demo.product_movements`
- Read partitioning: `id`, `1..1000500`, `16` partitions, `fetchsize: 20000`
- Mode: `upsert`
- Merge key: `movement_uid`
- Composite key derivation: `product_id`, `movement_seq`
- Deduplication order: `updated_at DESC`, `id DESC`
- Quality: movement required fields, unique key, accepted movement types, quarantine zero quantity and negative unit cost

### `silver_supabase_product_tags`

Identical sections:

- `annotations`
- `operations`

Ingestion differences:

| Field | Databricks | AWS | Reason |
|---|---|---|---|
| `target.catalog` | `workspace` | `contractforge` | Logical catalog names differ per adapter. |
| `extensions.databricks.delta_properties.delta.enableChangeDataFeed` | `true` | not present | Delta CDF is Databricks-specific. |
| `extensions.databricks.cluster_columns` | `[brand, price_band]` | not present | Databricks clustering optimization. |

No semantic differences:

- Source logical ref: `bronze.b_products_jdbc`
- Mode: `overwrite`
- JSON parsing schemas for `attributes_json` and `tags_json`
- `cast_input: STRING`
- Array explode of `product_tags`
- Column projection and casts
- Brand/tag/supplier standardization
- Derived `product_tag_uid`
- Deduplication by `product_tag_uid`
- Quality: required fields, unique key, accepted price bands and supplier tiers, quarantine null exploded tags

### `silver_supabase_movements_current`

Identical sections:

- `annotations`
- `operations`

Ingestion differences:

| Field | Databricks | AWS | Reason |
|---|---|---|---|
| `target.catalog` | `workspace` | `contractforge` | Logical catalog names differ per adapter. |
| `extensions.databricks.delta_properties.delta.enableChangeDataFeed` | `true` | not present | Delta CDF is Databricks-specific. |
| `extensions.databricks.cluster_columns` | `[movement_date, movement_type]` | not present | Databricks clustering optimization. |

No semantic differences:

- Source SQL uses `{{ table_ref:bronze.b_product_movements_jdbc }}`
- Mode: `overwrite`
- SQL projection
- Window function:
  `ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY event_ts DESC, updated_at DESC)`
- Derived `is_latest_for_product`
- Quality: required fields, unique key, abort if rank is not positive

### `gold_supabase_brand_inventory`

Identical sections:

- `annotations`
- `operations`

Ingestion differences:

| Field | Databricks | AWS | Reason |
|---|---|---|---|
| `target.catalog` | `workspace` | `contractforge` | Logical catalog names differ per adapter. |
| `extensions.databricks.delta_properties.delta.enableChangeDataFeed` | `true` | not present | Delta CDF is Databricks-specific. |
| `extensions.databricks.cluster_columns` | `[brand, price_band]` | not present | Databricks clustering optimization. |

No semantic differences:

- Source SQL uses `{{ table_ref:silver.s_product_tags }}` and `{{ table_ref:silver.s_movements_current }}`
- Mode: `overwrite`
- Aggregate grain: `brand`, `price_band`, `supplier_tier`
- Measures: product count, distinct tags, inbound/outbound quantities, gross movement value, latest movement time
- Quality: required fields and abort on negative product count

## Platform-Specific Extensions

Databricks contracts include:

```yaml
extensions:
  databricks:
    delta_properties:
      delta.enableChangeDataFeed: "true"
    cluster_columns: [...]
```

These are intentionally absent from AWS contracts. They are not portable
semantic intent; they are Databricks-native table optimization and Delta
features.

AWS does not add equivalent `extensions.aws` in these ingestion contracts.
Instead, AWS table format and deployment behavior are controlled by the
environment:

```yaml
parameters:
  aws:
    iceberg:
      warehouse: s3://...
```

This keeps the dataset contract focused on ingestion intent and keeps AWS
deployment/storage settings in the environment contract.

## What This Proves

This project validates that the same ingestion design can be moved from
Databricks to AWS with minimal contract differences.

The portable part is the contract intent:

- what to read
- how to key and write it
- how to transform it
- how to validate and quarantine it
- what annotations and operations metadata to preserve
- what evidence to emit

The platform-specific part is the execution boundary:

- how artifacts are published
- which native table format is used
- how compute and dependencies are configured
- which optional native optimizations are available

## Remaining Improvement

The remaining platform differences are now limited to target catalog naming,
environment deployment settings and optional native extensions. If desired,
logical target catalogs can be introduced later, but that should be a separate
API decision because it affects how users name deployment environments.
