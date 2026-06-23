# Parameter Defaults

## Purpose

ContractForge should be concise without hiding semantics. Defaults are allowed
only when the omitted value does not change ingestion intent, governance intent,
write semantics, data loss risk, cost posture or deployment trust boundaries.

## Defaulting Rule

Use defaults for stable operational conventions. Require explicit values for
semantic choices and platform/account boundaries.

## Safe Core Defaults

| Field | Default | Reason |
| --- | --- | --- |
| `layer` | `bronze` | A missing layer can safely mean the first ingestion layer. |
| `mode` | `append` | Conservative write behavior; no overwrite, merge or history is implied. |
| `schema_policy` | `permissive` | Existing permissive behavior; stricter policies remain explicit. |
| `on_quality_fail` | `fail` | Quality failures remain fail-closed unless the contract asks for warning/quarantine behavior. |
| `hash_strategy` | `explicit` | Avoids hashing hundreds of columns unless requested. |
| `scd2_late_arriving_policy` | `apply` | Late arriving rows are applied unless a contract explicitly asks for review/blocking behavior. |
| `idempotency_policy` | `always_run` | Does not silently skip user-requested executions. |
| `extensions` | `{}` | Adapter extension space is empty unless explicitly declared. |
| `dry_run` | `false` | Contracts execute normally unless dry-run planning is requested. |
| `source.state.storage` | `adapter_managed` | Lets each adapter use its safest native state when no external state location is declared. |
| `environment.name` | `dev` | Logical environment label only; does not change ingestion semantics. |
| `schedule.timezone` | `UTC` | Portable scheduler default when a schedule is declared. |
| `schedule.enabled` | `true` | A declared schedule is active unless the project explicitly deploys it paused/disabled. |

## Contract Section Defaults

These defaults come from the public contract models. They are intentionally
small and fail-closed where execution or governance risk exists.

| Section | Field | Default | Reason |
| --- | --- | --- | --- |
| `source` | `read`, `request`, `watermark`, `options`, `auth`, `pagination`, `response`, `incremental`, `limits` | `{}` | Empty maps make nested overrides predictable without inventing source semantics. |
| `source.state` | `storage` | `adapter_managed` | The adapter chooses the safest native state location unless external state is explicit. |
| `shape.parse_json[]` | `drop_source` | `false` | Parsing JSON does not remove source payloads unless requested. |
| `shape.flatten` | `enabled` | `false` | Flattening is opt-in because it changes column shape. |
| `shape.flatten` | `separator` | `_` | Stable default for generated flattened column names. |
| `shape.flatten` | `max_depth` | `10` | Bounded recursive flattening. |
| `shape.arrays[]` | `mode` | `keep` | Arrays are preserved unless a cardinality-changing behavior is explicit. |
| `shape.arrays[]` | `allow_cartesian` | `false` | Prevents accidental row multiplication. |
| `shape` | `allow_cardinality_change_on_bronze` | `false` | Bronze keeps raw shape unless the contract allows cardinality changes. |
| `transform.standardize.*` | `trim`, `lower`, `upper`, `normalize_whitespace`, `empty_as_null` | `false` | String cleanup is explicit. |
| `transform.deduplicate.order_by[]` | `direction` | `desc` | Deterministic default for ordered deduplication. |
| `transform.custom` | `parameters` | `{}` | Custom treatment receives no parameters unless declared. |
| `quality_rules.expressions[]` | `severity` | `quarantine` | Portable SQL expression failures are isolatable by default. |
| `quality_rules.custom.*` | `severity` | `abort` | Adapter/custom rule failures are fail-closed unless explicitly downgraded. |
| `quality_rules` | `accepted_values`, `max_null_ratio`, `custom` | `{}` | Empty quality maps mean no implicit rules. |
| `quality_rules` | `expressions` | `[]` | No expression checks are invented. |
| `operations` | `alert_on_failure` | `false` | Alert routing is explicit. |
| `operations` | `alert_on_quality_fail` | `false` | Quality alert routing is explicit. |
| `operations` | `tags` | `{}` | No operational tags are invented. |
| `operations` | `ownership` | `{}` | Ownership metadata remains explicit unless project defaults provide it. |
| `annotations` | `policy` | `warn` | Annotation/governance drift is visible without blocking ingestion by default. |
| `annotations.table` | `tags` | `{}` | No catalog tags are invented. |
| `annotations.columns.*` | `tags` | `{}` | No column tags are invented. |
| `annotations.columns.*.pii` | `enabled` | `true` | If a PII block is declared, it means PII is present unless disabled. |
| `annotations.columns.*.pii` | `type` | `unknown` | Unknown PII is explicit and reviewable. |
| `annotations.columns.*.pii` | `sensitivity` | `internal` | Conservative default for declared PII. |
| `access.access_policy` | `mode` | `apply` | Declared access policy should be applied unless review/dry-run mode is explicit. |
| `access.access_policy` | `on_drift` | `warn` | Unmanaged drift is surfaced without destructive changes. |
| `access.access_policy` | `revoke_unmanaged` | `false` | The adapter does not revoke privileges unless explicitly allowed. |
| `access` | `grants`, `row_filters`, `column_masks` | `[]` | No security policy is invented. |
| `execution.window` | `stop_on_failure` | `true` | Windowed execution stops after a failed window. |
| `execution.catchup` | `enabled` | `false` | Catchup runs are opt-in. |
| `execution.catchup` | `stop_on_failure` | `true` | Catchup execution stops after a failed slice. |
| `environment` | `runtime`, `deployment`, `artifacts`, `evidence`, `secrets`, `defaults`, `capabilities`, `parameters` | empty maps | Environment files provide only the adapter context explicitly declared by the project. |

