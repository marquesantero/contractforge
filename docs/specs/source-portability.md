# Source Portability Specification

## Purpose

ContractForge Core classifies source types by portability before an adapter attempts to plan or render execution.

The source contract must make the boundary explicit:

- portable built-in source
- native passthrough source
- bounded stream source
- available-now stream source
- unsupported or non-portable source

This prevents platform-specific connectors from leaking into the semantic core while still allowing adapters to use the best native capability available.

## Portable Built-Ins

These source types are maintained as core-level portable intent:

| Category | Source types |
| --- | --- |
| Lakehouse catalog | `table`, `delta_table`, `iceberg_table`, `view`, `sql` |
| File formats | `csv`, `json`, `parquet`, `delta`, `orc`, `text`, `avro`, `xml` |
| Object storage | `s3`, `adls`, `azure_blob`, `gcs`, `blob`, `object_storage` |
| Incremental files | `incremental_files` |
| HTTP fetch | `http_file`, `http_csv`, `http_json`, `http_text` |
| JDBC batch | `jdbc`, `postgres`, `mysql`, `sqlserver`, `oracle`, `redshift`, `db2`, `mariadb` |
| Bounded streams | `kafka_bounded`, `eventhubs_bounded` |
| Available-now streams | `kafka_available_now`, `eventhubs_available_now` |
| Lakehouse sharing | `delta_share` |
| Connection reference | `connection` |

`oracle` is portable JDBC intent, but adapters must document that the user provides the Oracle JDBC driver. The project must not redistribute `ojdbc`.

`xml` is portable file intent, but parser options such as row tags, schema validation and malformed-record handling vary by adapter. Contracts should declare required parser options in `source.options`, and adapters must return warnings or review-required results when their runtime cannot preserve the declared XML semantics.

`connection` is not a runtime connector. It is a reusable YAML reference resolved by `load_contract_bundle()` before semantic normalization. After resolution, adapters see the concrete source declared by the connection YAML, such as `connector/postgres`, `http_file`, `object_storage` or `rest_api`.

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: public.products
```

`project://` paths are resolved from the nearest `project.yaml` root. Same-bundle
relative paths are allowed only when they stay under the ingestion bundle
directory and do not contain `..`. Absolute paths are rejected. Dataset-specific
fields in the ingestion contract override connection defaults through deep
merge.

Catalog sources can also use logical table references when reading a table
created by another ContractForge contract:

```yaml
source:
  type: table
  ref: bronze.b_products_jdbc
```

SQL sources can reference the same logical table through placeholders:

```sql
FROM {{ table_ref:silver.s_product_tags }}
```

The core validates the neutral `layer.table` reference. Adapters resolve it to
native table names. This keeps downstream medallion contracts portable without
teaching the core Unity Catalog, Glue Catalog, Snowflake or Fabric naming rules.

## Source Intent, Discovery And State

`source.type` remains the concrete portable source family, such as `s3`, `jdbc`, `incremental_files`, `rest_api` or `native_passthrough`.

Contracts may also declare optional intent metadata when the source family alone is not enough to express adapter planning intent:

- `source.intent`: high-level ingestion intent, such as `file_stream`, `file_batch`, `database_query`, `catalog_query`, `api_call`, `object_files`, `stream_replay` or `native_handoff`.
- `source.discovery`: how new source data is discovered, with `strategy` values such as `file_listing`, `event_driven` or `queue_based`, and `tracking` values such as `modification_time`, `filename_pattern`, `external_state` or `external_queue`.
- `source.state`: where source progress is tracked when the contract requires an explicit state location. `storage: external` requires a `location`; `adapter_managed` lets the adapter choose the native state mechanism.

These fields do not introduce platform execution behavior into the core. They give adapters more precise planning input while preserving the original source payload in evidence.

Example:

```yaml
source:
  type: s3
  intent: file_stream
  path: s3://bucket/landing/events/
  format: json
  discovery:
    strategy: file_listing
    tracking: modification_time
  state:
    storage: external
    location:
      type: object_storage
      path: s3://bucket/_state/events/
```

