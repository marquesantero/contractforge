# Snowflake Adapter Implementation Plan

## Purpose

This plan defines how to implement `contractforge-snowflake` as a first-class
ContractForge adapter without weakening the core architecture.

It is based on the lessons from the Databricks reference adapter and the AWS
Glue/Iceberg adapter:

- keep the core free of platform SDKs and runtime libraries;
- make the adapter consume public core models and contracts;
- declare capabilities conservatively;
- use platform-native execution, not lowest-common-denominator execution;
- keep a stable runtime library as the default execution path;
- use generated artifacts for review, deployment and debugging, not as the only
  source of ingestion behavior;
- persist the canonical ContractForge evidence/control-table schema and fill it
  with Snowflake-native values.

The researched Snowflake parity target is
[Snowflake capability and evidence parity](snowflake-capability-parity.md).

## Non-Negotiable Architecture Rules

1. The core must not import Snowflake connector, Snowpark, SQLAlchemy or any
   Snowflake SDK.
2. The adapter must not change contract meaning to fit Snowflake.
3. Snowflake-specific configuration must live under `environment.parameters.snowflake`
   or adapter-owned deployment artifacts, not in ingestion semantics.
4. Runtime imports must be lazy. Importing `contractforge_snowflake` locally for
   planning must not require Snowflake credentials or a network connection.
5. Unsupported or review-sensitive semantics must return `REVIEW_REQUIRED` or
   `UNSUPPORTED`; no silent fallback from historical mode to append, from quarantine to warn,
   or from streaming to batch.
6. Evidence tables must use the core control-table schema. Snowflake Account
   Usage and Information Schema views are evidence sources, not replacements for
   ContractForge evidence.
7. Use registries and strategy objects for source/write/evidence/governance
   routing. Avoid long `if platform == ...` or sequential `if source_type == ...`
   dispatch blocks.
8. Every implemented capability needs docs, tests, planner behavior and either
   runtime behavior or an explicit blocker/review item.

## Target Package

```text
adapters/snowflake/
  pyproject.toml
  README.md
  src/
    contractforge_snowflake/
      __init__.py
      adapter.py
      api.py
      cli.py
      environment.py
      capabilities/
        __init__.py
        models.py
        registry.py
        sql_warehouse.py
        task_graph.py
        snowpipe.py
        streams_tasks.py
      planning/
        __init__.py
        planner.py
        diagnostics.py
        warnings.py
      naming/
        __init__.py
        identifiers.py
        objects.py
      rendering/
        __init__.py
        artifacts.py
        review.py
        sql_bundle.py
        deployment_manifest.py
      runtime/
        __init__.py
        runner.py
        context.py
        session.py
        contract_loader.py
        execution.py
        finalization.py
      sources/
        __init__.py
        registry.py
        table.py
        sql.py
        stage_files.py
        incremental_files.py
        native_passthrough.py
      write_modes/
        __init__.py
        registry.py
        append.py
        overwrite.py
        merge.py
        hash_diff.py
        snapshot_reconcile_soft_delete.py
        scd2_review.py
      preparation/
        __init__.py
        registry.py
        select.py
        mapping.py
        transforms.py
        shape_review.py
      quality/
        __init__.py
        registry.py
        sql_checks.py
        quarantine.py
        dmf_review.py
      schema/
        __init__.py
        inspection.py
        policy.py
        ddl.py
      evidence/
        __init__.py
        ddl.py
        writer.py
        query_history.py
        task_history.py
        copy_history.py
        cost.py
      state/
        __init__.py
        tables.py
        watermarks.py
        locks.py
      annotations/
        __init__.py
        comments.py
        tags.py
        evidence.py
      governance/
        __init__.py
        grants.py
        row_access.py
        masking.py
        drift.py
      operations/
        __init__.py
        evidence.py
        tasks.py
      deployment/
        __init__.py
        project.py
        stages.py
        tasks.py
        procedures.py
      security/
        __init__.py
        secrets.py
        redaction.py
        query_tag.py
      diagnostics/
        __init__.py
        explain.py
        portability.py
        cost_review.py
      templates/
        runner.sql
        stored_procedure.sql
        task_graph.sql
  tests/
    ...
```

