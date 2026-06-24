# Snowflake Stabilization Matrix

## Purpose

This spec defines the release gate for stabilizing the `contractforge-snowflake`
adapter. It is not a roadmap of possible Snowflake features. It is the checklist
that decides whether the Snowflake adapter can be called stable for the supported
surface.

The target is `snowflake_sql_warehouse`:

- Snowflake SQL warehouse runtime;
- Snowflake native tables;
- Snowflake database/schema cataloging;
- optional governance via tags, comments, row access policies and masking policies;
- ContractForge evidence tables persisted as Snowflake control tables.

The adapter must preserve core semantics. If a Snowflake runtime cannot preserve
a contract behavior, the planner or renderer must return `REVIEW_REQUIRED`,
`SUPPORTED_WITH_WARNINGS` or `UNSUPPORTED`. It must not silently downgrade the
contract.

## Stabilization Scope

The stable candidate scope is intentionally smaller than the full Snowflake
thesis.

| Area | Stable candidate scope | Out of scope for stable candidate |
| --- | --- | --- |
| Sources | `table`, `view`, `sql`, bounded `rest_api` with optional Snowflake-scoped secret aliases, `staged_files` with CSV, JSON and Parquet named file formats | `autoloader`, `kafka`, `copy_into`, Snowpipe, Streams, unmanaged external stages |
| Write modes | `append`, `overwrite`, `upsert`, `hash_diff_upsert` | historical equivalence, snapshot soft delete |
| Quality | abort, warn, row-level quarantine, `not_null`, `required_columns`, `accepted_values`, `min_rows`, `unique_key`, `max_null_ratio`, row-level expressions, case-insensitive matching for Snowflake metadata aliases | Data Metric Functions integration |
| Preparation | SQL-compatible casts, derives, standardization, filters, deterministic deduplicate | Complex nested shapes, array explosions, unsafe bronze operations |
| Schema policy | additive only, strict, permissive via `INFORMATION_SCHEMA.COLUMNS` | Automatic column evolution policies |
| Evidence | runs, errors, quality, quarantine, schema changes, state, annotations, access, operations, lineage, explain, cost | Alternate evidence stores |
| Governance | Table/column comments, tag SQL with validate-only mode, row access policy SQL, masking policy SQL, destructive revoke gating | Automatic consumer-engine guarantees for row filters and column masks |
| Deployment | Dry-run validation, publish-to-stage, hosted procedure execution, `CREATE OR REPLACE TASK` graph deployment, live project run/wait and cleanup when task/procedure grants exist | Long-running production scheduling operations beyond the declared project task graph |
| Cost | Query history reconciliation, query attribution signals, pending/latency handling | Real-time cost dashboards |
| Lineage | Immediate lineage and explain evidence, delayed `ACCESS_HISTORY` reconciliation | Real-time lineage streaming |

## Required Test Projects

The Snowflake adapter cannot be stabilized from renderer tests alone. These
scenarios run through `contractforge-snowflake` commands against a real
Snowflake account.

| Project | Source | Main purpose | Required result |
| --- | --- | --- | --- |
| `smoke` | Generated test sources | Append, overwrite, quarantine, upsert, hash-diff full lifecycle | Five contracts complete successfully with matching control evidence |
| `smoke-failure-paths` | Controlled bad contracts | Error evidence, failed-run evidence, redaction, missing source, quality abort, strict schema | Failures produce redacted evidence without exposing secrets |
| `smoke-stage-publish` | Internal stage | Stage publish, artifact reload, staged contract execution | Published bundle loads and runs from `@stage` |
| `smoke-procedure` | Internal stage + procedure | Procedure deployment, staged ZIP imports, procedure call | Procedure deploys and runs one contract |
| `smoke-task-graph` | Procedure + tasks | Task graph deployment, root task execution, task history polling | Tasks deploy and execute through runner procedure |
| `tmdb-authenticated-rest` | Snowflake secret + external access integration | Authenticated bounded REST, secret alias resolution, task graph lifecycle, quality checks | Five bronze-to-gold tasks complete through hosted procedure execution |

Hash-diff scenarios must declare `merge_keys` and a hash strategy. The Snowflake
adapter validates null and duplicate merge keys before executing the write. Hash
computation uses Snowflake's `HASH` function over non-merge, non-excluded
columns.

## Release Gates

| Gate | Requirement | Status values |
| --- | --- | --- |
| G0 local suite | Unit and render tests pass | `PASS`, `FAIL` |
| G1 render compile | Smoke contracts render valid Snowflake SQL without syntax errors | `PASS`, `FAIL` |
| G2 publish flow | Artifacts publish to Snowflake internal stage and reload correctly | `PASS`, `FAIL` |
| G3 success runtime | Smoke contracts execute successfully through connector-backed runner | `PASS`, `FAIL` |
| G4 failure runtime | Failure matrix writes redacted error and failed-run evidence | `PASS`, `FAIL` |
| G5 control audit | Evidence tables match expected counts and statuses after smoke runs | `PASS`, `FAIL` |
| G6 lineage | Immediate lineage and explain evidence is written; `ACCESS_HISTORY` reconciliation handles pending/latency | `PASS`, `FAIL` |
| G7 cost | Query history reconciliation probes structured query tags and records cost signals | `PASS`, `FAIL` |
| G8 governance | Comments apply correctly; tag validate-only evidence matches expected grants | `PASS`, `FAIL` |
| G9 procedure | Snowpark procedure deploys and executes with staged ZIP library imports | `PASS`, `BLOCKED` |
| G10 task graph | Tasks deploy and execute through runner procedure | `PASS`, `FAIL` |
| G11 parity | Snowflake/Databricks/AWS contract differences are documented and minimal | `PASS`, `REVIEW_REQUIRED`, `FAIL` |
| G12 docs | Snowflake user docs, specs and site reflect tested behavior | `PASS`, `FAIL` |
| G13 lifecycle | Smoke test objects have a documented, non-destructive cleanup plan | `PASS`, `FAIL` |

