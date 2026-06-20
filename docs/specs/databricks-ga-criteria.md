# Databricks Adapter GA Criteria

## Purpose

This document defines the verifiable conditions under which
`contractforge-databricks` is promoted from `Development Status :: 3 - Alpha`
to General Availability (`Development Status :: 5 - Production/Stable`,
package version `1.0.0`).

It is a gate, not a description of features. The implemented scope is
documented in [databricks-adapter.md](databricks-adapter.md). The functional
parity matrix lives in
[databricks-contractforge-parity.md](databricks-contractforge-parity.md).
This file complements those by listing the **must-be-true** conditions and the
**how to verify** each one.

A criterion is considered met only when the verification step is implemented,
running in CI, and green for at least four consecutive weekly cycles after the
criterion is added.

## Scope Of This Gate

This gate covers the `contractforge-databricks` package only. AWS, Snowflake
and AI packages have their own gates. Core (`contractforge-core`) GA is bound
to Databricks GA because the Databricks adapter is the reference
implementation: when Databricks reaches `1.0.0`, core is promoted to `1.0.0`
in the same release window.

This gate does not require:

- adapters other than Databricks to reach GA;
- Lakeflow AUTO CDC to be runtime-validated for current-state (only historical is in scope);
- workspace mutation through the `contractforge-databricks` CLI (deployment
  remains a customer-owned concern);
- a GUI;
- continuous streaming. Only available-now / bounded-stream behavior is in
  scope, consistent with the adapter spec.

## Inherited Preconditions

The following must be green before any GA criterion is evaluated. These are
not GA-specific; they are repository invariants.

| Precondition | Verification |
| --- | --- |
| Core has no platform imports | `tests/test_core_platform_independence.py` |
| Adapters do not import each other | `tests/test_adapter_independence.py` |
| AI module has no adapter or SDK top-level imports | `ai/tests/test_architecture_boundaries.py` |
| Public packaging shape is stable | `tests/test_publication_packaging.py` |
| Declared package versions match `pyproject.toml` | `tests/test_package_version.py` |
| Databricks adapter spec is consistent | `tests/test_databricks_contractforge_parity_docs.py` |
| CI install-test matrix passes on Python 3.10/3.11/3.12 × Linux/Windows | `.github/workflows/ci.yml` `install-matrix` job |

If any precondition is red, GA evaluation is paused. Fix the precondition
first; do not waive it.

## GA Criteria

Each criterion below has three parts: **what must hold**, **how to verify**
and **status**. Status is one of `not_started`, `in_progress`, `met` or
`waived` (with reason). Waivers are case-by-case, never blanket.

### 1. Write Modes — End-To-End Execution

**What must hold.** All six portable write modes execute end-to-end against
a real Databricks workspace with the supported engine selected by
`write_modes/strategy.py:choose_write_strategy`:

- `append` → Delta append (native)
- `overwrite` → Delta overwrite (native)
- `upsert` → Databricks SQL MERGE (native)
- `hash_diff_upsert` → ContractForge hash-diff Delta MERGE (algorithm)
- `historical` → ContractForge historical Delta MERGE (algorithm); Lakeflow
  AUTO CDC remains adapter-rendered but is not on the GA execution gate
- `snapshot_reconcile_soft_delete` → ContractForge snapshot soft-delete Delta MERGE
  (algorithm)

Each successful run produces:

- a Delta target table at the contract's three-part UC name;
- a row in `ctrl_ingestion_runs` with `status = 'SUCCEEDED'`;
- normalized write metrics
  (`rows_inserted` / `rows_updated` / `rows_deleted` / `rows_expired` /
  `rows_affected`) as defined in
  [databricks-adapter.md §Write Metrics](databricks-adapter.md);
- stage durations recorded in `stage_durations_json`.

**How to verify.** Live workspace smoke job (see section 11) runs one
fixture contract per write mode. Existing offline tests
(`tests/test_databricks_delta_basic_execution.py`,
`tests/test_databricks_sql_merge_execution.py`,
`tests/test_databricks_hash_diff_execution.py`,
`tests/test_databricks_scd2_execution.py`,
`tests/test_databricks_snapshot_execution.py`,
`tests/test_databricks_replace_partitions_execution.py`) stay green in
PR CI.

**Out of scope for GA.** `custom:*` write modes ship as a stable extension
point but are not on the GA gate; consumers carry their own coverage.

