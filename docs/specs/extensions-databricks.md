# Databricks Extensions Specification

## Purpose

`extensions.databricks` is the only contract location where Databricks-owned execution parameters may appear.

The core validates that `extensions` is an opaque map. The Databricks adapter owns the meaning, compatibility checks, rendering and runtime behavior of the keys below. These keys must not become top-level core fields.

## Canonical Shape

```yaml
extensions:
  databricks:
    delta_properties:
      delta.enableChangeDataFeed: "true"
    partition_columns: [event_date]
    cluster_columns: [customer_id]
    write_engine:
      requested: auto
      fallback_policy: fail
```

Legacy top-level aliases such as `delta_properties`, `cluster_columns`, `partition_columns`, `write_engine`, `ctrl_schema` or `notebook_name` are not accepted by the core contract.

## Supported Keys

| Key | Type | Adapter behavior |
| --- | --- | --- |
| `delta_properties` | map string to scalar | Applied during Databricks Delta table setup when the adapter creates or syncs the target table. |
| `partition_columns` | list of strings | Used for Delta table creation and partition-aware write planning. Mutually constrained by Databricks table features and clustering. |
| `cluster_columns` | list of strings | Rendered as Databricks `CLUSTER BY` or used as liquid clustering intent when supported. |
| `zorder_columns` | list of strings | Used by maintenance artifact rendering for `OPTIMIZE ... ZORDER BY` style operations where supported. |
| `write_engine` | string or map | Requests a Databricks write engine and fallback policy. See [write-engines.md](write-engines.md). |
| `lakeflow` | map | Lakeflow AUTO CDC planning and review options. Runtime execution is adapter-owned. |
| `autoloader` | map | Optional Databricks Auto Loader options for portable `source.type: incremental_files`. |
| `fix_encoding` | boolean or map | Enables adapter-owned emergency string encoding repair before write. Not portable core semantics. |
| `encoding` | string | Source character encoding used by Databricks emergency encoding repair. Only applies when `fix_encoding` is enabled. |
| `encoding_columns` | list of strings | Limits emergency encoding repair to specific string columns. |
| `cache_source` | boolean | Allows the adapter runtime to cache a prepared source DataFrame when useful. |
| `custom_transform` | map | Databricks binding for `source.type: custom_transform`, including reviewed notebook task metadata. |
| `explain_mode` | boolean or string | Captures Databricks explain plan evidence when a query runner is available. |
| `explain_format` | string | Databricks explain format to capture, for example `formatted` or `extended`. |
| `openlineage_enabled` | boolean | Emits or persists OpenLineage-compatible runtime events from Databricks evidence. |
| `openlineage_namespace` | string | Overrides the OpenLineage namespace used by Databricks lineage events. |
| `openlineage_producer` | string | Overrides the OpenLineage producer URI used by Databricks lineage events. Values are redacted in review artifacts when sensitive. |
| `optimize_after_write` | boolean | Runs adapter-owned post-write optimization when the Databricks runtime supports it. |
| `allow_type_widening` | boolean | Allows Databricks schema sync to apply compatible column type widening. Portable schema policy still lives in the core contract. |
| `lock_enabled` | boolean | Enables Databricks runtime locking through the adapter state table for a target table. |
| `merge_strategy` | string | Selects a Databricks merge strategy such as partition-scoped merge or replace partitions. |
| `merge_partition_column` | string | Partition column used by Databricks partition-scoped merge strategies. |
| `partition_column` | string | Single-column table partition shorthand. Prefer canonical `partition_columns`. |
| `partition_value` | scalar | Static Databricks partition value used by partition-aware runtime strategies. |
| `replace_partitions_source_complete` | boolean | Required safety assertion for Databricks replace-partitions strategies. |
| `hooks` | `DatabricksIngestionHooks` instance or compatible mapping | Runtime hooks around prepared input, write execution and finalization. Programmatic only. |

The adapter may support additional keys in minor releases, but each new key requires:

1. an update to this spec;
2. a compatibility or runtime test;
3. documented behavior when unsupported by the Databricks runtime;
4. no imports or behavior changes in `contractforge_core`.

## Write Engine Request

Canonical map form:

```yaml
extensions:
  databricks:
    write_engine:
      requested: lakeflow_auto_cdc
      fallback_policy: preview_only
```

`requested` may also be supplied as a string:

```yaml
extensions:
  databricks:
    write_engine: native_databricks_merge
```

The adapter records the selected engine in control-table evidence:

- `write_engine_requested`
- `write_engine_selected`
- `write_engine_status`
- `write_engine_reason`
- `write_engine_fallback_policy`

The adapter must never silently downgrade a requested engine. If the requested engine cannot preserve semantics, the result is `REVIEW_REQUIRED`, `UNSUPPORTED` or a failed runtime result depending on fallback policy.

## Incremental Files And Auto Loader

Portable contract:

```yaml
source:
  type: incremental_files
  path: s3://bucket/landing/orders/
  format: json
  trigger: available_now
  progress_location: s3://bucket/_checkpoints/orders
extensions:
  databricks:
    autoloader:
      schema_tracking_location: s3://bucket/_schemas/orders
```

The core owns the intent: checkpointed new-file discovery. The Databricks adapter translates it to `cloudFiles` and may consume `extensions.databricks.autoloader` for native options.

`source.type: autoloader` is not portable core syntax.

## Custom Treatment Notebook Binding

Portable contract:

```yaml
source:
  type: custom_transform
  intent: custom_treatment
  inputs:
    - alias: orders
      table_ref:
        layer: silver
        table: orders
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
      base_parameters:
        contract: customer_features.ingestion.yaml
```

The adapter renders a review artifact for every `custom_transform` source. When `notebook_path` is declared, the Databricks Asset Bundle includes the notebook as a pre-task and the generated ContractForge run task depends on it. At runtime, the Databricks resolver reads `extensions.databricks.custom_transform.output_table`; if that is omitted it falls back to `transform.custom.output`. One of those values is required so the library can read the reviewed notebook output and then apply normal schema, quality, write and evidence handling.

The notebook path is a Databricks binding only. The semantic contract still owns declared inputs, target, write mode, schema policy, quality rules, access rules and evidence requirements.

## Runtime Metadata Boundary

Runtime metadata such as job id, run id, cluster id, notebook path, runtime version and evidence schema is not declared in `extensions.databricks`.

Use:

- `environment` contract for stable deployment/evidence defaults;
- `DatabricksIngestOptions.runtime_metadata` for runtime facts observed at execution time;
- adapter-generated evidence for control-table records.

## Validation Behavior

The core:

- accepts `extensions` as an opaque map;
- rejects legacy top-level Databricks aliases;
- does not interpret Databricks extension keys.

The Databricks adapter:

- consumes only canonical keys already declared under `extensions.databricks`;
- warns on unknown keys with `DATABRICKS_UNKNOWN_EXTENSION`;
- rejects invalid hook objects;
- classifies unsupported native requests through planning or runtime results;
- records selected runtime behavior in evidence.