This mirrors the Databricks and AWS domain split without copying their runtime
technology. The Snowflake adapter should start smaller than Databricks, but it
should still avoid god files from day one.

## Runtime Model

The default Snowflake execution model should follow the AWS correction and the
Databricks operational shape:

```text
contract bundle
  -> core validation
  -> Snowflake planning
  -> publish Snowflake contract/environment/runtime artifacts
  -> create/update stable Snowflake runtime object
  -> runtime object loads contract and calls contractforge_snowflake runner
  -> runner executes source, preparation, quality, write and evidence steps
```

Generated per-contract ingestion SQL must not be the default. Snowflake follows
the publish-and-runner model: deploy the contract, environment and runner
metadata, then let a stable adapter runtime execute the ingestion. SQL artifacts
are allowed for infrastructure bootstrap and review support only. The adapter
should expose a stable runner:

```python
from contractforge_snowflake.runtime import run_ingestion

run_ingestion(
    contract_uri="stage://CONTRACTFORGE_ARTIFACTS/contracts/orders.json",
    environment_uri="stage://CONTRACTFORGE_ARTIFACTS/environments/prod.json",
)
```

Deployment can implement this with one or more of:

- Snowflake Scripting stored procedure;
- Python stored procedure with the adapter wheel staged;
- external deployment command that submits runner SQL through the Snowflake
  connector;
- task graph that calls the stable runner entrypoint for each contract step.

The first implementation may build publish bundles and run them through a local
Python CLI that calls the same adapter runtime. Runtime-in-Snowflake can be
phased in, but the architecture must keep the library-runner model as the
default path, not per-contract code generation.

## Public API Target

```python
from contractforge_snowflake import (
    SnowflakeAdapter,
    build_snowflake_publish_bundle,
    plan_snowflake_contract,
    render_snowflake_contract,
    deploy_snowflake_project,
    run_snowflake_contract,
)
```

Expected behavior:

| API | Network required | Purpose |
| --- | --- | --- |
| `plan_snowflake_contract` | No | Validate Core contract against Snowflake capabilities. |
| `build_snowflake_publish_bundle` | No | Build contract, environment, runtime invocation and infrastructure bootstrap artifacts for the library runner. |
| `render_snowflake_contract` | No | Compatibility adapter-protocol entry point that returns the same publish bundle; it must not generate per-contract ingestion SQL. |
| `deploy_snowflake_project` | Yes | Upload artifacts, create/update stages/procedures/tasks. |
| `run_snowflake_contract` | Yes | Execute through Snowflake session or deployed task/procedure. |

The package import path must remain network-free. Runtime/deploy functions may
import optional dependencies lazily.

## Packaging

```toml
[project]
name = "contractforge-snowflake"
dependencies = [
  "contractforge-core>=0.2,<0.3",
]

[project.optional-dependencies]
runtime = [
  "snowflake-connector-python>=3",
]
snowpark = [
  "snowflake-snowpark-python>=1",
]
dev = [
  "pytest",
]
```

Default install should support planning and publish-bundle creation. Runtime dependencies should
be optional until a user asks to deploy or execute.

## Phase 0: Design Lock And Guardrails

### Scope

- Add ADR for Snowflake adapter strategy.
- Confirm the subtargets from `snowflake-capability-parity.md`.
- Confirm first runtime path:
  - first: local CLI loads published contract artifacts and calls the adapter runtime;
  - next: stable stored procedure/task runner calls the same runtime entry point;
  - future: Snowpark for complex transforms and external connectors.
- Define Snowflake environment contract fields.
- Define artifact URI schemes accepted by the adapter.

### Deliverables

- `docs/adrs/ADR-009-snowflake-adapter-strategy.md`
- `docs/specs/extensions-snowflake.md`
- updates to `publication-packaging.md`, `adapter-authoring.md`, `platform-contract-parity.md`

### Acceptance

- Architecture docs explicitly state what belongs to core vs Snowflake adapter.
- No core model receives Snowflake-specific fields.
- Planner statuses for first capability set are documented.