**Status.** `not_started`.

### 2. Source Connectors — Declared Status Honored

**What must hold.** Every source declared by
`sources/support.py:list_databricks_source_support` behaves according to its
declared status:

| Status declared | GA requirement |
| --- | --- |
| `SUPPORTED` | One live workspace fixture per source family runs end-to-end (read + write to Delta) |
| `REVIEW_REQUIRED` | Renderer emits the expected review artifact and a planning warning; no silent execution |
| `UNSUPPORTED` | Adapter returns a planning blocker; no artifact is emitted |

Source families covered for GA:

- `incremental_files` (Auto Loader)
- `jdbc` family (`postgres`, `mysql`/`mariadb`, `sqlserver`, `oracle`,
  `redshift`)
- catalog (`table`, `view`, `sql`, `delta_table`, `iceberg_table`)
- `http_file` / `http_csv` / `http_json` / `http_text`
- `rest_api` (bounded resolver only)
- bounded streams (`kafka_bounded`, `eventhubs_bounded`)
- `delta_share`
- batch file/object-storage (`csv`, `json`/`jsonl`/`ndjson`, `parquet`,
  `delta`, `orc`, `text`, `avro`, `xml`, `s3`, `adls`, `azure_blob`, `gcs`)
- `native_passthrough` (REVIEW_REQUIRED artifact only)

Driver responsibilities (e.g. Oracle JDBC driver, XML format jar) remain a
deployment concern and are explicitly out of scope for the adapter gate, but
the workspace used by the smoke job must provide them so the fixtures can
execute.

**How to verify.** Live smoke runs one fixture per family. Offline tests
(`tests/test_databricks_*_source.py`,
`tests/test_databricks_source_*.py`,
`tests/test_databricks_runtime_sources.py`) stay green.

**Status.** `not_started`.

### 3. Schema Policy — Plan, Apply, Audit

**What must hold.** The three core schema policies behave as specified:

- `additive_only` — additive changes apply; structural breaks fail with
  a blocker; `ctrl_ingestion_schema_changes` records each applied change
- `permissive` — all detected diffs are recorded but not blocked
- `fail` — any detected diff fails the run before write

Schema change records include `change_type`, `column_name`, `previous_type`,
`current_type` and the run id.

**How to verify.** `tests/test_databricks_schema_diff.py`,
`tests/test_databricks_schema_policy.py` and one live smoke per policy
behavior.

**Status.** `not_started`.

### 4. Quality Rules — Rendering, Execution, Quarantine, Evidence

**What must hold.** All seven core quality rule kinds — `required_columns`,
`not_null`, `unique_key`, `accepted_values`, `row_count_minimum`,
`max_null_ratio`, `expression` — execute against Databricks and the result
is recorded:

- `ctrl_ingestion_quality` receives one row per rule per run with
  `status`, `failed_records` and rule metadata;
- `on_quality_fail = fail` aborts the write;
- `on_quality_fail = warn` records the failure and continues;
- `on_quality_fail = quarantine` writes failing rows to the contract's
  quarantine target before the main write proceeds.

**How to verify.** `tests/test_databricks_quality_*.py` and one live smoke
that exercises each `on_quality_fail` branch.

**Status.** `not_started`.

### 5. Governance And Annotations — Apply And Audit

**What must hold.** Unity Catalog SQL is rendered and applied for:

- table comments, column comments, table tags, column tags, aliases, PII
  metadata and deprecation markers (annotations);
- grants, row filters and column masks (access);
- owner review notes.

Behaviors required for GA:

- annotations `policy=ignore|warn|fail` produce the documented outcome
  and audit row in `ctrl_ingestion_annotations`;
- access `mode=ignore|validate_only|apply` produces the documented outcome
  and audit row in `ctrl_ingestion_access`;
- access `on_drift=fail` rejects detected drift when the runner supports
  `query()`;
- access `revoke_unmanaged=true` requires the documented runtime
  confirmation before issuing REVOKE.

**How to verify.** `tests/test_databricks_annotations_sql.py`,
`tests/test_databricks_governance_application.py`,
`tests/test_databricks_governance_log.py`,
`tests/test_databricks_access_audit_sql.py` and one live smoke that flips
each mode.

**Status.** `not_started`.

### 6. Operations Metadata — Recorded

