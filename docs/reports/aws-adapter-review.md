# Report: AWS Adapter (`contractforge_aws`)

Review date: 2026-06-05

Checklist: `docs/specs/adapter-technical-review-checklist.md`

Scope: `adapters/aws/src/contractforge_aws`

## Executive Summary

The AWS adapter is mature and has a strong security posture. Credential handling
is intentionally placeholder-based, rendered Glue artifacts resolve secrets at
runtime, and primary evidence/governance paths use redaction helpers. The
adapter also has broad root-level test coverage (`tests/test_aws_*.py`).

Risk level: LOW. Optional runtime result errors are redacted, generated evidence
schema-column helpers and required-text validation now flow through shared AWS
helpers, and Athena/Glue wait loops clamp minimum polling intervals. The
`exec()`-based library runner remains a notable trust boundary, but the current
implementation validates generated scripts with AST checks and blocks dangerous
calls/imports before execution.

## Findings By Dimension

### Security

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |
| MEDIUM | Dynamic execution trust boundary must remain explicit | `adapters/aws/src/contractforge_aws/runtime/library_runner.py:42` / `run_contractforge_aws_library` | `exec(compile(generated, ...), namespace)` executes adapter-rendered Glue code in-process. | Keep AST validation mandatory. Document the trust boundary in the module docstring and add a regression test that dangerous rendered code remains blocked. |

Optional evidence/operations runtime result objects now redact exception text
before returning structured errors.

### Development Standards

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |
| LOW | Dependencies use ranges rather than exact pins | `adapters/aws/pyproject.toml` | Runtime extras use `boto3>=1.34`, `botocore[crt]>=1.34`. | Acceptable for a library package, but release validation should keep using `uv lock` / CI lock resolution and vulnerability scanning before publishing. |

### Code Reuse

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |
| LOW | Mapping helper duplicated | `environment.py:40`, `evidence/run_metadata.py:41`, `operations/sql.py:97`, `rendering/iam_s3.py:66` | `_mapping(value)` is repeated with the same behavior. | Consolidate into an adapter-local helper module when touching those files next. |

Shared `contractforge_aws.schema_columns.schema_columns` and
`contractforge_aws.validation.required_text` helpers now cover the generated
schema-column and Glue required-text paths that were duplicated before.

### Code Quality

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |
| MEDIUM | Generated code renderers are hard to audit at scale | `rendering/glue_job.py`, `rendering/streaming_job.py`, `evidence/*_runtime.py`, `schema/runtime.py` | Runtime Python is assembled as string lists and joined. | Keep compile/AST tests broad. Prefer small renderer helpers over large inline string blocks when adding new runtime evidence behavior. |

### Performance

No open actionable performance findings remain from this pass. Athena and Glue
wait loops now clamp minimum polling intervals.

### Testability

| Severity | Checklist item | Location | Code evidence | Recommendation |
| --- | --- | --- | --- | --- |
| LOW | Some smoke paths instantiate SDK session internally | `smoke/runner.py` | The smoke runner is integration-oriented and creates runtime clients internally. | Acceptable for smoke tests. Keep unit-testable runtime helpers accepting injected clients, as they do today. |

## Severity Metrics

| Level | Count |
| --- | ---: |
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 3 |

Health score: 9.1/10

Checklist items violated: 5 actionable items. Several checklist items were
assessed as positive controls, especially secret placeholder enforcement,
redaction in primary and optional evidence paths, SDK client injection, clamped
polling waits, shared generated-runtime helpers, and AST validation of rendered
Glue scripts.

## Top 3 Immediate Actions

1. Keep AST validation mandatory around `runtime/library_runner.py`.
2. Consolidate the remaining simple mapping helpers when those files are next
   touched.
3. Keep generated-code compile/AST tests broad as rendered Glue artifacts grow.
