# Snowflake Adapter Parity Execution Plan

## Purpose

This is the local commit-by-commit plan for bringing
`contractforge-snowflake` to the same maturity level as the Databricks and AWS
adapters.

The goal is capability and release-discipline parity, not identical file names.
Snowflake should keep a Snowflake-native package shape, but every supported
capability needs the same maturity signals:

1. planner behavior;
2. implementation;
3. CLI surface;
4. unit tests;
5. real-account smoke coverage where the behavior touches Snowflake;
6. docs and examples;
7. evidence/control-table validation.

## Current Baseline

As of the first live local smoke, Snowflake has:

1. planning and publish-bundle support;
2. local library-runner execution through a Snowflake session;
3. table, SQL and staged-file source planning;
4. append, overwrite, current-state upsert and hash-diff upsert runtime paths;
5. basic quality, schema policy, state and control-table evidence;
6. publish-to-stage and task/procedure rendering code paths;
7. cost reconciliation and dashboard/maintenance helpers;
8. a temporary live smoke harness under `.tmp/snowflake-smoke`.

Known baseline gaps:

1. the local smoke harness is not a first-class package/CLI command;
2. CLI `run` does not yet open a real connector session for non-dry-run runs;
3. stage publish, Snowpark procedure execution and task execution are not live-smoked;
4. governance/access/cost/failure-path live coverage is incomplete;
5. source/preparation parity is much thinner than Databricks/AWS;
6. state/idempotency/locking is thinner than Databricks;
7. control-table migrations and existing-table compatibility need hardening.

## Commit Plan

### Commit 01: Record The Parity Execution Plan

Goal: make this numbered execution plan visible in the repo.

Implementation items:

1. add `docs/specs/snowflake-adapter-parity-execution-plan.md`;
2. link it from `adapters/snowflake/README.md`;
3. link it from `docs/README.md`;
4. do not change runtime behavior.

Validation:

1. inspect markdown links;
2. no runtime tests required unless docs tooling is run.

Commit message:

```text
docs: add Snowflake parity execution plan
```

### Commit 02: Connector-Backed CLI Run

Goal: make `contractforge-snowflake run` execute a real local library-runner run
using Snowflake connector options.

Implementation items:

1. split CLI code enough to keep `cli.py` thin or add focused helpers under
   `contractforge_snowflake/cli_run.py`;
2. add `--connect-options` to `run`;
3. open a connector connection lazily only for non-dry-run execution;
4. wrap connector connections with a session adapter that exposes
   `session.sql(...).collect()`;
5. preserve current dry-run behavior;
6. close owned connections on success and failure;
7. redact connect-option values from errors/output.

Tests:

1. CLI dry-run still avoids connector import;
2. CLI non-dry-run opens `_connect`, passes the session into
   `run_snowflake_contract`, and closes it;
3. connector-session wrapper exposes `schema.names`/`schema.fields` from cursor
   metadata;
4. connection failure returns a clear CLI error.

Live smoke:

```powershell
contractforge-snowflake run `
  --contract-uri .tmp\snowflake-smoke\contracts\orders_append.contract.json `
  --environment-uri .tmp\snowflake-smoke\environment.json `
  --connect-options .tmp\snowflake-smoke\connect-options.yaml
