# AWS Stable-Surface Criteria

## Purpose

This document defines the verifiable conditions for treating
`contractforge-aws` as stable for its supported `aws_glue_iceberg` surface.

The gate is intentionally scoped. It does not claim that every ContractForge
semantic supported by the Databricks reference adapter is production-certified
on AWS. It says that the AWS Glue/Iceberg surface documented here has passed
planning, rendering, deployment, runtime, evidence, audit, lifecycle and
parity checks without contract-specific workarounds.

The detailed evidence matrix lives in
[aws-stabilization-matrix.md](aws-stabilization-matrix.md). This file is the
release checklist that converts those results into a stability decision.

## Scope

The stable AWS surface is:

- AWS Glue Spark runtime;
- Apache Iceberg tables on Amazon S3;
- AWS Glue Data Catalog metadata;
- ContractForge evidence as Iceberg/Athena-readable control tables;
- Lake Formation grants and review/apply helpers where equivalence is proven
  or explicitly review-required.

Stable source families:

- S3/object-storage files and portable file formats;
- `incremental_files` using Glue bookmarks where eligible;
- JDBC/Postgres through Glue JDBC paths;
- bounded `rest_api` and `http_file` paths with SSRF and redirect guards;
- the validated AWS MSK and Azure Event Hubs Kafka available-now streaming paths.

Stable write modes:

- `append`;
- `overwrite`;
- `upsert`;
- `hash_diff_upsert` as `SUPPORTED_WITH_WARNINGS`; the reference benchmark is
  validated, while workload-specific SLA claims require attached evidence.

Excluded or workload-specific boundaries:

- `historical`;
- `snapshot_reconcile_soft_delete`;
- arbitrary Lake Formation row-filter and column-mask expressions beyond the
  reviewed consumer matrix;
- non-MSK Kafka/Event Hubs compatibility provider claims beyond the validated
  paths.

## Inherited Preconditions

These repository invariants must pass before AWS stability can be evaluated.

| Precondition | Verification |
| --- | --- |
| Core has no platform imports | `tests/test_core_platform_independence.py` |
| Adapters do not import each other | `tests/test_adapter_independence.py` |
| Public packaging shape is stable | `tests/test_publication_packaging.py` |
| Declared package versions match metadata | `tests/test_package_version.py` |
| AWS architecture remains adapter-owned | `tests/test_aws_architecture.py` |
| AWS capability docs stay in sync | `tests/test_aws_capability_parity_docs.py` |
| CI builds the AWS adapter wheel | `.github/workflows/ci.yml` package/full scopes |

If any precondition fails, AWS stability evaluation is paused.

## Stability Criteria

### 1. Local And Render Gates

**What must hold.** Unit, rendering, architecture, packaging and generated-code
compile gates pass for AWS.

**How to verify.** Run:

```bash
uv run pytest tests/test_aws_*.py tests/test_adapter_source_support.py tests/test_adapter_extension_docs.py tests/test_publication_packaging.py tests/test_package_version.py
uv run contractforge-aws deploy-project examples/real-world/supabase-jdbc-medallion/project.yaml --dry-run --summary-only
```

**Status.** `met`.

### 2. Runtime Success Projects

**What must hold.** The real validation projects run through ContractForge
commands only, with no Glue Studio edits and no handwritten runtime code.

Required projects:

- `aws_supabase_jdbc_medallion`;
- `aws_usgs_rest_medallion`;
- `aws_s3_file_medallion`;
- `aws_incremental_files`;
- `aws_eventhubs_kafka_available_now`;
- `aws_msk_kafka_available_now`.

Each project must create/write target Iceberg tables, populate
`ctrl_ingestion_runs`, record quality/state/metadata/lineage where applicable,
and preserve the expected row counts.

**How to verify.** Use the project-level AWS CLI flow:

```bash
contractforge-aws deploy-project <project.yaml> --run --wait --record-cost-evidence --audit-evidence
```

**Status.** `met`.

### 3. Failure Evidence

**What must hold.** Controlled failures produce failed run evidence and redacted
error evidence while preserving the original runtime failure.

