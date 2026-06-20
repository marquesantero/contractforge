# Write Engines Specification

## Purpose

A ContractForge write mode describes semantic intent. A write engine describes how an adapter executes that intent on a specific platform.

The core owns write modes such as append, overwrite, upsert, hash-diff upsert and historical versioning. Adapters own native engine selection. The selected engine must be recorded as evidence so operators can see whether a run used native platform behavior or a ContractForge-managed algorithm.

## Core Write Modes

| Contract mode | Portable semantics |
| --- | --- |
| `append` | Append prepared rows to the target without matching existing rows. |
| `overwrite` | Replace the target contents according to adapter-supported overwrite semantics. |
| `replace_partitions` | Replace scoped partitions only. Requires explicit partition predicate support. |
| `upsert` | Current-state merge keyed by `merge_keys`. Requires merge or equivalent update semantics. |
| `hash_diff_upsert` | Insert/update only when a row hash changes. Requires hash calculation and merge or equivalent semantics. |
| `historical` | Preserve history with current-row markers and validity columns. Requires stronger review across platforms. |
| `snapshot_reconcile_soft_delete` | Snapshot comparison with soft-delete marking for missing records. Review required across many engines. |

The planner must never replace a requested mode with a weaker mode. For example, `historical` cannot fall back to `append`.

## Databricks Engine Names

| Engine | Typical modes | Status value | Notes |
| --- | --- | --- | --- |
| `delta_append` | `append` | `native_databricks` | SQL insert into Delta target. |
| `delta_overwrite` | `overwrite` | `native_databricks` | Delta overwrite behavior selected by adapter policy. |
| `delta_replace_partitions` | `replace_partitions` | `native_databricks` | Uses partition predicates or `replaceWhere` style behavior where supported. |
| `delta_merge` | `upsert` | `native_databricks` | Delta `MERGE` using core merge keys. |
| `core_managed_hash_diff_delta` | `hash_diff_upsert` | `contractforge_algorithm` | Adapter computes row hash and executes Delta merge/write flow. |
| `core_managed_historical_delta` | `historical` | `contractforge_algorithm` | Adapter builds historical staging columns and executes Delta merge semantics. |
| `core_managed_snapshot_reconcile_soft_delete_delta` | `snapshot_reconcile_soft_delete` | `contractforge_algorithm` | Adapter compares snapshot state and applies soft-delete columns. |
| `databricks_sql_merge` | upsert-style modes | `native_databricks` or `review_required` | Explicit native SQL merge request. Subject to compatibility checks. |
| `lakeflow_auto_cdc` | CDC-style upsert and historical modes | `review_required` or `native_databricks_preview` | Planned/rendered through Lakeflow compatibility review before runtime use. |
| `auto` | any supported mode | selected engine status | Adapter chooses the safest supported engine for the contract. |

The exact selected engine is persisted per run. Users should read evidence instead of inferring execution behavior from mode alone.

## Request Syntax

Adapter-specific engine requests live under `extensions.databricks`.

```yaml
extensions:
  databricks:
    write_engine:
      requested: lakeflow_auto_cdc
      fallback_policy: preview_only
```

Supported `fallback_policy` values are adapter-owned. Databricks currently treats these policies as:

| Policy | Behavior |
| --- | --- |
| `fail` | Fail if the requested engine cannot be used safely. |
| `preview_only` | Render/review the native plan but do not silently execute an alternate engine as if equivalent. |
| `auto` | Allow the adapter to choose a compatible engine when no explicit engine is required. |

## Evidence Columns

Every production run should populate:

- `write_engine_requested`: user request, usually `auto` when not specified.
- `write_engine_selected`: concrete engine selected by the adapter.
- `write_engine_status`: classification such as `native_databricks`, `contractforge_algorithm`, `review_required` or `unsupported`.
- `write_engine_reason`: short selection or blocker explanation.
- `write_engine_fallback_policy`: policy applied when request and selected engine differ.

These columns belong to the core evidence model. The adapter fills them with platform-specific values.

## Adapter Authoring Requirements

Every adapter must define:

1. the write modes it supports natively;
2. the modes it supports with a ContractForge-managed algorithm;
3. the modes that require review;
4. the modes that are unsupported;
5. evidence values for requested, selected, status, reason and fallback policy.

An adapter may have fewer native engines than Databricks. That is acceptable if the planner returns the correct status and does not alter semantics silently.

## Cross-Platform Guidance

| Platform | Likely native engines | Review pressure |
| --- | --- | --- |
| Databricks | Delta append, overwrite, merge, Auto Loader, Lakeflow AUTO CDC | historical equivalence, soft deletes, available-now streams. |
| AWS | Iceberg append/overwrite/merge through Glue or EMR | Table format/version behavior, Lake Formation governance, job bookmarks. |
| Fabric | Lakehouse table writes, Dataflow Gen2, Data Pipelines | Merge/history semantics and checkpoint behavior. |
| Snowflake | SQL insert/merge, streams/tasks, dynamic tables | historical mapping, masking/row access policy parity. |
| GCP | BigQuery load/merge, Dataflow, Dataproc/Iceberg | Merge semantics, streaming checkpoint and governance parity. |

When a platform needs more parameters than the core mode exposes, the adapter should use its own extension namespace or environment parameters. It must not add platform-specific fields to the core contract root.
