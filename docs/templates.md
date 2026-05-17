# Contract Templates

Templates are executable examples of complete contract bundles. They do not replace presets:

- A `preset` provides reusable defaults inside a contract.
- A `template` writes starter YAML files for a real scenario.

Use templates to speed up onboarding and standardize new data projects.

## List Templates

```bash
contractforge templates list
```

## Inspect a Template

```bash
contractforge templates show silver_jdbc_scd1_upsert
contractforge templates show silver_jdbc_scd1_upsert --metadata-only
```

## Write a YAML Bundle

```bash
contractforge templates write silver_jdbc_scd1_upsert \
  --output contracts/silver/s_orders
```

When the template contains governance files, this command writes split contracts:

```text
contracts/silver/s_orders.ingestion.yaml
contracts/silver/s_orders.annotations.yaml
contracts/silver/s_orders.operations.yaml
contracts/silver/s_orders.access.yaml
```

Validate the generated bundle:

```bash
contractforge validate-bundle contracts/silver/s_orders
contractforge governance-preview contracts/silver/s_orders
```

## Template Wizard

Use `templates wizard` to get deterministic recommendations before writing files:

```bash
contractforge templates wizard --layer silver --source jdbc --mode scd1_upsert
contractforge templates wizard --layer bronze --source s3 --pattern partitioned
contractforge templates wizard --layer bronze --source http_file --pattern csv
contractforge templates wizard --layer silver --source jdbc --pattern rds_iam
contractforge templates wizard --layer silver --pattern hash_diff --limit 1
```

Write the best recommended template:

```bash
contractforge templates wizard \
  --layer bronze \
  --source s3 \
  --output contracts/bronze/b_orders_files
```

Write a specific template in the same flow:

```bash
contractforge templates wizard \
  --layer silver \
  --pattern hash_diff \
  --name silver_scd1_hash_diff \
  --output contracts/silver/s_products_hash_diff
```

The wizard is deterministic: it does not use AI and does not open a Databricks connection. The JSON response includes `score`, `matched` and template metadata.

## Built-in Templates

| Template | Use |
| --- | --- |
| `bronze_rest_api_incremental` | Paginated REST API with watermark and secrets. |
| `bronze_http_file_csv_snapshot` | Public/authenticated HTTP(S) CSV with explicit schema and overwrite. |
| `bronze_autoloader_json` | Auto Loader JSON in `available_now` mode. |
| `bronze_autoloader_available_now_json` | Auto Loader `available_now` with external checkpoint and microbatch controls. |
| `bronze_blob_partitioned_files` | Partitioned CSV/Parquet in S3/Blob/ADLS/GCS with explicit schema and optional filtering. |
| `bronze_object_storage_nested_json_shape` | Nested JSON in object storage using `transform.shape.columns`. |
| `bronze_object_storage_small_files` | Many small files with glob, regex and explicit schema. |
| `silver_jdbc_scd1_upsert` | Incremental JDBC with SCD1, quality and access validate-only. |
| `silver_jdbc_rds_iam_hash_diff` | Amazon RDS/Aurora IAM auth with incremental JDBC and hash diff. |
| `silver_raw_json_payload_shape` | JSON string column normalized with `transform.shape.parse_json`. |
| `silver_parallel_arrays_shape` | Parallel API arrays normalized with `zip_arrays` + `explode_outer`. |
| `silver_snapshot_soft_delete` | Full snapshot with soft delete for missing rows. |
| `silver_scd1_hash_diff` | Append-only hash diff to keep changed versions. |
| `silver_scd2_history` | SCD2 history for mutable dimensions. |
| `gold_full_refresh_kpi` | Gold full refresh for aggregate/KPI tables. |

## Example: REST API to Bronze

```bash
contractforge templates write bronze_rest_api_incremental \
  --output contracts/bronze/b_orders_api
```

The generated template uses:

```yaml
source:
  type: connector
  connector: rest_api
  auth:
    type: bearer_token
    token: "{{ secret:orders_api/token }}"
  pagination:
    type: cursor
  incremental:
    watermark_param: updated_after
    watermark_header: X-Watermark
```

## Example: JDBC to Silver

```bash
contractforge templates write silver_jdbc_scd1_upsert \
  --output contracts/silver/s_orders
```

The generated template combines:

```yaml
preset:
  - silver_incremental_watermark_upsert
  - quality_quarantine
  - delta_optimized_writes

source:
  type: connector
  connector: postgres
  options:
    url: "{{ secret:erp/postgres_url }}"
    dbtable: public.orders
  auth:
    type: basic
    username: "{{ secret:erp/user }}"
    password: "{{ secret:erp/password }}"

target:
  catalog: main
  schema: sales_curated
  table: s_orders
```

## Example: Shape for Nested JSON

```bash
contractforge templates write bronze_object_storage_nested_json_shape \
  --output contracts/bronze/b_earthquake_events
```

The generated template uses `transform.shape` to project nested fields and expressions without manual PySpark:

```yaml
transform:
  shape:
    columns:
      id: event_id
      properties.mag:
        alias: magnitude
        cast: DOUBLE
      properties.time:
        alias: event_time
        expression: "CAST(properties.time / 1000 AS TIMESTAMP)"
      longitude_expr:
        alias: longitude
        expression: "element_at(geometry.coordinates, 1)"
```

## Example: RDS/Aurora IAM + Hash Diff

```bash
contractforge templates write silver_jdbc_rds_iam_hash_diff \
  --output contracts/silver/s_orders_hash_diff
```

This template demonstrates:

- `auth.type: rds_iam`
- `credential_provider: default_chain`
- JDBC partitioning with `partition_column`, bounds and `num_partitions`
- `transform.deduplicate`
- `mode: scd1_hash_diff`

## Recommended Edits After Generation

- Replace `target.schema` and `target.table` with your physical naming standard.
- Replace owners, groups and runbook URLs in `.operations.yaml`.
- Replace grants in `.access.yaml`.
- Replace URLs, paths and secret names.
- Run `contractforge validate-bundle` and `contractforge governance-preview`.