## Phase 1: Package Skeleton And Planning

### Scope

Create `adapters/snowflake` with:

- independent `pyproject.toml`;
- package exports;
- `SnowflakeAdapter` facade;
- capability registry;
- planning API;
- basic artifact model;
- no Snowflake SDK imports at package import time.

### Capability Baseline

| Capability | Initial status |
| --- | --- |
| table/view/sql sources | `SUPPORTED` |
| staged file batch | `SUPPORTED_WITH_WARNINGS` |
| incremental files | `REVIEW_REQUIRED` |
| append | `SUPPORTED` |
| overwrite | `SUPPORTED_WITH_WARNINGS` |
| current-state upsert | `SUPPORTED` |
| hash-diff upsert | `SUPPORTED_WITH_WARNINGS` |
| historical | `REVIEW_REQUIRED` |
| snapshot soft delete | `SUPPORTED_WITH_WARNINGS` |
| strict schema | `SUPPORTED` |
| additive schema | `SUPPORTED_WITH_WARNINGS` |
| quality SQL checks | `SUPPORTED` |
| quarantine row-level | `SUPPORTED_WITH_WARNINGS` |
| comments | `SUPPORTED` |
| tags | `SUPPORTED_WITH_WARNINGS` |
| grants | `SUPPORTED_WITH_WARNINGS` |
| row access policies | `SUPPORTED_WITH_WARNINGS` |
| masking policies | `SUPPORTED_WITH_WARNINGS` |
| task scheduling | `SUPPORTED` |
| task dependencies | `SUPPORTED_WITH_WARNINGS` |
| cost evidence | `SUPPORTED_WITH_WARNINGS` |

### Tests

- Import tests prove no Snowflake SDK is required.
- Planning tests cover `SUPPORTED`, `SUPPORTED_WITH_WARNINGS`,
  `REVIEW_REQUIRED`, `UNSUPPORTED`.
- Planner blocks Databricks-specific `autoloader`.
- Planner suggests portable `incremental_files`.
- Planner keeps historical review-required.

### Acceptance

- `uv run pytest tests/test_snowflake_planning.py`
- No changes required in `contractforge_core` except generic improvements that
  benefit all adapters.

## Phase 2: Identifier, Naming And Environment Binding

### Scope

Implement Snowflake-safe naming helpers:

- quote identifiers;
- quote fully-qualified names;
- validate task/procedure/stage names;
- derive artifact names from core naming policy;
- map `target.catalog` to Snowflake database;
- map `target.schema` to Snowflake schema;
- map `environment.evidence` to Snowflake evidence database/schema;
- map `environment.parameters.snowflake` without leaking into ingestion semantics.

### Environment Example

```yaml
adapter: snowflake
evidence:
  database: CONTRACTFORGE
  schema: CF_EVIDENCE
artifacts:
  uri: stage://CONTRACTFORGE_ARTIFACTS/prod/
parameters:
  snowflake:
    warehouse: CF_WH
    role: CONTRACTFORGE_ROLE
    runtime_database: CONTRACTFORGE
    runtime_schema: CF_RUNTIME
    task_database: CONTRACTFORGE
    task_schema: CF_TASKS
    external_access_integrations:
      - CF_TMDB_REST_ACCESS
    secrets:
      tmdb_api_token: CONTRACTFORGE.CF_RUNTIME.CF_TMDB_API_TOKEN
```

`{{ secret:snowflake/<alias> }}` placeholders are for values resolved inside a
Snowflake hosted procedure. They must correspond to aliases declared in
`parameters.snowflake.secrets`, which renders Snowflake `SECRETS = (...)`
bindings. Connection profiles and account names remain deployment/runtime
configuration, not ingestion contract secrets.

### Tests

- Identifier quoting handles embedded quotes.
- Generated object names are stable and deterministic.
- Environment defaults do not mutate contract source/target semantics.

## Phase 3: Publish Bundle And Runtime Manifest

### Scope

Build reviewable publish artifacts for:

