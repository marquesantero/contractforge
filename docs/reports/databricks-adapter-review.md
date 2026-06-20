# Report: Databricks Adapter (`contractforge_databricks`)

Review date: 2026-06-05

Checklist: `docs/specs/adapter-technical-review-checklist.md`

Scope: `adapters/databricks/src/contractforge_databricks`

## Executive Summary

The Databricks adapter is well structured and has strong positive controls:
secret placeholder enforcement, centralized SQL quoting helpers, lazy optional
runtime imports, Protocol-style injection for SQL execution, and extensive
root-level tests (`tests/test_databricks_*.py`). It cleanly separates many
planning, rendering, runtime, and evidence concerns.

Risk level: LOW. The most urgent security/runtime and maintainability findings
from the initial pass were corrected: error stack traces are redacted,
Databricks CLI profile/target/job-key values are validated, CLI calls have a
timeout, RDS IAM cache keys are hashed incrementally, Spark fallback paths now
emit debug diagnostics, duplicated mapping/list and evidence SQL helpers are
centralized, optional lazy imports use `importlib`, source connector groups are
named, serverless detection is cached per session, the main orchestrator is
decomposed into focused context/finalization helpers, the orchestrator accepts a
deterministic run-id factory, and evidence timestamp enrichment accepts a
deterministic clock.

## Findings By Dimension

### Security

No open actionable security findings remain from this pass. Corrected items are
covered by `tests/test_databricks_runtime_errors.py`,
`tests/test_databricks_deploy.py`, and `tests/test_databricks_rds_iam_runtime.py`.

### Development Standards

No open actionable development-standard findings remain from this pass.
Optional PySpark imports now use `importlib.import_module`, and adapter-wide
Ruff checks pass.

### Code Reuse

No open actionable code-reuse findings remain from this pass. Repeated
mapping/list coercion now flows through `contractforge_databricks.coercion`,
and repeated evidence SQL casts/timestamps flow through
`contractforge_databricks.evidence.helpers`.

### Code Quality

No open actionable code-quality findings remain from this pass. The runtime
orchestrator delegates context construction and finalization to
`runtime/orchestration_context.py`, and JDBC source aliases are now a named
module constant.

### Performance

No open actionable performance findings remain from this pass. Serverless
detection now caches by Spark session identity.

### Testability

No open actionable testability findings remain from this pass. Evidence SQL
default timestamp enrichment can now receive an injected deterministic clock
through direct render functions or `EvidenceWriter`.

## Severity Metrics

| Level | Count |
| --- | ---: |
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

Health score: 10/10

Checklist items violated: 0 open actionable items. Positive controls include
secret placeholder enforcement, SQL quoting, source security validation,
Protocol-friendly SQL runners, adapter-local coercion/evidence helpers,
deterministic runtime/evidence hooks, and broad root-level adapter tests.

## Top 3 Immediate Actions

1. Keep new runtime orchestration behavior inside focused context/finalization
   helpers instead of growing `ingest_databricks_contract`.
2. Reuse `coercion.py` and `evidence/helpers.py` for new adapter modules that
   need mapping/list normalization or evidence SQL fragments.
3. Preserve the current adapter-wide Ruff and Databricks test gates before
   adding GCP parity code.