```

Commit message:

```text
feat(snowflake): run contracts through connector-backed CLI
```

### Commit 03: Promote Minimal Smoke To First-Class Package

Goal: replace the temporary `.tmp` smoke harness with a reusable adapter smoke
command.

Implementation items:

1. add `contractforge_snowflake/smoke/models.py`;
2. add `contractforge_snowflake/smoke/minimal.py`;
3. add `contractforge_snowflake/smoke/runner.py`;
4. add CLI command `smoke`;
5. support `--connection` for Snowflake CLI interop documentation and
   `--connect-options` for connector execution;
6. support `--database`, `--schema`, `--table-prefix`;
7. default to non-destructive `CF_SMOKE_*` objects;
8. write summary JSON with target counts, control-table counts, run ids and
   warnings.

Tests:

1. smoke contract generation is deterministic;
2. smoke setup only touches configured schema/prefix;
3. smoke summary marks all scenarios pass/fail;
4. smoke command refuses broad cleanup unless `--execute-cleanup` is supplied.

Live smoke:

```powershell
contractforge-snowflake smoke --connect-options .tmp\snowflake-smoke\connect-options.yaml
```

Commit message:

```text
feat(snowflake): add first-class minimal smoke runner
```

### Commit 04: Control-Table DDL And Migration Hardening

Goal: make evidence table creation safe for existing Snowflake accounts.

Implementation items:

1. keep all generated control-table identifiers quoted;
2. add migration/compatibility inspection for existing unquoted uppercase
   control tables;
3. avoid unconditional `CREATE DATABASE` when the current role only owns schema
   objects and the database already exists;
4. add a deployment option for validate-only DDL;
5. record skipped bootstrap statements in smoke summary;
6. document minimum privileges for service users.

Tests:

1. reserved words such as `trigger` are quoted;
2. existing incompatible tables produce actionable errors;
3. existing compatible tables are reused;
4. service-role bootstrap can skip existing database/schema creation.

Live smoke:

1. run minimal smoke with service role in existing `PUBLIC`;
2. run minimal smoke in a new schema with admin role.

Commit message:

```text
fix(snowflake): harden control table bootstrap
```

### Commit 05: Runtime Metrics And Run Evidence Completeness

Goal: populate run evidence with row metrics and Snowflake query context closer
to AWS/Databricks.

Implementation items:

1. capture rows read before quality filters;
2. capture rows written for append/overwrite;
3. capture inserted/updated counts where Snowflake result metadata supports it;
4. store query ids for adapter-owned statements when available;
5. include warehouse, role, database, schema and Snowflake version in metadata;
6. include command/query counts in `metrics_json`;
7. preserve redaction in error paths.

Tests:

1. append success evidence has row counts;
2. overwrite success evidence has row counts;
3. upsert/hash-diff records available write metrics;
4. connector result metadata is normalized without Snowpark.

Live smoke:

1. verify `ctrl_ingestion_runs.rows_read`;
2. verify `metrics_json` contains query ids or documented nulls.

Commit message:

```text
feat(snowflake): record runtime row and query metrics
```

### Commit 06: Failure-Path Evidence Smoke

Goal: make Snowflake failure behavior match AWS/Databricks discipline.

Implementation items:

1. add smoke scenario for missing source table;
2. add smoke scenario for failing quality rule;
3. persist `ctrl_ingestion_errors`;
4. persist failed `ctrl_ingestion_runs`;
5. ensure original exception still propagates for CLI non-zero exit;
6. include redacted error text in summary.

Tests:

1. runtime failure writes error evidence;
2. quality abort writes quality/error/run evidence;
3. secrets/password/token-like strings are redacted.

Live smoke:

```powershell
contractforge-snowflake smoke-failure-paths --connect-options ...
```

Commit message:

```text
feat(snowflake): validate failure path evidence
```

### Commit 07: Source Registry And Source Parity Layer

Goal: move source handling out of the monolithic runtime execution module.

Implementation items:

1. add `sources/registry.py`;
2. add `sources/table.py`;
3. add `sources/sql.py`;
4. add `sources/stage_files.py`;
5. add `sources/review.py` for unsupported/review-required source families;
6. keep behavior identical for currently supported sources;
7. return structured source metadata for evidence.

Tests:

1. table/view/sql source SQL is unchanged;
2. stage source SQL is unchanged;
3. unsupported source types produce existing planner statuses;
4. source metadata is available to evidence writer.

Commit message:

```text
refactor(snowflake): introduce source registry
```

### Commit 08: Preparation Registry And SQL-Compatible Transforms

Goal: reach baseline transform parity for Snowflake SQL-compatible operations.

Implementation items:

1. add `preparation/registry.py`;
2. support projection/column selection;
3. support `transform.cast`;
4. support `transform.derive`;
5. support `transform.standardize` for trim/lower/upper;
6. support filters where represented by core semantic model;
7. support deterministic deduplicate using `QUALIFY ROW_NUMBER()`;
8. keep complex nested shape as `REVIEW_REQUIRED` until live-tested.

Tests:

1. casts render Snowflake SQL;
2. derives render Snowflake SQL with dialect warning;
3. standardization renders SQL functions;
4. deduplicate requires deterministic ordering;
5. unsupported nested shape stays review-required.

Live smoke:

1. SQL-compatible transform scenario;
2. deduplicate/upsert scenario.

Commit message:

```text
feat(snowflake): add SQL-compatible preparation registry
```

### Commit 09: Write-Mode Registry

Goal: split write modes and make them independently testable.

Implementation items:

1. add `write_modes/registry.py`;
2. add `write_modes/append.py`;
3. add `write_modes/overwrite.py`;
4. add `write_modes/upsert.py`;
5. add `write_modes/hash_diff.py`;
6. keep historical/snapshot soft-delete review boundaries explicit;
7. centralize merge-key validation.

Tests:

1. append SQL unchanged;
2. overwrite SQL unchanged;
3. upsert validates null/duplicate keys;
4. hash-diff excludes declared columns;
5. unsupported modes cannot execute silently.

Commit message:

```text
refactor(snowflake): split write mode execution
```

### Commit 10: Schema Policy And Schema Evidence

Goal: bring schema policy closer to Databricks/AWS maturity.

Implementation items:

1. inspect target schema through `INFORMATION_SCHEMA.COLUMNS` when connected;
2. maintain connector metadata fallback for local session wrapper;
3. enforce strict/additive/permissive consistently;
4. write `ctrl_ingestion_schema_changes` for additive changes;
5. classify type widening/incompatible changes;
6. add schema change details to run evidence.

Tests:

1. strict added/removed columns fail;
2. additive nullable columns are applied;
3. incompatible type changes fail or review according to policy;
4. schema changes evidence is written.

Live smoke:

1. additive column smoke;
2. strict failure smoke.

Commit message:

```text
feat(snowflake): add schema policy evidence
```

### Commit 11: Quality Parity Expansion

Goal: implement and live-smoke supported quality rules.

Implementation items:

1. confirm `not_null`, `required_columns`, `accepted_values`, `min_rows`,
   `unique_key`, `max_null_ratio`, and row-level expressions;
2. reject aggregate quarantine without row predicate;
3. add warn/fail/quarantine status handling;
4. persist `ctrl_ingestion_quality` and `ctrl_ingestion_quarantine`;
5. include quality summary in run evidence.

Tests:

1. pass/warn/fail/quarantine unit tests;
2. aggregate quarantine rejection;
3. row-level quarantine filters target write.

Live smoke:

1. passing quality;
2. quarantined row quality;
3. aborting quality.

Commit message:

```text
feat(snowflake): expand quality and quarantine runtime
```

### Commit 12: State, Idempotency And Locks

Goal: bring state handling toward Databricks maturity.

Implementation items:

1. persist last success state for every run;
2. support watermark candidate calculation;
3. support previous watermark filtering;
4. add idempotency lookup for declared idempotent runs;
5. add lock acquire/release helpers;
6. record lock/state evidence in control tables.

Tests:

1. previous watermark filters source;
2. successful run updates state;
3. idempotent replay can skip;
4. lock acquisition detects active lock;
5. lock release does not mask original failures.

Live smoke:

1. two-run watermark scenario;
2. idempotent replay scenario.

Commit message:

```text
feat(snowflake): add state idempotency and locks
```

### Commit 13: Governance Comments And Tags

Goal: validate Snowflake annotations live.

Implementation items:

1. implement table comments;
2. implement column comments;
3. implement tag application when tag objects exist;
4. support validate-only mode for tags;
5. persist `ctrl_ingestion_annotations`;
6. document tag namespace requirements.

Tests:

1. comments render/apply;
2. missing tag can warn or fail by policy;
3. annotation evidence redacts values.

Live smoke:

1. comments smoke;
2. tag validate-only smoke;
3. optional tag apply smoke when tag object exists.

Commit message:

```text
feat(snowflake): apply comments and tag annotations
```

### Commit 14: Access Grants And Policy Review

Goal: mature access handling without unsafe destructive changes.

Implementation items:

1. map grants to Snowflake privileges;
2. implement validate-only grant plan;
3. implement apply grants when explicitly requested;
4. render row access policy SQL;
5. render masking policy SQL;
6. keep destructive revokes review-required;
7. persist `ctrl_ingestion_access`.

Tests:

1. grant plan renders safe SQL;
2. validate-only records evidence without grant;
3. row/mask policy SQL validates required fields;
4. destructive drift raises review-required.

Live smoke:

1. validate-only grant smoke;
2. optional grant apply smoke to test role.

Commit message:

```text
feat(snowflake): add access grant and policy evidence
```

### Commit 15: Stage Publish Live Smoke

Goal: prove publish bundles can be uploaded and consumed from a Snowflake stage.

Implementation items:

1. add smoke setup for internal stage;
2. publish artifacts to stage;
3. load contract/environment artifacts back through runtime loader;
4. run a staged-artifact contract through local connector-backed runtime;
5. summarize manifest and artifact URIs.

Tests:

1. stage URI validation;
2. unsafe stage paths rejected;
3. publish closes owned connections on failure.

Live smoke:

```powershell
contractforge-snowflake smoke-stage-publish --connect-options ...
```

Commit message:

```text
feat(snowflake): smoke stage publish artifacts
```

### Commit 16: Snowpark Procedure Deployment

Goal: deploy and execute the stable Snowflake runtime procedure.

Implementation items:

1. build/install adapter wheel for procedure import;
2. upload wheel to stage;
3. create or replace runtime procedure;
4. call procedure with contract/environment artifact URIs;
5. capture procedure query id and result;
6. document required packages/imports.

Tests:

1. procedure SQL renders deterministic imports/packages;
2. unsafe wheel URIs are rejected;
3. procedure call SQL is safe.

Live smoke:

1. deploy procedure;
2. run one append contract through procedure;
3. verify target/evidence.

Commit message:

```text
feat(snowflake): deploy stable Snowpark runner procedure
```

### Commit 17: Task Graph Deployment And Execution

Goal: prove scheduled/dependency project execution in real Snowflake.

Implementation items:

1. create task graph from project schedule and dependencies;
2. deploy tasks calling stable runner procedure;
3. support dry-run/apply/resume/suspend;
4. run root task manually for smoke;
5. poll task history;
6. persist task evidence summary.

Tests:

1. schedule timezone renders correctly;
2. dependency `AFTER` renders correctly;
3. resume/suspend commands are explicit;
4. task graph refuses missing artifact URI/procedure.

Live smoke:

```powershell
contractforge-snowflake smoke-task-graph --connect-options ...
```

Commit message:

```text
feat(snowflake): deploy and smoke task graph execution
```

### Commit 18: Project CLI Parity

Goal: make Snowflake project commands as usable as AWS/Databricks equivalents.

Implementation items:

1. split `deploy-project` implementation if needed;
2. add `run-project` or equivalent execute command;
3. add `--wait` and status polling;
4. add summary-only and JSON output modes;
5. add cleanup-plan command;
6. add cost-gated apply flags.

Tests:

1. project dry-run validates all steps;
2. unsupported step blocks deployment;
3. summary-only omits noisy artifacts;
4. cleanup plan is non-destructive by default.

Live smoke:

1. deploy two-step project;
2. run/wait;
3. verify both targets and evidence.

Commit message:

```text
feat(snowflake): add project run and cleanup CLI
```

### Commit 19: Cost Reconciliation Live Smoke

Goal: validate Snowflake cost evidence after Account Usage latency.

Implementation items:

1. reconcile by structured query tag;
2. record query history signals;
3. record query attribution signals when available;
4. include warehouse metering/task metadata where available;
5. support delayed poll/retry configuration.

Tests:

1. query history SQL filters by run id;
2. missing Account Usage rows returns delayed/pending status;
3. cost evidence insert is idempotent enough for repeated reconciliation.

Live smoke:

1. run minimal smoke;
2. reconcile cost for one run id;
3. verify `ctrl_ingestion_cost` rows or documented pending status.

Commit message:

```text
feat(snowflake): smoke query history cost reconciliation
```

### Commit 20: Source Expansion For Stage Formats

Goal: broaden file-source support while keeping non-Snowflake extraction
review-first.

Implementation items:

1. support staged CSV with file format;
2. support staged JSON with `VARIANT` projection;
3. support staged Parquet projection where feasible;
4. classify external stage requirements;
5. keep HTTP/JDBC/Kafka review-required unless pre-staged.

Tests:

1. CSV staged read;
2. JSON staged read;
3. Parquet staged read or explicit review;
4. unsafe file format/stage rejected.

Live smoke:

1. stage small CSV;
2. run bronze staged-file append;
3. validate target and copy/source evidence.

Commit message:

```text
feat(snowflake): expand staged file source support
```

### Commit 21: Lineage And Explain Evidence

Goal: populate lineage/explain control tables.

Implementation items:

1. write immediate ContractForge lineage during run;
2. add optional delayed `ACCESS_HISTORY` reconciliation;
3. capture `EXPLAIN` output for supported statements;
4. persist `ctrl_ingestion_lineage`;
5. persist `ctrl_ingestion_explain`.

Tests:

1. lineage event includes source/target/run id;
2. explain capture stores plan text;
3. Account Usage latency is handled as pending.

Live smoke:

1. verify lineage rows;
2. verify explain rows.

Commit message:

```text
feat(snowflake): record lineage and explain evidence
```

### Commit 22: Documentation And Examples

Goal: document Snowflake operation at the same standard as AWS/Databricks.

Implementation items:

1. add `docs/adapters/snowflake.md`;
2. add service-user/PAT/key-pair setup guide;
3. add minimal smoke guide;
4. add project deploy guide;
5. add governance/access guide;
6. add cost reconciliation guide;
7. update site docs if applicable;
8. add real-world Snowflake example project.

Validation:

1. docs links pass existing documentation tests;
2. examples render with current CLI.

Commit message:

```text
docs: add Snowflake adapter operations guide
```

### Commit 23: Stabilization Matrix And CI Gates

Goal: make readiness measurable.

Implementation items:

1. add `docs/specs/snowflake-stabilization-matrix.md`;
2. list support status for every source/write/governance/evidence feature;
3. map each row to tests and smoke command;
4. add optional/manual GitHub workflow for Snowflake smoke;
5. add packaging check for runtime extras.

Tests:

1. documentation map includes matrix;
2. packaging tests include `contractforge-snowflake[runtime]` where feasible;
3. CI workflow syntax is valid.

Commit message:

```text
docs: add Snowflake stabilization matrix
```

### Commit 24: Release Candidate Cleanup

Goal: finish alpha-quality release discipline.

Implementation items:

1. remove temporary `.tmp` smoke dependencies from docs;
2. ensure public API exports are stable;
3. run full tests;
4. run live minimal smoke;
5. run live failure smoke;
6. run live stage/procedure/task smoke where credentials allow;
7. update README maturity status;
8. tag known review-required limitations.

Validation:

1. `uv run pytest`;
2. `uv build`;
3. live Snowflake smoke summary attached to release notes;
4. no Snowflake SDK import on default import path.

Commit message:

```text
chore(snowflake): prepare adapter alpha release
```

## Running Status

Use this section as commits land.

| Commit | Status | Notes |
| --- | --- | --- |
| 01 | Complete | Plan document and links added. |
| 02 | Complete | Connector-backed CLI run and focused tests pass. Service-role execution is unblocked by Commit 04. |
| 03 | Complete | First-class `smoke` package and CLI added; live packaged smoke passed with `CFINGESTSVC`. |
| 04 | Complete | Control-table DDL can skip existing database/schema bootstrap; live service-role smoke passed in `CONTRACTFORGE_TEST_DB.PUBLIC`. |
| 05 | Complete | Runtime rows/query metrics recorded in run evidence; live packaged smoke verified rows and query ids. |
| 06 | Complete | `smoke-failure-paths` added; live smoke verified missing-source and quality-abort evidence. |
| 07 | Complete | Source registry added for table/view/sql/stage sources; live success and failure smokes passed after refactor. |
| 08 | Complete | Preparation registry added with metadata projection, filters, Snowflake-native replacement transforms, deterministic deduplicate, and live transform/dedup smokes passing. |
| 09 | Complete | Write modes split into append/overwrite/upsert/hash-diff registry modules; focused tests and live success/failure smokes passed. |
| 08 | Pending | Preparation registry. |
| 09 | Pending | Write-mode registry. |
| 10 | Complete | Schema policy now inspects INFORMATION_SCHEMA with connector fallback, records additive schema-change evidence/run metrics, rejects incompatible type changes, and live additive/strict smokes passed. |
| 11 | Complete | Quality runtime now records per-rule summaries, propagates quality_status into run evidence, rejects aggregate quarantine, filters row-level quarantine writes, reports quarantined row metrics, and live pass/quarantine/abort smokes passed. |
| 12 | Complete | State runtime now quotes control-table columns, records failed state rows, supports previous watermark filtering/candidate recording, skips successful idempotency replays with evidence, and provides opt-in lock acquire/release with live watermark/idempotency smokes. |
| 13 | Complete | Table/column comments, qualified tag SQL, tag validate-only evidence, ignore/warn/fail policies, annotation evidence redaction, docs, and live comments/tag-validation smoke passed. |
| 14 | Complete | Grants, validate-only access evidence, row access policy SQL, masking policy SQL, destructive revoke review gating, access evidence redaction, docs, and live validate-only access smoke passed. |
| 15 | Complete | `smoke-stage-publish` creates a temporary internal stage, publishes the library-runner bundle, reloads manifest/contract/environment artifacts from `@stage` through connector-backed GET, runs the staged contract, and live smoke passed. |
| 16 | Complete | Procedure smoke command now stages Snowflake-compatible ZIP imports for the built core/adapter wheels, defaults procedure packages to the runtime dependency set, skips connector-only query-tag mutation inside the Snowpark handler, and live hosted procedure smoke passed with query id `00000000-0000-0000-0000-000000000000`. |
| 17 | Complete | Task lifecycle SQL, graph-level task history query, `smoke-task-graph`, dry-run tests and focused suite passed. Live task graph smoke passed after task grants were provisioned. |
| 18 | Complete | Added `run-project` dry-run/live task execution with optional bounded task-history wait, summary-only JSON output, non-destructive `cleanup-plan`, tests, and docs. |
| 19 | Complete | Cost reconciliation now probes structured `QUERY_TAG` run ids, returns `PENDING` for delayed or unavailable Account Usage, deletes prior adapter-owned cost signals before insert, records query-history and optional query-attribution signals, exposes wait/poll CLI flags, and focused tests pass. Live Account Usage grants were validated for `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` and `QUERY_ATTRIBUTION_HISTORY`. Runtime query tags were fixed to store parseable JSON by using unquoted target names; fresh minimal smoke passed with run `00000000-0000-0000-0000-000000000000`, and reconciliation remains correctly `PENDING` until Account Usage latency exposes that new run id. |
| 20 | Complete | Staged-file source rendering now supports CSV positional projections, JSON payload/typed projections and Parquet typed projections with named Snowflake file formats or stage defaults; unsupported staged formats are review-required and unsafe stage paths/column expressions/file-format mappings are rejected. Focused source tests pass. Live CSV staged-file append passed with run `00000000-0000-0000-0000-000000000000`, wrote 2 rows to `CF_SMOKE_STAGEFMT_ORDERS`, and temporary stage/file format/target objects were cleaned up. |
| 21 | Complete | Runtime execution now writes immediate ContractForge/OpenLineage-style lineage rows and `EXPLAIN USING TEXT` evidence, exposes delayed `ACCESS_HISTORY` reconciliation through API/CLI with `PENDING` handling, and focused Snowflake tests pass. Live minimal smoke wrote 5 lineage rows and 5 explain rows; `ACCESS_HISTORY` was reachable but still had 0 rows for run `00000000-0000-0000-0000-000000000000`, matching the delayed pending path. |
| 22 | Complete | Added `docs/adapters/snowflake.md` operations guide, stabilization matrix, and updated adapter index/docs links. |
| 23 | Complete | Added `docs/specs/snowflake-stabilization-matrix.md` with scope, release gates, and blocked-gate unblock plan. |
| 24 | Complete | Updated README maturity status from "Planning" to "Alpha with real Snowflake validation". Marked known review-required limitations for blocked procedure/task gates. Focused tests passed. |
| 25 | Complete | Real Snowflake hosted procedure library-runner USGS GeoJSON frozen medallion executed bronze-to-gold against the same 30-feature baseline used for AWS/Databricks parity. Snowflake counts were bronze=1, silver=30, gold daily=2, gold bands=3 with 4 successful run rows, 16 quality rows, no quarantine rows and no errors. AWS and Databricks target/run evidence matched the four result counts and `SUCCESS/PASSED` statuses. Full tests passed. |

## Execution Rule

Work through this file in order unless a blocking dependency forces a local
swap. Each commit should update the status table, include tests for its change,
and record any live-smoke command that was run.