- raw contract snapshot;
- environment snapshot;
- runner invocation manifest;
- evidence DDL from core control-table schema;
- stage, warehouse, role and task review notes;
- deployment manifest.

### Publish Rules

- Publish artifact names must be deterministic.
- Sensitive values must be redacted.
- Unsupported sections produce review blockers or warnings, not runnable partial ingestion artifacts.
- The default publish bundle must not contain `.source.sql`, `.write.sql` or other per-contract ingestion logic.
- Runtime dispatch should use registries:

```python
SOURCE_RUNNERS = {
    "table": TableSourceRunner(),
    "view": TableSourceRunner(),
    "sql": SqlSourceRunner(),
    "csv": StageFileSourceRunner(),
}
```

### Acceptance

- Every artifact has a type, path, bytes, line count and purpose in the manifest.
- Publish manifests declare `execution_model: library_runner`.
- Tests fail if generated source/write SQL is emitted by the default path.
- No sequential source/write-mode `if` chain grows into a god runner.

## Phase 4: Source Runtime Implementation

### Initial Sources

| Source | Runtime path |
| --- | --- |
| `table` | `SELECT` from resolved table. |
| `view` | `SELECT` from resolved view. |
| `sql` | Adapter-resolved SQL with `table_ref` placeholders replaced. |
| staged `csv/json/parquet` | Snowflake stage plus `COPY INTO` or staged `SELECT`. |
| `object_storage` | External stage configuration review first, then load. |

### Later Sources

| Source | Target status |
| --- | --- |
| `incremental_files` | Snowpipe/copy-history/state-table design; review first. |
| `http_file` | Prefer pre-stage pattern first; external access/Snowpark later. |
| JDBC family | Review-required; Snowflake is not the general extraction runtime. |
| Kafka/Event Hubs | Snowpipe Streaming or bridge; review-required. |
| native passthrough | Connector/native app/marketplace pattern; review artifact first. |

### Tests

- Table/view/sql source runner contract tests.
- Stage file source runner contract tests.
- Incremental files returns review-required with concrete reason.
- `connection.yaml` inheritance is resolved by core before Snowflake planning.

## Phase 5: Write Modes

### Initial Runtime Modes

| Mode | Implementation |
| --- | --- |
| `append` | `INSERT INTO target SELECT ...` or `COPY INTO target`. |
| `overwrite` | reviewed transaction pattern: `CREATE OR REPLACE TABLE AS SELECT` or truncate/insert based on environment policy. |
| `upsert` | `MERGE INTO target USING staging`. |
| `hash_diff_upsert` | staging hash projection plus `MERGE` only changed rows. |
| `snapshot_reconcile_soft_delete` | render review-first SQL; execute only when source completeness is declared. |
| `historical` | review-required until historical policy is explicit and tested. |

### Hard Requirements

- Duplicate keys must fail before `MERGE`.
- Null merge keys must follow core policy.
- Hash diff must automatically exclude generated/framework columns.
- User can declare `hash_keys` for wide tables.
- User can declare `hash_exclude_columns` for all-column hashing.
- Adapter must not use Snowflake row counters alone when it can compute exact
  ContractForge counters in staging.

### Tests

- Append inserts rows.
- Overwrite preserves planned behavior and emits warning.
- Upsert inserts and updates correctly.
- Hash diff does not update unchanged rows.
- Hash diff updates changed rows.
- historical returns review-required.

## Phase 6: Schema Policy

### Scope

- Inspect target schema via `INFORMATION_SCHEMA.COLUMNS`.
- Render create table DDL when missing.
- Enforce strict schema policy.
- Render/apply additive nullable columns when allowed.
- Record schema change evidence.
- Keep type widening review-required until tested.

### Acceptance

- Strict drift fails before write.
- Additive nullable column is planned and recorded.
- Incompatible type change is review-required or failed according to policy.

## Phase 7: Quality And Quarantine

### Runtime Rules

| Quality type | Implementation |
| --- | --- |
| `not_null` | SQL count/predicate. |
| `required_columns` | `INFORMATION_SCHEMA.COLUMNS`. |
| `unique_key` | grouped duplicate query. |
| `accepted_values` | SQL predicate or reference table. |
| `min_rows` | row count query. |
| `max_null_ratio` | ratio query. |
| `expressions` | Snowflake SQL predicate with dialect warning. |

