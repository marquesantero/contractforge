# Databricks Adapter

`contractforge-databricks` is the reference adapter for ContractForge.

It keeps Databricks-specific execution out of `contractforge_core` while providing native Databricks behavior for Delta, Unity Catalog, Auto Loader, Lakeflow and evidence/control tables.

## Package Boundary

```text
adapters/databricks/
  pyproject.toml
  src/contractforge_databricks/
```

The adapter wheel owns:

- `contractforge_databricks`;
- `contractforge-databricks` CLI;
- Databricks SQL rendering;
- Delta write helpers;
- Unity Catalog governance;
- Auto Loader and Lakeflow artifacts;
- Delta evidence/control tables;
- Databricks runtime helpers.

The core wheel does not include this package.

## Native Responsibilities

| ContractForge concept | Databricks mapping |
| --- | --- |
| `incremental_files` | Auto Loader `cloudFiles` available-now planning/runtime helpers. |
| `kafka_available_now` | Spark Structured Streaming `availableNow` with checkpointed contract-runtime execution. |
| `append` | Delta append SQL/runtime helper. |
| `overwrite` | Delta overwrite SQL/runtime helper. |
| `upsert` | Databricks SQL `MERGE`. |
| `hash_diff_upsert` | ContractForge hash-diff staging plus Delta insert. |
| `historical` | ContractForge-compatible historical Delta MERGE. |
| `snapshot_reconcile_soft_delete` | Complete-source Delta MERGE with soft-delete semantics. |
| `custom_transform` | Databricks notebook pre-task in Asset Bundles, followed by ContractForge validation, write and evidence handling. |
| annotations | Unity Catalog comments/tags where supported. |
| access | Unity Catalog grants, row filters and column masks where supported. |
| evidence | Delta control tables such as `ctrl_ingestion_runs`, `ctrl_ingestion_quality`, `ctrl_ingestion_state` and related tables. |

## SQL And PySpark Boundary

The Databricks adapter uses a hybrid pattern:

```text
source/read/shape/quality/hash/dedup
        PySpark preparation
          |
prepared temp view or staged table
          |
write-mode execution
        SQL MERGE / INSERT / ALTER
          |
evidence/governance
        SQL artifacts and small runtime helpers
```

Use SQL for final table operations and governance. Use PySpark for connector reads, DataFrame shaping and preparation where Spark DataFrame APIs are the correct tool.

## Databricks CLI

The adapter uses the standardized command vocabulary documented in
[Adapter CLI](cli.md). Databricks-specific subcommands such as presets,
templates, dashboard rendering, governance review and Asset Bundle helpers are
platform extensions; core CLI commands remain platform-neutral.

## Custom Transform Notebook Boundary

For complex treatment that should stay in reviewed Databricks code, use
`source.type: custom_transform`. The contract declares named inputs, expected
output columns, quality rules and the target. The Databricks extension binds
that semantic boundary to a notebook task:

```yaml
extensions:
  databricks:
    custom_transform:
      notebook_path: ./notebooks/prepare_movie_features.py
      task_key: prepare_movie_features
      output_table: workspace.cf_movie_tmp.movie_feature_engineering_output
```

The adapter renders review artifacts and wires the notebook as a pre-task in
the Databricks Asset Bundle. The ContractForge runtime then reads the declared
output table and applies normal schema, quality, write-mode, evidence and
deployment-versioning behavior.

See the [Databricks movie custom transform example](adapters/databricks-custom-transform.md)
for a full bronze-to-gold project based on the tested movie/ratings data shape.

## Stable-Surface Status

The documented Databricks serverless Delta surface is classified as
`STABLE_SUPPORTED_SURFACE` with `stable_final: true` for the scoped v0.2.0
claim. This is not the broader 1.0 GA gate; full GA, unbounded continuous
streaming and generic Kafka provider equivalence remain separately governed by
the GA criteria.

The machine-readable evidence manifest is published at
`docs/reports/databricks-stable-surface-evidence.json`.

## More Detail

- [Databricks adapter spec](specs/databricks-adapter.md)
- [Databricks movie custom transform example](adapters/databricks-custom-transform.md)
- [Databricks parity tracker](specs/databricks-contractforge-parity.md)
- [Databricks stable-surface evidence](reports/databricks-stable-surface-evidence.json)
- [Databricks Kafka contract-runtime evidence](reports/databricks-kafka-provider-smoke.json)