Required cases:

- invalid or missing credentials;
- blocked REST/HTTP targets;
- quality abort;
- invalid merge key;
- missing source path;
- target permission failure where available.

**How to verify.** Run the AWS failure-path project with
`--accept-expected-failures` and audit `ctrl_ingestion_runs`,
`ctrl_ingestion_errors` and `ctrl_ingestion_quality`.

**Status.** `met`.

### 4. Evidence Audit

**What must hold.** Athena audit queries over canonical control tables pass for
all real validation projects.

Required tables:

- `ctrl_ingestion_runs`;
- `ctrl_ingestion_errors`;
- `ctrl_ingestion_quality`;
- `ctrl_ingestion_quarantine`;
- `ctrl_ingestion_schema_changes`;
- `ctrl_ingestion_metadata`;
- `ctrl_ingestion_lineage`;
- `ctrl_ingestion_access`;
- `ctrl_ingestion_operations`;
- `ctrl_ingestion_cost`;
- `ctrl_ingestion_state`;
- `ctrl_ingestion_locks`.

**How to verify.**

```bash
contractforge-aws audit-evidence --database <evidence_database> --athena-output-location <s3-uri>
```

**Status.** `met`.

### 5. Platform Parity

**What must hold.** Shared ContractForge contract intent produces the same
logical results on Databricks, AWS and Snowflake for the supported shared
surface. AWS-specific differences are limited to source binding, environment,
Iceberg warehouse settings and accepted review boundaries.

**How to verify.**

```bash
uv run python -m tools.platform_parity.report
uv run pytest tests/test_platform_parity_contracts.py
```

Real E2E evidence from the same contracts on all three platforms should be
attached to release notes or the release evidence manifest at
[../reports/aws-stable-surface-evidence.json](../reports/aws-stable-surface-evidence.json).

**Status.** `met` for the supported surface.

### 6. Security And Runtime Boundaries

**What must hold.**

- The core imports no AWS SDKs.
- The base AWS package does not eagerly import `boto3`.
- Rendered artifacts do not contain plaintext secrets.
- Runtime secret resolution uses Secrets Manager or platform-owned mechanisms.
- REST/HTTP paths reject unsafe schemes, private hosts and redirects.
- The stable Glue library runner validates rendered runtime code before
  in-process execution.

**How to verify.** Run AWS architecture/security tests and keep AST validation
tests around `runtime/library_runner.py` mandatory.

**Status.** `met`.

## Open Production-Certification Boundaries

The stable supported surface is ready and `stable_final` is true for the
documented AWS Glue/Iceberg claim. Broader claims remain explicit exclusions or
workload-specific warnings:

| Boundary | Current decision | Required closure |
| --- | --- | --- |
| `hash_diff_upsert` workload-specific performance | `SUPPORTED_WITH_WARNINGS` | Reference benchmark passed; attach workload-specific evidence before claiming a production SLA for a new hash-diff contract. |
| Non-MSK Kafka/Event Hubs compatibility providers | `EXCLUDED_FROM_STABLE_FINAL` | Provider-specific offset/checkpoint matrix beyond the validated AWS MSK and Azure Event Hubs Kafka paths. |
| Lake Formation row filters and masks | `EXCLUDED_FROM_STABLE_FINAL` | Consumer-engine matrix passed for Athena and Glue Spark; arbitrary contract expressions still require review before workload-specific claims. |
| `historical` and `snapshot_reconcile_soft_delete` | `EXCLUDED_FROM_STABLE_FINAL` | Documented stable-scope exclusion until runtime implementation and E2E equivalence evidence are attached. |

These are not hidden defects. They are explicit limits on what the stable AWS
surface claims.

## Machine-Readable Gate

Use:

```bash
contractforge-aws stabilization-report
```

Expected stable-surface result:

- `classification = STABLE_SUPPORTED_SURFACE`;
- `supported_surface_ready = true`;
- `stable_final = true` for the documented stable-final claim.
- `evidence_manifest = docs/reports/aws-stable-surface-evidence.json`.

Use `--strict-final` in workflows that must enforce the documented stable-final
claim.