### Enforcement

- `fail`: persist quality/error evidence where possible and fail the run.
- `warn`: persist quality evidence and continue.
- `quarantine`: only row-level predicates remove rows and write
  `ctrl_ingestion_quarantine`.
- aggregate quarantine rules become recorded warnings or fail according to core
  policy; they must not invent quarantined rows.

### Optional Native Integration

Snowflake Data Metric Functions can enrich observability but should not replace
runtime quality enforcement until the behavior matches ContractForge fail/warn/
quarantine semantics.

## Phase 8: Evidence And Control Tables

### Scope

Render and write canonical tables:

- `ctrl_ingestion_runs`
- `ctrl_ingestion_state`
- `ctrl_ingestion_quality`
- `ctrl_ingestion_quarantine`
- `ctrl_ingestion_errors`
- `ctrl_ingestion_schema_changes`
- `ctrl_ingestion_streams`
- `ctrl_ingestion_lineage`
- `ctrl_ingestion_annotations`
- `ctrl_ingestion_access`
- `ctrl_ingestion_operations`
- `ctrl_ingestion_explain`
- `ctrl_ingestion_cost`
- `ctrl_ingestion_metadata`

### Snowflake Native Sources

| Evidence need | Snowflake source |
| --- | --- |
| query status/timing/rows/errors | `SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY` and query-history table functions. |
| task status/timing/graph ids | `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY`. |
| staged file loads | `COPY_HISTORY` and `COPY INTO` result sets. |
| object access/lineage | `ACCESS_HISTORY`. |
| policy application | `POLICY_REFERENCES`. |
| tags | `TAG_REFERENCES`. |
| cost | `QUERY_ATTRIBUTION_HISTORY`, warehouse metering and Snowpipe billing fields. |
| schema | `INFORMATION_SCHEMA.COLUMNS`. |

### Query Tag

Every adapter-owned statement must set a structured query tag:

```json
{
  "product": "contractforge",
  "adapter": "snowflake",
  "run_id": "<run-id>",
  "project": "<project>",
  "target": "<database.schema.table>"
}
```

This is the join key for post-run reconciliation.

### Acceptance

- Success writes run/state/metadata/lineage evidence.
- Failure writes run/error evidence and re-raises or returns failed status.
- Quality quarantine writes both quality and quarantine evidence.
- Cost reconciliation can run after Account Usage latency and append
  `ctrl_ingestion_cost` rows.

## Phase 9: Annotations, Operations And Governance

### Annotations

- `annotations.table.description` -> `COMMENT ON TABLE`.
- `annotations.columns.*.description` -> `COMMENT ON COLUMN`.
- tags/PII/lifecycle metadata -> Snowflake tags where configured.
- evidence -> `ctrl_ingestion_annotations`.

### Operations

- persist ownership, SLA, criticality, runbook and groups to
  `ctrl_ingestion_operations`;
- map project schedule to task metadata;
- keep alerting review-required until notification integration is implemented.

### Access

- grants -> `GRANT` statements with privilege mapping;
- row filters -> row access policies;
- column masks -> masking policies;
- drift -> compare declared policy/grants to current state;
- destructive revoke paths always review-required.

### Acceptance

- Apply comments and validate.
- Apply one tag and validate through tag references.
- Apply grant plan in validate-only mode.
- Render row/mask policy SQL and evidence.
- Do not apply destructive access changes without explicit command and review.

## Phase 10: Project Deployment

### Project Flow

```bash
contractforge-snowflake deploy-project project.yaml --target dev --dry-run
contractforge-snowflake deploy-project project.yaml --target dev --apply
contractforge-snowflake run-project project.yaml --target dev --wait
```

### Deployment Responsibilities

- Load `project.yaml`.
- Resolve environment and connections through core.
- Plan every contract.
- Block unsupported contracts.
- Render artifacts.
- Upload artifacts to stage or configured artifact URI.
- Create/update runtime procedure or SQL scripts.
- Create/update tasks and dependencies.
- Optionally resume/suspend tasks.
- Record deployment manifest.