**What must hold.** Operations metadata (criticality, expected frequency,
freshness SLA, alerting flags, runbook URL, ownership, owners, groups,
tags) is recorded into `ctrl_ingestion_operations` when declared, and
returns `NOT_CONFIGURED` when absent.

**How to verify.** `tests/test_databricks_operations_application.py`,
`tests/test_databricks_operations_sql.py` and one smoke fixture with full
operations metadata.

**Status.** `not_started`.

### 7. Evidence Stores — Schemas, DDL, Migration

**What must hold.** All twelve evidence/control tables can be created,
written and additively migrated against a real workspace:

`ctrl_ingestion_runs`, `ctrl_ingestion_errors`, `ctrl_ingestion_quality`,
`ctrl_ingestion_state`, `ctrl_ingestion_locks`,
`ctrl_ingestion_schema_changes`, `ctrl_ingestion_lineage`,
`ctrl_ingestion_streams`, `ctrl_ingestion_annotations`,
`ctrl_ingestion_access`, `ctrl_ingestion_operations`,
`ctrl_ingestion_explain`.

The migration SQL rendered by `state/migrations.py` is idempotent on a
workspace that already has the previous control-table version installed.

**How to verify.** `tests/test_databricks_evidence_ddl.py`,
`tests/test_databricks_evidence_sql.py`,
`tests/test_databricks_control_table_schema_parity.py`,
`tests/test_databricks_state_sql.py` and one live smoke that runs the
migration SQL against a workspace with prior tables installed.

**Status.** `not_started`.

### 8. Lineage — OpenLineage Event Per Run

**What must hold.** For each successful run, the runtime emits an
OpenLineage-compatible record persisted through `ctrl_ingestion_lineage`
with namespace `databricks://<catalog>`, `eventType` matching run outcome
(`COMPLETE` or `FAIL`), input/output schema facets and the output row
count as a data-quality metric facet.

**How to verify.** `tests/test_databricks_lineage.py` and live smoke
emits at least one valid record per write mode fixture.

**Status.** `not_started`.

### 9. Cost Signals — Reportable

**What must hold.** `cost/sql.py:render_operational_cost_query` produces
SQL that runs against the populated evidence tables and returns a
non-empty result set when called with valid `dbu_per_hour`,
`currency_per_dbu` and `currency`.

This is operational cost estimation, not provider billing reconciliation;
that remains explicit non-scope.

**How to verify.** `tests/test_databricks_cost.py` and live smoke runs
the cost query after at least one successful run.

**Status.** `not_started`.

### 10. Parity Scenarios — Validated Live

**What must hold.** All eight scenarios declared in
`adapters/databricks/src/contractforge_databricks/parity/scenarios.py`
have a corresponding live workspace execution that produces the
expected outcome:

- six `must_match` scenarios (3× current-state SQL MERGE, 3× historical Lakeflow AUTO
  CDC) produce metrics that match the ContractForge Delta reference run;
- one `unsupported` scenario
  (`hash_diff_auto_cdc_non_equivalence`) is correctly blocked at
  planning time;
- one `intentional_difference` scenario
  (`snapshot_reconcile_soft_delete_auto_cdc_difference`) is rendered with the
  declared blocker recorded in the run evidence.

**How to verify.** Live smoke job runs the parity harness weekly. Offline
test `tests/test_databricks_parity_catalog.py` continues to enforce the
catalog shape in PR CI.

**Status.** `not_started`.

## Live Workspace Smoke

The GA gate depends on a recurring smoke job. Decisions for the first
release window:

| Item | Decision |
| --- | --- |
| Workspace | The same workspace already used to validate `examples/real-world/supabase-jdbc-medallion` end-to-end on Databricks and AWS. |
| Catalog and schema | Reuses the existing example evidence schema (`cf_supabase_jdbc_e2e_v2_ops`) and target catalog (`workspace`). No new naming. |
| Frequency | Weekly cron (Sunday 06:00 UTC) plus on-demand `workflow_dispatch`. Daily is intentionally out of scope due to compute cost. |
| Trigger workflow | New `.github/workflows/databricks-smoke.yml` (to be authored as part of Phase 1; not yet present). |
| Secrets | `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID` injected as repository secrets; not echoed; never logged. |
| Failure handling | A failing weekly run blocks the next GA review cycle until the run is green or the failure is explicitly waived with a recorded reason. |
| Teardown | The smoke job drops only objects it created in the dedicated schema. Existing example artifacts are preserved. |
| Cost envelope | Documented in the smoke workflow. A run that exceeds the envelope is investigated before the next cycle. |

