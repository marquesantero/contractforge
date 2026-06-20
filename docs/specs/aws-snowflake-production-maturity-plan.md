# AWS And Snowflake Production Maturity Plan

## Purpose

AWS and Snowflake are now stable-supported for their documented surfaces:

- `contractforge-aws`: `aws_glue_iceberg`
- `contractforge-snowflake`: `snowflake_sql_warehouse`

This plan starts the next maturity phase: moving from
`STABLE_SUPPORTED_SURFACE` to `stable_final=true` for the claims that are safe
to certify. It is deliberately evidence-led. A gate closes only when runtime
evidence, audit output, docs and status-report payloads all agree.

The source-of-truth stable-surface gates remain:

- [Databricks stable-surface evidence](../reports/databricks-stable-surface-evidence.json)
- [AWS stable-surface criteria](aws-ga-criteria.md)
- [AWS waiver registry](aws-ga-waivers.md)
- [Snowflake stable-surface criteria](snowflake-ga-criteria.md)
- [Snowflake waiver registry](snowflake-ga-waivers.md)

The machine-readable tracker for this plan is
[../reports/aws-snowflake-production-maturity-plan.json](../reports/aws-snowflake-production-maturity-plan.json).
Hash-diff production certification uses the shared
[hash-diff production benchmark runbook](hash-diff-production-benchmark-runbook.md).

## Maturity Levels

| Level | Meaning | Required evidence |
| --- | --- | --- |
| Stable supported surface | The documented production-use subset is validated and safe to adopt with explicit review boundaries. | Adapter status report, stable criteria, evidence manifest, E2E smoke evidence. |
| Production certified boundary | A previously review-required boundary is validated for a stated scope. | Runtime run ids, control-table audit, failure evidence, docs update, status-report update. |
| Stable final | All claimed production boundaries are certified or explicitly excluded from the stable claim without ambiguity. | `stable_final=true` in the adapter status report and no active blocker in the maturity tracker. |

## Shared Rules

1. No gate can close from renderer tests alone.
2. Every runtime gate needs success and failure evidence.
3. A benchmark gate must record dataset size, partitioning/clustering,
   concurrency, elapsed time, cost signal and retry behavior.
4. A governance gate must prove that access is neither broader nor narrower
   than the contract declares.