### Schedule Mapping

Core `project.schedule` remains platform-neutral:

```yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
```

Snowflake maps it to task syntax:

```sql
SCHEDULE = 'USING CRON 0 6 * * * America/Sao_Paulo'
```

Task dependencies map to `AFTER` relationships. The adapter must document
Snowflake task graph limits and failure behavior in the deployment review.

## Phase 11: Runtime Execution

### Initial Runtime

- local CLI opens Snowflake session;
- creates temp/staging objects;
- loads published contract/environment artifacts;
- calls the same `contractforge_snowflake` runtime used by deployed tasks;
- writes evidence using adapter evidence writer;
- optionally reconciles query history by query tag.

### Stable In-Snowflake Runtime

- package adapter wheel and runner metadata into a stage;
- create procedure/function runner;
- task graph calls stable runner with contract URI;
- runner loads contract and environment artifact;
- runner executes same adapter runtime steps.

### Acceptance

- One contract can run by local CLI.
- One project can run through task graph.
- Updating only contract artifact changes next run behavior without regenerating
  ingestion logic.

## Phase 12: Real E2E Tests

### Test Projects

| Project | Purpose |
| --- | --- |
| Minimal table-to-table | Baseline table source, append, evidence. |
| SQL-to-table | SQL source, table refs, transform derive. |
| Staged CSV medallion | Stage/COPY, bronze/silver/gold, quality, quarantine. |
| Supabase parity review | Same contract family used by Databricks/AWS, but Snowflake should mark JDBC extraction review-required unless pre-staged. |
| GeoJSON staged project | JSON/VARIANT, shape review, quality and medallion aggregation. |
| Governance project | comments, tags, grant plan, row/mask policy review. |
| Failure path | failed source/query, failed quality, redaction and error evidence. |
| Scheduled project | task graph with schedule, timezone and dependencies. |

### Required Evidence Checks

- target table row counts;
- `ctrl_ingestion_runs` status and row metrics;
- `ctrl_ingestion_state` latest watermark/status;
- `ctrl_ingestion_quality` results;
- `ctrl_ingestion_quarantine` when applicable;
- `ctrl_ingestion_errors` on expected failure;
- `ctrl_ingestion_schema_changes` for additive schema;
- `ctrl_ingestion_cost` after reconciliation;
- query tag join to `QUERY_HISTORY`;
- task graph join to `TASK_HISTORY`.

### Cost Discipline

Use the smallest warehouse and suspend it after tests. Cost-heavy tests must be
explicitly gated like AWS smoke tests. No test should create a long-running task
without a cleanup command.

## Phase 13: Documentation And Site

### Docs

- `docs/adapters/snowflake.md`
- `docs/specs/extensions-snowflake.md`
- `docs/specs/snowflake-stabilization-matrix.md`
- update `docs/connectors.md`
- update `docs/project-yaml.md`
- update `docs/specs/platform-contract-parity.md`
- update `docs/specs/evidence-mapping-matrix.md`
- update `docs/specs/write-engines.md`
- update `docs/security.md`

### Site

- expand `/docs/adapters/snowflake`;
- add Snowflake project examples;
- add Snowflake evidence/control-table examples;
- add Snowflake task deployment examples;
- add platform-minimal-difference examples when real tests pass.

### AI

ContractForge AI must learn:

- Snowflake target selection;
- Snowflake environment generation;
- Snowflake review boundaries;
- Snowflake evidence mapping;
- Snowflake project validation and parity reports.

## Phase 14: Stabilization Matrix

Create a Snowflake stabilization matrix with release gates:

| Gate | Requirement |
| --- | --- |
| Import boundary | No Snowflake SDK import in core or default adapter import path. |
| Planning | Full support/warning/review/unsupported coverage. |
| Rendering | Deterministic artifacts and manifests. |
| Runtime | Append, overwrite and current-state upsert real-account tests. |
| Quality | fail/warn/quarantine behavior validated. |
| Evidence | all canonical tables either populated or explicitly not applicable with reason. |
| Governance | comments/tags/grants validated; row/mask policies review or apply path tested. |
| Scheduling | task schedule/timezone/dependency tested. |
| Failure | failed run/error evidence tested. |
| Cost | query/task cost evidence reconciled. |
| Docs | repo docs and site complete. |
| Packaging | independent wheel built and install-tested. |

