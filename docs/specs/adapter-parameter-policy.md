# Adapter Parameter Policy

## Purpose

This policy defines how ContractForge Core names contract parameters and how platform adapters add native behavior without forcing the core contract to mirror one platform.

The core owns semantic parameter names. Adapters own translation.

## Parameter Layers

ContractForge parameters are classified into four layers.

| Layer | Owner | Purpose | Example |
| --- | --- | --- | --- |
| Core semantic | Core | Platform-neutral intent. | `source.type: incremental_files`, `progress_location`, `schema_policy` |
| Core optional detail | Core | Extra portable detail that multiple platforms can use. | `schema_tracking_location`, `watermark`, `merge_keys` |
| Adapter parameter | Adapter | Native tuning or required native options. | `environment.parameters.databricks`, `environment.parameters.aws` |
| Native artifact | Adapter | Rendered platform resource, not contract input. | Databricks Asset Bundle, Glue job script, Fabric pipeline JSON |

Adapter parameters live in `environment.parameters.<adapter>`.

## Naming Rules

Core names must describe intent, not an implementation.

Preferred examples:

| Prefer | Avoid in core | Reason |
| --- | --- | --- |
| `incremental_files` | `autoloader` | Auto Loader is Databricks-specific. |
| `progress_location` | `checkpoint_location` | Checkpoint is implementation vocabulary; progress is semantic. |
| `schema_tracking_location` | `schema_location` | Schema tracking describes intent across engines. |
| `native_passthrough` | `lakeflow_connect` / `appflow` | Native connector service differs by platform. |
| `access.row_filters` | `unity_catalog_row_filters` | Row filtering is cross-platform intent. |
| `annotations.tags` | `uc_tags` / `lf_tags` / `policy_tags` | Tag implementation differs by catalog. |

Databricks adapter names must not become compatibility aliases in the core. Platform-specific names should be converted before validation rather than accepted by runtime APIs.

## No Core Aliases

The core does not preserve platform-specific aliases.

Disallowed in core:

- `source.type: autoloader`
- `checkpoint_location`
- `schema_location`
- `glue_bookmark`
- `lakeflow_connect_*`
- `appflow_*`
- `dms_*`
- `dataflow_gen2_*`
- `shortcut_*`

Allowed outside runtime contracts:

- conversion helpers that rewrite platform-specific names to canonical names before validation
- diagnostics documenting why a native alias was rejected
- rendered artifacts using native platform names
- adapter docs explaining how canonical core fields map to native parameters

## Extension Shape

Portable parameters stay in their normal contract section.

Adapter-specific parameters live under `environment.parameters.<adapter>`.

Recommended shape:

```yaml
source:
  type: incremental_files
  path: s3://bucket/landing/events/
  format: json
  progress_location: s3://bucket/_progress/events/
  schema_tracking_location: s3://bucket/_schemas/events/
environment:
  name: prod
  adapter: databricks
  parameters:
    databricks:
      incremental_files.infer_column_types: true
      job.warehouse_id: ${DATABRICKS_WAREHOUSE_ID}
```

Rules:

- `environment.parameters.<adapter>` configures adapter-owned deployment/rendering concerns and platform defaults.
- adapters must ignore extension blocks for other platforms.
- adapters must warn when a required native extension is missing and cannot be safely defaulted.

## When A Platform Needs More Parameters

Adapters must follow this order:

1. Use the core semantic parameter.
2. Use a safe platform default if one exists and document it as a warning when relevant.
3. Read adapter-specific parameters from `environment.parameters.<adapter>`.
4. Return `REVIEW_REQUIRED` if a design choice is needed.
5. Return `UNSUPPORTED` if no safe equivalent exists.

Examples:

| ContractForge intent | Platform need | Adapter behavior |
| --- | --- | --- |
| `incremental_files` | Databricks needs `cloudFiles.schemaLocation`. | Use `schema_tracking_location`; if missing, use review warning or require extension depending on execution mode. |
| `incremental_files` | AWS Glue may need bookmark key/state configuration. | Use `progress_location` if external state is rendered; otherwise read `environment.parameters.aws` defaults. |
| `annotations.columns.email.pii` | GCP may need policy tag taxonomy id. | Read `environment.parameters.gcp.policy_tags`; otherwise `REVIEW_REQUIRED`. |
| `access.column_masks.email.function` | Snowflake may need masking policy signature. | Use function if compatible; otherwise require `environment.parameters.snowflake.masking_policy`. |
| `operations.alert_on_failure` | AWS needs SNS/EventBridge target. | Read `environment.parameters.aws.alerting`; otherwise `REVIEW_REQUIRED`. |

## When To Rename A Parameter

Rename a core parameter when:

- the name is tied to one platform's product or API
- at least two platforms can implement the same intent under different names
- the current name hides a semantic distinction
- examples would mislead users into thinking a portable contract is platform-specific

Do not rename when:

- the parameter is already semantic and readable
- only one platform can implement the concept
- the concept should be a platform extension instead

## Adapter Planning Output

Adapters must report parameter-level decisions in planning diagnostics when behavior is not fully direct.

Diagnostics should include:

- contract parameter path
- adapter target
- status
- native mapping
- missing native parameters, if any
- warning or review reason

Example:

```json
{
  "parameter": "source.schema_tracking_location",
  "adapter": "databricks",
  "status": "SUPPORTED",
  "native_mapping": "cloudFiles.schemaLocation"
}
```

## Core Rule

The core accepts adapter extension blocks as opaque data. It must not validate, normalize, rename or interpret adapter-owned keys.

The adapter owns native execution artifacts and native option semantics.
