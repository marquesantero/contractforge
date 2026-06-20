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
| `idempotency_policy` | `always_run` | Does not silently skip user-requested executions. |
| `source.state.storage` | `adapter_managed` | Lets each adapter use its safest native state when no external state location is declared. |
| `environment.name` | `dev` | Logical environment label only; does not change ingestion semantics. |
| `schedule.timezone` | `UTC` | Portable scheduler default when a schedule is declared. |

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