The adapter is not stable until all non-blocked gates are `PASS` except
explicitly accepted `REVIEW_REQUIRED` parity items. Blocked gates require a
documented unblock plan.

## Stabilization Tracker

| Item | Current status | Notes |
| --- | --- | --- |
| Local Snowflake adapter unit tests | `PASS` | Focused Snowflake suite: 175 passed. Full suite: 1421 passed, 2 known AWS failures not related to Snowflake. |
| Smoke contract render compile | `PASS` | Minimal smoke dry-run validated all contracts render SQL without syntax errors. |
| Stage publish smoke | `PASS` | `smoke-stage-publish` created temporary internal stage, published library-runner bundle, reloaded artifacts from `@stage` and ran staged contract. |
| Minimal success runtime | `PASS` | All five contracts (append, overwrite, quarantine, upsert, hash-diff) completed successfully through connector-backed runner with evidence. |
| Failure-path runtime | `PASS` | Missing source, quality abort and strict schema failures produced redacted error evidence without exposing connection secrets. |
| Control-table audit | `PASS` | Smoke verification confirmed run, error, quality, quarantine, schema change, state, annotation, access, operations, lineage, explain and cost evidence rows. |
| Lineage evidence | `PASS` | Immediate lineage wrote 5 rows to `ctrl_ingestion_lineage`. `EXPLAIN USING TEXT` wrote 5 rows to `ctrl_ingestion_explain`. `ACCESS_HISTORY` reconciliation returned `PENDING` with 0 rows, matching Account Usage latency. |
| Cost reconciliation | `PASS` | Query history reconciliation probed structured `QUERY_TAG` run ids and returned `PENDING` for delayed Account Usage. Runtime query tags store parseable JSON with unquoted target names. |
| Governance comments and tags | `PASS` | Table/column comments applied; tag validate-only evidence recorded with correct grants. |
| Schema policy | `PASS` | `INFORMATION_SCHEMA.COLUMNS` inspection with connector metadata fallback; additive column smoke and strict failure smoke passed. |
| Quality runtime | `PASS` | Pass, quarantine and abort scenarios all produced correct evidence and propagated `quality_status` into run records. |
| Quality alias matching | `PASS` | Runtime quality checks resolve contract aliases against Snowflake source metadata with exact matching first and Snowflake-safe case-insensitive matching for unquoted uppercase SQL aliases. |
| State idempotency and locks | `PASS` | Watermark candidate calculation, previous watermark filtering, idempotent replay skip, lock acquire and release tested. |
| Procedure deployment | `PASS` | Hosted Snowpark procedure deployed with staged ZIP imports for the core/adapter libraries, called the stable runner, and live smoke wrote 2 rows. |
| Task graph deployment | `PASS` | Live smoke deployed the graph, executed the root task, waited for root/dependent task success and cleaned up smoke artifacts. Redeploys suspend existing task definitions before `CREATE OR REPLACE TASK`. |
| Authenticated REST secrets | `PASS` | TMDB task graph run resolved `{{ secret:snowflake/<alias> }}` through `parameters.snowflake.secrets` and Snowflake procedure `SECRETS` bindings without inline credentials. |
| Staged file source parity | `PASS` | CSV positional projections, JSON payload/typed projections and Parquet typed projections with named file formats validated. Unsafe paths and column expressions rejected. |
| Preparation registry | `PASS` | Metadata projection, filters, casts, derives, standardization and deterministic deduplicate validated with live smoke. |
| Write mode registry | `PASS` | Append, overwrite, upsert and hash-diff split into independent registry modules with prewrite merge-key validation. |
| Cleanup lifecycle | `PASS` | `smoke --execute --execute-cleanup` removes all `CF_SMOKE_*` objects. `cleanup-plan` produces non-destructive DROP IF EXISTS SQL. |
| Cross-platform real source validation | `PASS` | TMDB authenticated REST project completed on Snowflake task graph alongside AWS, Fabric and GCP validations. Databricks TMDB was blocked by workspace DNS for `api.themoviedb.org`, while Databricks USGS REST bronze-to-gold validation passed separately. |
| Docs/site update | `PASS` | Snowflake adapter operations guide, parity execution plan, capability parity spec and stabilization matrix are published and now document secret aliases, quality alias matching and task graph lifecycle. |

## Blocked Gates Unblock Plan

The Snowflake access-policy smoke is blocked by the account feature response
`Unsupported feature 'ROW ACCESS POLICY'`. That policy-enforcement claim is
explicitly excluded from stable-final for accounts where the native policy
features are unavailable. Continuous ingestion is also excluded from
stable-final until a separate runtime/evidence mapping is implemented.
Historical/snapshot semantics are excluded from stable-final until parity
evidence exists.

## Machine-Readable Status

```bash
contractforge-snowflake stabilization-report
```

For the current release, the intended classification is
`STABLE_SUPPORTED_SURFACE` with `supported_surface_ready: true` and
`stable_final: true`. Continuous ingestion, account-feature-dependent policy
enforcement and historical/snapshot soft delete are excluded from stable-final, and
the reference hash-diff benchmark is validated.
