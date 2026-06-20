# Report: Snowflake Adapter (`contractforge_snowflake`)

Review date: 2026-06-05

Checklist: `docs/specs/adapter-technical-review-checklist.md`

Scope: `adapters/snowflake/src/contractforge_snowflake`

## Executive Summary

The Snowflake adapter has advanced quickly and now covers planning, runtime
execution, cost reconciliation, lineage/explain evidence, project deployment,
smoke tests, schema policy, access, annotations, staged-file sources, and write
modes. It has root-level unit coverage in this repository, including
`tests/test_snowflake_adapter.py`, `tests/test_snowflake_sources.py`,
`tests/test_snowflake_write_modes.py`, `tests/test_snowflake_schema_policy.py`,
and smoke-related tests. Therefore, the previous "zero unit tests" finding is
not valid for this repo.

Risk level: LOW-MEDIUM. Raw exception strings in reconciliation warnings and
the top-level runtime failure boundary were corrected in this pass, broad
connector option pass-through now uses an allowlist, non-CLI publish/project
paths accept injected connection factories, and the top-level runner accepts a
caller-supplied run id. Schema-inspection fallback, lock-release failure, and
unknown `extensions.snowflake` paths now emit redacted diagnostics or planning
warnings. The remaining risks are maintainability-focused: large evidence,
project, state, and runtime modules should keep being split before more runtime
surface area is added.

## Findings By Dimension

### Security

No open actionable security findings remain from this pass. Connector options
are allowlisted before `snowflake.connector.connect(**options)`, and runtime
failure paths redact exception text before passing it to evidence writers.

### Development Standards

No open actionable development-standard findings remain from this pass. Schema
inspection fallback records a redacted warning in schema-change diagnostics,
lock release returns `status`/`warning`, and unknown `extensions.snowflake`
keys produce `SNOWFLAKE_UNKNOWN_EXTENSION` planning warnings.

### Code Reuse

No open actionable code-reuse findings remain from this pass. Shared
`sql.py`, `session_ops.py`, `contract_extensions.py`, `polling.py`, and
`values.py` helpers cover the repeated SQL literal rendering, session
execution/scalar reads, extension access/warnings, polling lower bounds, and
small mapping/list/string coercions. Specialized wrappers remain only where
they return richer statement metadata or manage connector/file/project
operations.

### Code Quality

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |
| MEDIUM | Evidence writer module is too large | `evidence/writer.py` | 879-line module containing all evidence table SQL builders and record functions. | Split into `evidence/tables/` modules or at least per-table private builder modules. |
| MEDIUM | Project runtime module is too large | `runtime/project.py` | 600-line module combining project I/O, deployment orchestration, task waiting, cleanup planning, and connection management. | Extract project file loading, connection ownership, and task waiting into smaller modules. |
| MEDIUM | State runtime mixes idempotency, locks, watermarks, and recording | `state/runtime.py` | 381-line module with several independent state responsibilities. | Split into `state/idempotency.py`, `state/locks.py`, and `state/watermarks.py` when making next state changes. |

`execute_snowflake_contract` now delegates post-write governance/operations and
runtime evidence recording to focused helpers. Continue extracting pipeline
steps opportunistically as new behavior is added.

### Performance

No open actionable performance findings remain from this pass. Cost
reconciliation and project task waits use the shared polling clamp helper.

### Testability

No open actionable testability findings remain from this pass. Runtime publish
and project helpers accept optional connection factories, and
`run_snowflake_contract` accepts an optional caller-supplied `run_id`.

## Severity Metrics

| Level | Count |
| --- | ---: |
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 0 |

Health score: 9.2/10

Checklist items violated: 3 actionable items. Positive controls include
identifier quoting, evidence redaction in primary writers, validated smoke
prefixes, redacted reconciliation/runtime/fallback warnings, extension
guardrails, connector option allowlisting, connection factory injection for
non-CLI publish/project paths, caller-supplied Snowflake runner IDs, shared
SQL/session/polling/value helpers, centralized SQL literal rendering, runtime
dependency isolation, root-level unit coverage, and live smoke cleanup
verification.

## Top 3 Immediate Actions

1. Split `evidence/writer.py` into per-table writer modules.
2. Extract project file loading, connection ownership, and task waiting from
   `runtime/project.py`.
3. Split state idempotency, locks, watermarks, and recording when those paths
   are next changed.