The smoke workflow runs a fixed test matrix derived from the GA criteria
above. New criteria require both an offline test and a smoke matrix entry
before the criterion can be marked `met`.

## Post-GA Breaking Change Policy

Once `contractforge-databricks` reaches `1.0.0`:

- Public API surface (everything documented in
  [databricks-adapter.md](databricks-adapter.md) and accessible without an
  underscore prefix) follows SemVer.
- Breaking changes require a `2.0.0` bump; no exceptions absent a
  documented security carveout.
- Deprecations land one minor before removal, with a `DeprecationWarning`
  emitted at import or call time. Minimum deprecation window: 90 days.
- Evidence/control table schemas evolve additively. Destructive migrations
  are not allowed in minor versions.
- Extension surfaces under `extensions.databricks.*` follow the
  [adapter parameter policy](adapter-parameter-policy.md) and are governed
  by the same SemVer contract.
- The capability declarations in
  `adapters/databricks/src/contractforge_databricks/capabilities/` form
  part of the public API. Renaming a capability is a breaking change.
- Parity scenarios in
  `adapters/databricks/src/contractforge_databricks/parity/scenarios.py`
  may be added without a bump. Changing an `expectation` value or
  removing a scenario is a breaking change.

The policy is enforced by the existing `tests/test_publication_packaging.py`
checks and by review during release.

## De-GA Criteria

The `1.0.0` status is revoked, and the package returns to `0.x` semantics,
if any of the following becomes true:

- four consecutive weekly smoke runs fail without an accepted waiver;
- a security vulnerability requires a breaking change inside a minor;
- a write mode that was on the GA gate is removed or its semantic
  contract changes;
- core platform isolation is violated (a `contractforge-core` release
  starts importing a platform SDK).

A de-GA event must be recorded in the package CHANGELOG with the
triggering condition cited.

## 1.0.0 Release Checklist

Binary checklist for the actual release tag `v1.0.0-databricks`:

- [ ] All sections 1–10 above marked `met` with green smoke history for
      at least four consecutive weeks.
- [ ] All inherited preconditions green.
- [ ] `pyproject.toml` updated:
      `version = "1.0.0"` and
      `Development Status :: 5 - Production/Stable`.
- [ ] `adapters/databricks/CHANGELOG.md` includes a `[1.0.0]` entry
      that lists the API stability boundary and references this gate
      document.
- [ ] [databricks-adapter.md](databricks-adapter.md) reviewed and any
      drift from implementation reconciled.
- [ ] [databricks-contractforge-parity.md](databricks-contractforge-parity.md)
      reviewed.
- [ ] `docs/specs/api-stability.md` updated to reflect Databricks as a
      stable surface.
- [ ] `README.md` status table for the Databricks adapter changed from
      "Reference implementation" to "GA".
- [ ] `contractforge-core` bumped to `1.0.0` in the same release window;
      `4 - Beta` becomes `5 - Production/Stable`.
- [ ] PyPI release dispatched via `release.yml` with tag
      `v1.0.0-databricks` (and `v1.0.0-core`); install smoke run on
      Python 3.10/3.11/3.12 Linux + Windows; both pages render correctly.
- [ ] Trusted Publisher confirmed active for both packages.
- [ ] Release announced on the project page and in the documentation
      index. AI, AWS and Snowflake adapter pages clearly state they are
      not yet on the GA gate.

## Non-Goals Of This Gate

- GA of `contractforge-aws`, `contractforge-snowflake` or
  `contractforge-ai` (each has its own gate).
- A guarantee that every contract that passes the AWS or Snowflake
  adapter also runs on Databricks; portability remains contract-level,
  not adapter-equivalence.
- Live runtime validation of Lakeflow AUTO CDC current-state, EMR-like custom
  engines, continuous streaming or Fabric / GCP adapters.
- A scheduler or orchestration runtime owned by ContractForge.

## Open Items Before The Gate Is Active

- Workflow `.github/workflows/databricks-smoke.yml` to be authored.
- Cost envelope per smoke cycle to be calibrated against the workspace.
- First real waiver entry to validate the registry format in
  `docs/specs/databricks-ga-waivers.md` if a waiver is ever required.
