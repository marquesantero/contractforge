# Snowflake Stable-Surface Criteria

## Purpose

This document defines the verifiable conditions for treating
`contractforge-snowflake` as stable for its supported
`snowflake_sql_warehouse` surface.

The gate is intentionally scoped. It does not claim that every ContractForge
semantic supported by the Databricks reference adapter is production-certified
on Snowflake. It says that the Snowflake SQL warehouse surface documented here
has passed planning, rendering, stage publication, hosted-procedure runtime,
evidence, audit, lifecycle and parity checks without contract-specific
workarounds.

The detailed evidence matrix lives in
[snowflake-stabilization-matrix.md](snowflake-stabilization-matrix.md). This
file is the release checklist that converts those results into a stability
decision.

## Scope

The stable Snowflake surface is:

- Snowflake SQL warehouse runtime;
- Snowflake native tables;
- Snowflake database/schema cataloging;
- ContractForge evidence as Snowflake control tables;
- hosted Snowpark procedure library runner with staged ZIP imports;
- governance through comments, tags and validate/apply helpers where
  equivalence is proven or explicitly review-required.

Stable source families:

- `table` and `view`;
- `sql` / `query`;
- `staged_files` with CSV, JSON and Parquet using named Snowflake file
  formats.

Stable write modes:

- `append`;
- `overwrite`;
- `upsert`;
- `hash_diff_upsert` as `SUPPORTED_WITH_WARNINGS`; the reference production
  benchmark is validated, and workload-specific SLA evidence is still required
  for new production claims.

Review-required boundaries:

- Snowpipe, Streams, Snowpipe Streaming and Kafka connector ingestion
  surfaces;
- Data Metric Functions integration;
- `historical`;
- `snapshot_reconcile_soft_delete`;
- row access policy or masking policy enforcement on accounts where the policy
  features are unavailable.

## Inherited Preconditions

These repository invariants must pass before Snowflake stability can be
evaluated.

| Precondition | Verification |
| --- | --- |
| Core has no platform imports | `tests/test_core_platform_independence.py` |
| Adapters do not import each other | `tests/test_adapter_independence.py` |
| Public packaging shape is stable | `tests/test_publication_packaging.py` |
| Declared package versions match metadata | `tests/test_package_version.py` |
| Snowflake default import keeps runtime SDKs optional | `tests/test_snowflake_adapter.py` |
| Snowflake docs and status report stay in sync | `tests/test_snowflake_stability_docs.py` |
| CI builds the Snowflake adapter wheel | `.github/workflows/ci.yml` package/full scopes |

If any precondition fails, Snowflake stability evaluation is paused.

## Stability Criteria

### 1. Local And Render Gates

**What must hold.** Unit, rendering, architecture, packaging and generated SQL
compile gates pass for Snowflake.

**How to verify.** Run:

```bash
uv run pytest tests/test_snowflake_*.py tests/test_adapter_independence.py tests/test_publication_packaging.py tests/test_package_version.py
uv run contractforge-snowflake smoke --database CONTRACTFORGE_TEST --schema PUBLIC
```

**Status.** `met`.

### 2. Runtime Success Projects

**What must hold.** The real validation projects run through ContractForge
commands only, with no handwritten runtime SQL outside the adapter.

Required projects:

- `snowflake_smoke_minimal`;
- `snowflake_smoke_stage_publish`;
- `snowflake_smoke_procedure`;
- `snowflake_usgs_rest_medallion`.

Each project must create/write target Snowflake tables, populate
`ctrl_ingestion_runs`, record quality/state/metadata/lineage where applicable,
and preserve the expected row counts.

**How to verify.** Use the Snowflake CLI smoke and project flows:

```bash
contractforge-snowflake smoke --connect-options <connection.yaml> --execute --execute-cleanup
contractforge-snowflake smoke-stage-publish --connect-options <connection.yaml> --execute --execute-cleanup
contractforge-snowflake smoke-procedure --connect-options <connection.yaml> --execute --execute-cleanup
```