## Suggested Implementation Order

1. ADR and `extensions-snowflake.md`.
2. Package skeleton and import-boundary tests.
3. Capability registry and planner tests.
4. Identifier/naming/environment modules.
5. Rendering for SQL/table/append/overwrite/upsert.
6. Evidence DDL and writer.
7. Local runtime execution through Snowflake connector.
8. Quality checks and quarantine.
9. Schema policy.
10. Annotations comments and tags.
11. Project deployment and task graph rendering.
12. Real Snowflake smoke tests.
13. Cost/query-history reconciliation.
14. Governance grants/policies.
15. Site/docs/AI updates.
16. Stabilization and release candidate.

## Work Breakdown

### Milestone A: Planning-Only Adapter

Estimated scope: 2-4 days.

- package skeleton;
- capability registry;
- `plan_snowflake_contract`;
- docs and tests.

Done when core contracts can be evaluated for Snowflake with deterministic
planning results and no Snowflake dependencies installed.

### Milestone B: Publish-Bundle Adapter

Estimated scope: 4-7 days.

- publish bundle generation;
- evidence DDL rendering;
- review reports;
- deployment manifests.

Done when Databricks/AWS parity projects can build Snowflake publish bundles and
review-required items without executing. Default artifacts must not contain
per-contract ingestion SQL.

### Milestone C: Local Runtime

Estimated scope: 1-2 weeks.

- optional Snowflake connector dependency;
- session/security handling;
- append/overwrite/upsert;
- evidence writer;
- quality fail/warn/quarantine;
- schema strict/additive.

Done when real Snowflake smoke tests can run from local CLI.

### Milestone D: Project Deployment

Estimated scope: 1-2 weeks.

- stage artifacts;
- stored procedure or stable runner deployment;
- task graph deployment;
- schedule/timezone/dependency support;
- run/wait/status command.

Done when project-level flow works without users executing individual SQL files
manually.

### Milestone E: Stabilization

Estimated scope: 1-2 weeks.

- failure-path evidence;
- cost reconciliation;
- governance review/apply;
- ai/docs;
- release packaging.

Done when Snowflake has the same release discipline as AWS: real tests, evidence
audit and a stabilization matrix.

## Key Risks

| Risk | Mitigation |
| --- | --- |
| Account Usage latency delays evidence/cost rows. | Write immediate ContractForge evidence in-run; add reconciliation command for Account Usage enrichment. |
| historical looks possible but semantics are project-specific. | Keep `REVIEW_REQUIRED` until late-arriving, delete and effective-date policies are explicit and tested. |
| Snowflake can execute SQL but not general extraction. | Treat JDBC/HTTP/Kafka as review-required unless using pre-stage/native connector patterns. |
| Generated SQL grows into the runtime. | Keep stable runner target; generated SQL remains review/debug/deploy artifact. |
| Governance policies vary by role hierarchy and privileges. | Start validate-only/review-first; require explicit apply commands. |
| Cost tests consume credits. | Use minimal warehouse, explicit test gating and cleanup. |
| Snowpark tempts broader dependencies. | Keep Snowpark optional and only for semantics SQL cannot preserve. |

## Definition Of Done

`contractforge-snowflake` is ready for alpha when:

1. it has an independent wheel;
2. default import path is Snowflake-SDK-free;
3. planner returns correct statuses for all core contract sections;
4. append, overwrite and current-state upsert run in a real Snowflake account;
5. quality fail/warn/quarantine works for supported rule types;
6. canonical control tables are created and populated;
7. query tags join ContractForge run evidence to Snowflake query history;
8. project deployment supports schedule, timezone and dependencies;
9. unsupported/review-required semantics are explicit;
10. docs, site, AI and stabilization matrix are updated.
