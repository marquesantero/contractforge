# AWS Extensions Specification

## Purpose

`extensions.aws` is the only contract location where AWS-owned execution parameters may appear.

The core validates `extensions` as an opaque map. The AWS adapter owns the meaning, compatibility checks, rendering and runtime behavior of keys under `extensions.aws`. These keys must not become top-level core fields and must not be read by other adapters.

## Canonical Shape

Only declare AWS extension fields that override adapter defaults or are needed
for a specific contract. The example below shows several optional overrides; it
is not the minimum required AWS configuration.

```yaml
extensions:
  aws:
    glue_job:
      name: cf-orders
      role_arn: arn:aws:iam::123456789012:role/ContractForgeGlueRole
      script_s3_uri: s3://contractforge-artifacts/dev/orders/orders.glue_job.py
      worker_type: G.1X
      number_of_workers: 4
      timeout_minutes: 60
      max_retries: 0
      default_arguments:
        "--TempDir": s3://contractforge-artifacts/tmp/
    iceberg:
      warehouse: s3://company-lakehouse/warehouse/
      table_properties:
        write.format.default: parquet
    job_bookmarks:
      enabled: true
```

If these fields are omitted, the AWS adapter defaults Glue version `4.0`,
worker type `G.1X`, two workers, 60 minute timeout, zero retries and
library-runner mode. Bookmark enablement is inferred from source semantics
unless `job_bookmarks` or `glue_job.enable_job_bookmark` is declared.

## Supported Keys

| Key | Type | Adapter behavior |
| --- | --- | --- |
| `glue_job` | map | AWS Glue job rendering and deployment knobs, such as job name, role ARN, script S3 URI, worker shape, timeout, retries and default job arguments. |
| `iceberg` | map | Iceberg/Glue Catalog table options that do not belong to portable target semantics. `warehouse` sets `spark.sql.catalog.glue_catalog.warehouse` for Glue Spark jobs and must be an `s3://` URI. `table_properties` are applied only on generated Iceberg create/createOrReplace paths. |
| `lake_formation` | map | Lake Formation apply/review options for grants, row filters and column/security artifacts. |
| `job_bookmarks` | map | AWS Glue bookmark tuning for portable `incremental_files` or JDBC incremental contracts. |
| `dqdl` | map | AWS Glue Data Quality rendering/runtime preferences. |
| `dependencies` | map | Runtime dependency hints such as extra Python modules or connector jars. |
| `native_passthrough` | map | AWS-native connector handoff options for AppFlow, DMS, Glue native/custom connectors or related services. |

`glue_job.default_arguments` is additive only. It must not override adapter-owned Glue arguments such as `--datalake-formats`, `--enable-glue-datacatalog`, `--job-language`, `--job-bookmark-option`, or dependency arguments rendered by the adapter (`--additional-python-modules`, `--extra-jars`, `--extra-py-files`). The adapter raises instead of silently weakening the generated Glue runtime.

Consumed nested fields are also allowlisted. Misspelled nested fields warn with `AWS_UNKNOWN_EXTENSION_FIELD` and are ignored:

- `glue_job`: `name`, `role_arn`, `script_s3_uri`, `glue_version`, `worker_type`, `number_of_workers`, `timeout_minutes`, `max_retries`, `default_arguments`, `description`, `enable_job_bookmark`.
- `iceberg`: `warehouse`, `table_properties`.
- `job_bookmarks`: `enabled`, `enable_job_bookmark`.
- `dependencies`: `python_modules`, `additional_python_modules`, `jars`, `extra_jars`, `py_files`, `extra_py_files`.

The adapter may support additional keys in minor releases, but each new key requires:

1. an update to this spec;
2. a planning/rendering/runtime test;
3. documented behavior when the AWS runtime cannot preserve semantics;
4. no imports or behavior changes in `contractforge_core`.

## Validation Behavior

The core:

- accepts `extensions` as an opaque map;
- does not interpret AWS extension keys;
- does not import `contractforge_aws`.

The AWS adapter:

- reads only `extensions.aws`;
- warns on unknown keys with `AWS_UNKNOWN_EXTENSION`;
- warns on recognized keys with the wrong shape using `AWS_EXTENSION_SHAPE_IGNORED`;
- never honors unknown extension keys silently;
- never honors malformed extension values silently;
- must not allow contract extensions to relax security controls such as SSRF protection or inline-secret rejection.

## Boundary Rule

Prefer portable core parameters over AWS extensions. If a feature has equivalent intent across platforms but AWS needs extra detail, add an optional core semantic parameter with platform-neutral naming. Use `extensions.aws` only when the behavior is genuinely AWS-specific.
