# Connectors And Source Portability

ContractForge Core treats sources as contract intent. Adapters translate that intent to platform-native reads, jobs, copy operations, connector services or review artifacts.

## Source Categories

| Category | Source types | Portability |
| --- | --- | --- |
| Lakehouse catalog | `table`, `delta_table`, `iceberg_table`, `view`, `sql` | Portable intent, platform execution varies. |
| Files | `csv`, `json`, `parquet`, `delta`, `orc`, `text`, `avro`, `xml` | Portable when runtime supports the format. |
| Object storage | `s3`, `adls`, `azure_blob`, `gcs`, `object_storage`, `blob` | Portable intent, credentials/governance are adapter-owned. |
| Connection reference | `connection` | Bundle-loader reference to a reusable connection YAML; resolved to a concrete source before adapter planning. |
| Incremental files | `incremental_files` | Portable intent; adapter chooses Auto Loader, bookmarks, pipeline pattern or review. |
| HTTP files | `http_file`, `http_csv`, `http_json`, `http_text` | Portable bounded fetch intent. |
| JDBC batch | `jdbc`, `postgres`, `mysql`, `sqlserver`, `oracle`, `redshift`, `db2`, `mariadb`, `snowflake_jdbc`, `bigquery_jdbc` | Portable batch intent; drivers/network/auth are adapter-owned. |
| Bounded streams | `kafka_bounded`, `eventhubs_bounded` | Catch-up replay only; continuous streaming is adapter-specific. |
| Available-now streams | `kafka_available_now`, `eventhubs_available_now` | Checkpointed readStream catch-up with `availableNow`; not continuous streaming. |
| Lakehouse sharing | `delta_share` | Portable consumer intent where adapters support Delta Sharing or equivalent sharing clients. |
| REST API | `rest_api` | Generic bounded JSON API reads; specialized SaaS APIs should use native passthrough. |
| Custom treatment | `custom_transform` | Declared custom transformation boundary with named inputs; adapters bind native execution such as notebooks or jobs. |
| Native passthrough | `native_passthrough` | ContractForge records intent, adapter renders native connector/service artifacts. |

## Adapter-Specific Source Names

Names such as `autoloader`, `lakeflow_connect_salesforce`, `glue_bookmark` or `dataflow_gen2` are adapter-specific. They should not become core portable source types.

Preferred pattern:

```yaml
source:
  type: incremental_files
  path: s3://landing/events/
  format: json
```

Databricks may translate this to Auto Loader. AWS may translate it to Glue bookmarks. Fabric may render a Dataflow/Pipeline review artifact.

## Native Passthrough

Use `native_passthrough` when a source should be handled by a platform-native connector rather than by ContractForge connector code.

```yaml
source:
  type: native_passthrough
  system: salesforce
  object: Account
  watermark:
    column: SystemModstamp
```

Examples:

- Databricks adapter may render Lakeflow Connect artifacts.
- AWS adapter may render AppFlow or Glue artifacts.
- Fabric adapter may render Dataflow Gen2 artifacts.

The core records intent and portability diagnostics; the adapter owns native execution.

## Custom Treatment Boundary

Use `custom_transform` when a declarative transform cannot express the required treatment but the result must still stay under ContractForge validation, write-mode and evidence controls.

The contract declares the named inputs and expected output. Adapter-specific runtime details, such as a Databricks notebook path, live under the adapter extension.

```yaml
source:
  type: custom_transform
  intent: custom_treatment
  inputs:
    - alias: orders
      table_ref:
        layer: silver
        table: orders
    - alias: customers
      table: main.silver.customers
transform:
  custom:
    name: customer_feature_engineering
    output: customer_features
    expected_columns: [customer_id, order_count, lifetime_value]
extensions:
  databricks:
    custom_transform:
      notebook_path: /Workspace/ContractForge/customer_features/treatment
      task_key: prepare_customer_features
      output_table: main.tmp.customer_features_prepared
```

The notebook or job is a native adapter binding. It must not bypass schema, quality, access, write-mode or evidence semantics. Adapters should record review artifacts and require explicit runtime support before marking this source stable.

For a complete Databricks project using this boundary, see
[Databricks custom transform example](adapters/databricks-custom-transform.md).

## Reusable Connection YAML

Use `source.type: connection` when several ingestion contracts share endpoint, auth, driver and common read defaults.

See [Connection YAML](connection-yaml.md) for the full reference, including
merge order, override examples and path safety rules.

Connection file:

```yaml
# connections/supabase.yaml
type: connector
connector: postgres
system: supabase
options:
  url: "{{ secret:contractforge/supabase-jdbc-url }}"
  driver: org.postgresql.Driver
auth:
  type: basic
  username: "{{ secret:contractforge/supabase-user }}"
  password: "{{ secret:contractforge/supabase-password }}"
read:
  fetchsize: 1000
```

Ingestion contract:

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: public.products
  read:
    partition_column: product_id
    lower_bound: 1
    upper_bound: 500
    num_partitions: 4
```

`project://connections/...` paths are resolved from the nearest `project.yaml`
root. The core loads the connection file first, then deep-merges the ingestion
`source` fields on top. Ingestion fields win, including nested values such as
`read.fetchsize` or `options.driver`. Same-bundle relative paths are also
allowed when the connection file lives below the ingestion bundle directory and
the path does not contain `..`. Absolute paths and traversal outside the
bundle/project boundary are rejected.

## Logical Table References

Use logical table references when a contract reads a table produced by another
ContractForge contract. This keeps downstream medallion contracts portable
without embedding Unity Catalog, Glue Catalog, Snowflake or Fabric table
qualification in the source YAML.

Registered table source:

```yaml
source:
  type: table
  ref: bronze.b_products_jdbc
```

