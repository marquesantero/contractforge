# Adapter Technical Review Summary

Review date: 2026-06-05

Checklist: `docs/specs/adapter-technical-review-checklist.md`

Scope: AWS, Databricks, and Snowflake adapters. GCP is not implemented yet and
should use the same checklist before merge.

## Comparative Health Scores

| Adapter | Critical | High | Medium | Low | Health score |
| --- | ---: | ---: | ---: | ---: | ---: |
| AWS | 0 | 0 | 2 | 3 | 9.1/10 |
| Databricks | 0 | 0 | 0 | 0 | 10/10 |
| Snowflake | 0 | 0 | 3 | 0 | 9.2/10 |
| GCP | - | - | - | - | Not started |

## Important Corrections From Prior Report

- Snowflake does have root-level unit tests in this repo. The previous
  "zero unit tests" / CRITICAL finding is not valid.
- Several previous rows were marked as findings while their recommendations said
  "N/A" or "positive control." Those were removed from the regenerated reports.
- The regenerated reports include only verified actionable findings plus
  concise positive-control context in each executive summary.

## Recurring Patterns

### 1. Exception Text Needs Uniform Redaction

AWS optional evidence/operations result objects, Databricks error evidence stack
traces, and Snowflake reconciliation/runtime fallback warnings now redact
exception text before persisting or returning diagnostics.

### 2. Adapter-Local Helper Duplication

AWS generated schema-column and required-text helpers are centralized.
Databricks evidence SQL casts, runtime timestamp duplication, and repeated
mapping/list coercion now flow through adapter-local helpers. Snowflake now has
shared SQL/session, contract-extension, polling, and value-coercion helpers
used across reconciliation, schema policy, state, evidence, annotations, access,
maintenance, smoke paths, deployment rendering, quality scalar reads, execution
scalar reads, and pure SQL renderers.

### 3. Orchestration Functions Are Growing

Snowflake's central runtime function now delegates post-write governance,
operations, and runtime evidence recording to focused helpers, but larger module
splits remain a maintainability backlog. Databricks orchestration was
decomposed in this pass; keep new runtime behavior in focused helpers so
entrypoints stay narrow.

### 4. Deterministic Runtime Hooks Improved

Databricks now has deterministic hooks for both orchestrator run IDs and
evidence timestamp enrichment. Snowflake runner run IDs are injectable; use the
same pattern if future evidence clocks need deterministic injection.

### 5. Positive Security Baseline Is Strong

All current adapters enforce secret placeholders in important connector auth
paths, avoid importing cloud SDKs on the default core path, use structured
result types heavily, and have many root-level tests.

## Risk/Effort Matrix

|  | Low effort | High effort |
| --- | --- | --- |
| High risk | Corrected: AWS raw `str(exc)` result/evidence paths are redacted. | Continue splitting Snowflake evidence writer into per-table modules. |
| High risk | Corrected: Databricks CLI profile/target/job-key validation, subprocess timeout, and Snowflake connector option validation. | Continue decomposing large Snowflake runtime/project/state modules. |
| Low risk | Corrected: AWS and Snowflake polling interval lower bounds are centralized/clamped. | Corrected: duplicated AWS and Snowflake helpers were consolidated where behavior matched. |
| Low risk | Corrected: Snowflake `run_id` injection and connection factory injection in publish/project runtimes. | Use Databricks-style deterministic evidence clocks when refactoring AWS/Snowflake evidence paths. |

## Global Prioritization

1. Snowflake: continue splitting `evidence/writer.py` and project/state runtime
   modules before adding more runtime surface area.
2. Snowflake: keep decomposing `execute_snowflake_contract` into pipeline steps
   as new behavior is touched.
3. AWS: keep AST validation mandatory around generated Glue code execution.
4. Databricks: no open actionable review findings remain; keep parity gates
   green while using it as the GCP adapter reference.

## Per-Adapter Reports

- [AWS Adapter Review](./aws-adapter-review.md)
- [Databricks Adapter Review](./databricks-adapter-review.md)
- [Snowflake Adapter Review](./snowflake-adapter-review.md)