An adapter may map this to Auto Loader, Glue bookmarks, object listing plus evidence state, a pipeline-native incremental pattern, or `REVIEW_REQUIRED`. It must not silently convert the contract into a weaker bounded batch read.

## Incremental Files

`incremental_files` is the portable source intent for reading new files under a path with checkpoint/progress tracking.

Adapter examples:

- Databricks: Auto Loader `cloudFiles`
- AWS: Glue bookmarks or equivalent job state
- Fabric: platform-native incremental dataflow or pipeline behavior

Neither the core nor platform adapters should accept platform-specific source aliases such as `autoloader` as contract input. Migration tooling may rewrite old contracts before validation, but the runtime contract remains `incremental_files`.

Canonical portable fields:

- `path`
- `format`
- `progress_location`
- `schema_tracking_location`
- `schema_hints`
- `options`

Native adapter defaults for incremental file handling belong in `environment.parameters.<adapter>`, not in the source contract.

## Bounded Streams

`kafka_bounded` and `eventhubs_bounded` mean catch-up/replay over a bounded offset or timestamp range.

They do not mean continuous streaming. Continuous streaming requires a separate execution model with checkpointing, watermarks, exactly-once behavior, backpressure, and recovery semantics.

## Available-Now Streams

`kafka_available_now` and `eventhubs_available_now` mean checkpointed stream catch-up: the adapter reads all currently available events, persists stream progress at `source.checkpoint_location`, then terminates.

This is not continuous streaming. Adapters may map it to native `availableNow` triggers, scheduled catch-up jobs, or `REVIEW_REQUIRED` when checkpoint and write semantics cannot be preserved.

Canonical portable fields:

- `checkpoint_location`
- Kafka: `bootstrap_servers` plus `topic`, `topics` or `assign`
- Event Hubs: `connection_string` and `event_hub_name`
- Stream throughput limits: declare `source.limits.max_offsets_per_trigger` for Kafka and
  `source.limits.max_events_per_trigger` for Event Hubs. Top-level
  `max_offsets_per_trigger` / `max_events_per_trigger` are also accepted by the
  source model for direct stream connector declarations; if both locations are
  present with different values, validation/rendering must fail instead of
  silently choosing one.

## Non-Portable Sources

The core does not maintain a list of platform-specific source names. Unknown source types are not portable core source types.

Adapters may support adapter-local source names, but those names must not be added to `contractforge_core`.

## Native Passthrough

`native_passthrough` is a first-class source type for SaaS, enterprise applications, and proprietary connectors where platform-native ingestion is preferable to maintaining a custom connector.

Examples:

- Salesforce
- Workday
- SAP
- SharePoint
- Google Drive
- OData and SAP OData
- MongoDB, Cosmos DB, Elastic/OpenSearch
- SFTP, FTP, IMAP

Adapters translate native passthrough to their native service:

- Databricks: Lakeflow Connect or workspace-native connection/pipeline
- AWS: AppFlow, DMS, Glue connector, or platform-native job
- Fabric: Dataflow Gen2 or platform connector

## Contract Examples

Portable JDBC:

```yaml
source:
  type: jdbc
  jdbc:
    url: jdbc:postgresql://host:5432/db
    table: public.accounts
  watermark:
    column: updated_at
    type: timestamp
```

Portable incremental files:

```yaml
source:
  type: incremental_files
  path: s3://bucket/landing/events/
  format: json
  progress_location: s3://bucket/_progress/events/
  schema_tracking_location: s3://bucket/_schemas/events/
```

Portable object-storage source with explicit file-stream intent:

```yaml
source:
  type: s3
  intent: file_stream
  path: s3://bucket/landing/events/
  format: json
  discovery:
    strategy: file_listing
    tracking: modification_time
```

Native passthrough:

```yaml
source:
  type: native_passthrough
  system: salesforce
  object: Account
  watermark:
    column: SystemModstamp
  auth:
    type: oauth2_jwt
    secret_scope: sf_prod
```