## Project Default Resolver

`project.yaml.defaults` is a separate deterministic resolver. It can fill
omitted contract values before semantic validation and records every added
field in `defaults.decisions[]`.

The supported resolver keys, adapter override behavior and deterministic
inferences are documented in
[Project YAML Defaults Reference](../project-yaml.md#defaults-reference).

## Adapter Runtime Defaults

Adapters may default native runtime knobs when the default is documented and
does not change contract semantics.

| Adapter | Field | Default |
| --- | --- | --- |
| Databricks | evidence catalog/schema | `main.ops` when no environment is provided. |
| Databricks | workspace path | `/Workspace/ContractForge`. |
| Databricks | bundle target | environment name, defaulting to `dev`. |
| AWS | Glue version | `4.0`. |
| AWS | worker type | `G.1X`. |
| AWS | workers | `2`. |
| AWS | timeout | `60` minutes. |
| AWS | retries | `0`. |
| AWS | runtime mode | `library_runner`. |
| AWS | job bookmarks | inferred from source semantics unless explicitly configured. |

## Must Stay Explicit

These values must not be invented by the core or AI:

- source location, table, query, endpoint and dataset-specific overrides;
- target table name;
- write modes other than the conservative append default;
- merge keys, SCD keys and hash column policy for large tables;
- schema evolution policy when strictness matters;
- quality rules and quality enforcement policy;
- access grants, row filters and masks;
- owner, SLA, criticality and runbook metadata;
- adapter selector when an environment file is used;
- AWS artifact S3 URI, Iceberg warehouse, Glue role ARN and wheel location;
- Databricks workspace/profile/cluster/warehouse identifiers when required;
- secrets and credentials.

## Generator Policy

Generated examples should omit adapter knobs that already have documented
adapter defaults. Generated environments should keep review placeholders only
for deployment boundaries that cannot be inferred safely.

For AWS, this means the generator keeps:

- `artifacts.uri`;
- `parameters.aws.iceberg.warehouse`;
- `parameters.aws.dependencies.extra_py_files`;
- `parameters.aws.glue_job.role_arn`.

It omits Glue worker size, worker count, timeout, retries and job-bookmark
settings unless the user explicitly asks for them.