**Status.** `met`.

### 3. Failure Evidence

**What must hold.** Controlled failures produce failed run evidence and redacted
error evidence while preserving the original runtime failure.

Required cases:

- missing source;
- quality abort;
- strict schema failure;
- redaction of connection secrets in diagnostics.

**How to verify.** Run the Snowflake failure-path smoke with cleanup enabled
and audit `ctrl_ingestion_runs`, `ctrl_ingestion_errors` and
`ctrl_ingestion_quality`.

**Status.** `met`.

### 4. Evidence Audit

**What must hold.** Canonical control tables are written in Snowflake and audit
counts match the expected smoke results.

Required tables:

- `ctrl_ingestion_runs`;
- `ctrl_ingestion_errors`;
- `ctrl_ingestion_quality`;
- `ctrl_ingestion_quarantine`;
- `ctrl_ingestion_schema_changes`;
- `ctrl_ingestion_state`;
- `ctrl_ingestion_annotations`;
- `ctrl_ingestion_access`;
- `ctrl_ingestion_operations`;
- `ctrl_ingestion_lineage`;
- `ctrl_ingestion_explain`;
- `ctrl_ingestion_cost`.

**Status.** `met`.

### 5. Platform Parity

**What must hold.** Shared ContractForge contract intent produces the same
logical results on Databricks, AWS and Snowflake for the supported shared
surface. Snowflake-specific differences are limited to source binding,
environment, native table namespace, Snowflake governance settings and accepted
review boundaries.

**How to verify.**

```bash
uv run python -m tools.platform_parity.report
uv run pytest tests/test_platform_parity_contracts.py
```

Real E2E evidence from the same contracts on all three platforms should be
attached to release notes or the release evidence manifest at
[../reports/snowflake-stable-surface-evidence.json](../reports/snowflake-stable-surface-evidence.json).

**Status.** `met` for the supported surface.

### 6. Security And Runtime Boundaries

**What must hold.**

- The core imports no Snowflake clients.
- The base Snowflake package does not eagerly import Snowflake connector or
  Snowpark SDK modules.
- Rendered artifacts do not contain plaintext secrets.
- Runtime connection options are allowlisted.
- Stage artifact paths reject unsafe traversal.
- Failure and reconciliation warnings redact sensitive values before evidence
  writes or CLI output.

**Status.** `met`.

## Open Production-Certification Boundaries

The stable supported surface is ready. `stable_final` is true for the documented
claim because broader unavailable or unimplemented features are explicitly
excluded:

| Boundary | Current decision | Required closure |
| --- | --- | --- |
| `hash_diff_upsert` workload-specific performance | `SUPPORTED_WITH_WARNINGS` | Reference benchmark passed; attach workload-specific evidence before claiming a production SLA for a new hash-diff contract. |
| Row access policies and masking policies | `EXCLUDED_FROM_STABLE_FINAL` | The connected account returns `Unsupported feature 'ROW ACCESS POLICY'`; rerun and promote only on an account where native policy features are available. |
| Continuous ingestion | `EXCLUDED_FROM_STABLE_FINAL` | Snowpipe, Streams, Snowpipe Streaming and Kafka connector ingestion require a separate connector/runtime mapping with recovery and evidence semantics. |
| `historical` and `snapshot_reconcile_soft_delete` | `EXCLUDED_FROM_STABLE_FINAL` | Documented stable-scope exclusion until runtime implementation and E2E equivalence evidence are attached. |

These are not hidden defects. They are explicit limits on what the stable
Snowflake surface claims.

## Machine-Readable Gate

Use:

```bash
contractforge-snowflake stabilization-report
```

Expected stable-surface result:

- `classification = STABLE_SUPPORTED_SURFACE`;
- `supported_surface_ready = true`;
- `stable_final = true` for the documented stable-final claim;
- `evidence_manifest = docs/reports/snowflake-stable-surface-evidence.json`.

Use `--strict-final` in workflows that must enforce the documented stable-final
claim and exclusions.