Explicit mapping form:

```yaml
source:
  type: table
  table_ref:
    layer: silver
    table: s_product_tags
```

Inline SQL:

```sql
SELECT *
FROM {{ table_ref:silver.s_product_tags }}
```

The core only validates/parses the neutral `layer.table` reference. Each
adapter owns native resolution:

| Adapter | Example rendered table |
| --- | --- |
| Databricks | `workspace.cf_demo_bronze.b_products_jdbc` |
| AWS | `glue_catalog.contractforge_cf_demo_bronze.b_products_jdbc` |

If a project uses naming that cannot be inferred from the target layer, keep
the reference explicit with `table_ref.schema` and `table_ref.catalog`, or use
a platform-specific source table only after documenting the portability tradeoff.

## Connector Reference

| Source type | Required fields | Auth modes | Runtime notes |
| --- | --- | --- | --- |
| `table`, `delta_table`, `iceberg_table`, `view` | `table`, `path`, `ref` or `table_ref` | runtime identity | Adapter resolves catalog object, path or logical `layer.table` reference. |
| `sql` | `query` or `options.query` | runtime identity | Query dialect is platform-owned. SQL may include `{{ table_ref:layer.table }}` placeholders for contract-managed downstream sources. |
| `csv`, `json`, `jsonl`, `ndjson`, `parquet`, `delta`, `orc`, `text`, `avro`, `xml` | `path` | runtime identity or storage auth | XML parser details are adapter/runtime specific and belong in `source.options`. |
| `s3`, `adls`, `azure_blob`, `gcs`, `blob`, `object_storage` | `provider` when generic, `format`, `path` | runtime identity, storage-specific credentials | Governance and credential binding are adapter-owned. |
| `connection` | `connection_path` | inherited from referenced YAML | Resolved by the core bundle loader. Adapters receive the concrete resolved source, not `type: connection`. |
| `incremental_files` | `path`, `format` | runtime identity or storage-specific credentials | Databricks maps to Auto Loader; other adapters may use bookmarks, file listings, pipelines or review. |
| `http_file`, `http_csv`, `http_json`, `http_text` | `request.url` | none, bearer token, API key, basic | Bounded file fetch. Limits include timeout, retries, bytes and records. |
| `rest_api` | `request.url` | none, basic, bearer token, API key, OAuth client credentials | Generic bounded JSON API reads with pagination/retry limits. The shared core client validates request and OAuth token URLs, rejects unsafe schemes/private hosts by default and refuses HTTP redirects. Use native passthrough for vendor-specific APIs. |
| `custom_transform` | `inputs` | adapter-owned | Declares a custom treatment boundary with named source inputs. Native runtime binding belongs in adapter extensions. |
| `jdbc`, `postgres`, `mysql`, `mariadb`, `sqlserver`, `oracle`, `redshift`, `db2`, `snowflake_jdbc`, `bigquery_jdbc` | `url` plus `table`, `query`, `options.dbtable` or `options.query` | none, basic, connector-specific modes | Partitioned reads require all partition fields together. Oracle JDBC driver must be supplied by the user/runtime. |
| `kafka_bounded` | `bootstrap_servers`, `topic` or `topics` or `assign` | adapter/runtime specific | Bounded replay using starting/ending offsets or timestamps. |
| `eventhubs_bounded` | `connection_string` or Event Hubs options | adapter/runtime specific | Bounded replay using starting/ending positions. |
| `kafka_available_now` | `bootstrap_servers`, `topic`, `checkpoint_location` | adapter/runtime specific | Databricks uses `readStream.trigger(availableNow=True)` and records stream evidence. |
| `eventhubs_available_now` | `connection_string` or Event Hubs options, `checkpoint_location` | adapter/runtime specific | Databricks uses `readStream.trigger(availableNow=True)` and records stream evidence. |
| `delta_share` | `profile_file`, `table` | profile file or runtime secret | Consumer-side sharing source. |
| `native_passthrough` | `system` | adapter-owned | Adapter renders native connector artifacts, not core connector code. |

## JDBC Notes

JDBC is portable intent, not portable packaging. Adapters must document required drivers and platform networking.

- Oracle remains a valid JDBC source, but ContractForge must not redistribute `ojdbc`; users provide the driver in the target runtime.
- RDS IAM is declared in the core as `source.auth.type: rds_iam`. The core produces review-safe JDBC options and the Databricks adapter materializes the token at runtime using either declared secret placeholders or the cluster AWS credential chain.
- Partitioned reads require `source.read.partition_column`, `source.read.lower_bound`, `source.read.upper_bound` and `source.read.num_partitions` together.

## Available-Now Streams

Available-now streams are for checkpointed catch-up execution, not long-running continuous streaming.

```yaml
source:
  type: kafka_available_now
  bootstrap_servers: broker:9093
  topic: orders
  checkpoint_location: s3://bucket/_checkpoints/orders
```

Databricks executes this through Structured Streaming `availableNow`, writes a parent stream record to `ctrl_ingestion_streams`, and writes each micro-batch as a child ingestion run.

## Practical Rules

- Prefer `table` or `sql` when another system already landed or federated data.
- Prefer `incremental_files` for recurring file arrivals.
- Prefer `http_file` for bounded public or authenticated files.
- Prefer JDBC for relational batch ingestion with clear predicates/partitioning.
- Prefer `custom_transform` when business treatment needs reviewed custom code while the contract still owns inputs, output validation, write mode and evidence.
- Treat SaaS/ERP/marketing connectors as native passthrough or adapter-owned connectors.
- Do not hide continuous streaming semantics behind a batch connector.

Detailed source decisions are in [source portability](specs/source-portability.md).