5. If a platform cannot preserve a semantic, the adapter must keep returning
   `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or `UNSUPPORTED`.
6. Waivers cannot cover platform isolation, plaintext secrets, data loss, false
   success evidence or over-broad access grants.

## Workstreams

### 1. Hash-Diff Production Certification

Goal: certify `hash_diff_upsert` beyond functional correctness.

| Adapter | Current state | Next action | Evidence target |
| --- | --- | --- | --- |
| AWS | Production benchmark passed for initial load, no-change replay, changed-row wave, overlap guard and key-failure cases. | Keep the benchmark in release validation and rerun after hash-diff runtime or packaging changes. | [AWS benchmark manifest](../reports/aws-hashdiff-production-benchmark.json). |
| Snowflake | Production benchmark passed for initial load, no-change replay, changed-row wave, overlap policy, key-failure cases, candidate-row metrics and query-history cost signals. | Keep the benchmark in release validation and rerun after hash-diff runtime, procedure or packaging changes. | [Snowflake benchmark manifest](../reports/snowflake-hashdiff-production-benchmark.json). |

Acceptance criteria:

- No duplicate merge keys can reach the write.
- No-change replay writes zero changed rows or records a no-op result.
- Changed-row wave updates only changed records.
- Concurrent execution either serializes safely or fails with redacted evidence.
- Cost and elapsed time are recorded per run.

### 2. Governance Equivalence Certification

Goal: certify adapter-owned governance behavior for the declared platform
surface.

| Adapter | Current state | Next action | Evidence target |
| --- | --- | --- | --- |
| AWS | Lake Formation consumer matrix passed for the checked table. Athena allowed/denied read validation passed with query ids, Glue Spark allowed/denied read validation passed with Glue run ids, the table is LF-registered, a reviewed DataCellsFilter is applied and broad `IAM_ALLOWED_PRINCIPALS` table access was revoked. | Keep the LF consumer matrix in release validation and rerun after Lake Formation, IAM or Glue runtime changes. | [AWS LF consumer matrix](../reports/aws-lake-formation-consumer-matrix.json). |
| Snowflake | Comments/tags validated; grants and validate-only access evidence are supported. The current connected account returns `Unsupported feature 'ROW ACCESS POLICY'`, so row access and masking policy enforcement are excluded from stable-final for this account. | Keep the exclusion in status reports; promote only after rerunning the smoke on an account where native policy features are available. | [Snowflake access-policy smoke](../reports/snowflake-access-policy-smoke.json). |

Acceptance criteria:

- Principal with allowed access can read exactly the declared columns/rows.
- Principal without allowed access is denied or masked as declared.
- Evidence records applied, validate-only and skipped states correctly.
- Destructive revokes remain blocked unless explicitly enabled by a reviewed
  contract.

### 3. Continuous Ingestion And Streaming Boundaries

Goal: decide which streaming/continuous surfaces become certified and which
remain outside the stable claim.

| Adapter | Current state | Next action | Evidence target |
| --- | --- | --- | --- |
| AWS | Azure Event Hubs through Kafka available-now path is validated. MSK Serverless now has live Glue available-now evidence with checkpoint rerun, stream rows, cost rows and Athena audit. Confluent-compatible bootstrap plus AWS Secrets Manager credential metadata remain optional compatibility evidence. | Keep MSK Serverless in release validation. Promote the Confluent-compatible branch only when claiming cross-provider Confluent Cloud compatibility on AWS. | [AWS Kafka provider matrix](../reports/aws-kafka-provider-matrix.json). |
| Snowflake | Batch staged files validated. Snowpipe, Streams, Snowpipe Streaming and Kafka connector ingestion are explicitly excluded from stable-final until a separate runtime/evidence mapping is implemented and certified. | Keep the exclusion in status reports; promote only after connector/runtime recovery and evidence semantics are validated. | [Snowflake continuous ingestion decision](../reports/snowflake-continuous-ingestion-decision.json). |

Acceptance criteria:

- Provider-specific semantics are documented.
- Offset/checkpoint recovery is auditable.
- Failure paths produce redacted error evidence.
- Unsupported providers remain explicit in planner output.

### 4. Historical Semantics Decision

Goal: decide whether `historical` and `snapshot_reconcile_soft_delete` are in scope
for each adapter's final stable claim.

| Adapter | Current state | Next action | Evidence target |
| --- | --- | --- | --- |
| AWS | Excluded from stable-final. historical and snapshot soft-delete stay review-required until Databricks/AWS parity contracts prove late-arriving changes, deletes, replay idempotency and validity-window behavior on Iceberg. | Keep the exclusion in status reports; promote only after E2E parity evidence exists. | [AWS historical semantics decision](../reports/aws-historical-semantics-decision.json). |
| Snowflake | Excluded from stable-final. historical and snapshot soft-delete stay review-required until Databricks/Snowflake parity contracts prove late-arriving changes, deletes, replay idempotency and validity-window behavior in Snowflake SQL. | Keep the exclusion in status reports; promote only after E2E parity evidence exists. | [Snowflake historical semantics decision](../reports/snowflake-historical-semantics-decision.json). |

Acceptance criteria:

- If excluded, docs and status reports must say the stable claim excludes the
  behavior.
- If implemented, Databricks/AWS/Snowflake parity contracts must prove matching
  logical history output.

### 5. Snowflake Task Graph Live Certification

Goal: keep Snowflake project task graph execution in the release validation set.

Status: `PASS`. After task creation/execution grants were provisioned, the live
smoke recorded on 2026-06-09 deployed the graph, executed the root task, waited
for both tasks to reach `SUCCEEDED`, verified bronze/silver counts and cleaned
up smoke artifacts. The evidence is recorded in
[../reports/snowflake-task-graph-live-smoke.json](../reports/snowflake-task-graph-live-smoke.json).

Required runtime grants:

```sql
GRANT CREATE TASK ON SCHEMA <database>.<schema> TO ROLE <role>;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE <role>;
```

Acceptance criteria:

- `contractforge-snowflake smoke-task-graph --execute --execute-cleanup`
  creates tasks, executes the root task and reaches terminal success.
- Task history polling records terminal task states.
- Cleanup removes task, procedure, table and stage smoke artifacts.

## Execution Order

1. Snowflake task graph grants and live smoke.
2. AWS and Snowflake hash-diff benchmark projects.
3. AWS Lake Formation consumer-engine matrix.
4. Snowflake access policy live smoke.
5. AWS Kafka MSK release validation.
6. Snowflake Snowpipe/Streams exclusion review.
7. historical/snapshot soft-delete scope decision.
8. Update each adapter status report and evidence manifest when a gate closes.

## Definition Of Done

The maturity plan is complete when:

- every tracker item is `PASS` or explicitly `EXCLUDED_FROM_STABLE_FINAL`;
- `contractforge-databricks stabilization-report --strict-final` exits `0`;
- `contractforge-aws stabilization-report --strict-final` exits `0`;
- `contractforge-snowflake stabilization-report --strict-final` exits `0`;
- release notes link the evidence manifests and the maturity tracker;
- full test suite passes.
