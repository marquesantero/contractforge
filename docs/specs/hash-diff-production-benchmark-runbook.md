# Hash-Diff Production Benchmark Runbook

## Purpose

This runbook defines the shared benchmark required before AWS, GCP and
Snowflake can close their `hash_diff_upsert` production-certification gates.

It is not a performance marketing test. The goal is to prove bounded behavior:
correct changed-row detection, safe replay, safe concurrency or overlap
handling, redacted failure evidence and cost attribution.

The adapter-specific benchmark manifests are:

- [AWS hash-diff production benchmark](../reports/aws-hashdiff-production-benchmark.json)
- [GCP BigQuery hash-diff production benchmark](../reports/gcp-bigquery-hashdiff-production-benchmark.json)
- [Snowflake hash-diff production benchmark](../reports/snowflake-hashdiff-production-benchmark.json)

The shared executable fixture is:

- `examples/benchmarks/hash-diff-production/project.yaml`

## Dataset Shape

Use the same logical source schema on both platforms:

| Column | Type | Purpose |
| --- | --- | --- |
| `customer_id` | integer/string | Merge key. |
| `segment` | string | Low-cardinality change dimension. |
| `status` | string | Medium-cardinality change dimension. |
| `balance` | decimal | Numeric change dimension. |
| `updated_at` | timestamp | Ordering and audit dimension. |
| `payload_hash_noise` | string | Non-key field to increase row width. |

Recommended benchmark sizes:

| Size | Rows | Purpose |
| --- | ---: | --- |
| `small` | 10,000 | Fast correctness and failure-path check. |
| `medium` | 1,000,000 | Routine production-certification run. |
| `large` | 10,000,000+ | Optional capacity and cost envelope check. |

## Required Cases

| Case | Expected result |
| --- | --- |
| `initial_load` | Target receives all source rows and records successful run/cost evidence. |
| `no_change_replay` | Adapter records no duplicate rows and either zero changed rows or a no-op run. |
| `changed_row_wave` | Only changed rows are merged; unchanged rows remain untouched. |
| `concurrent_or_overlap_guard` | Concurrent writers serialize safely or one run fails with redacted evidence. |
| `duplicate_key_failure` | Duplicate merge keys fail before write and record redacted failed-run/error evidence. |
| `null_key_failure` | Null merge keys fail before write and record redacted failed-run/error evidence. |

## Required Metrics

Every live benchmark record must include:

- adapter and subtarget;
- package version and git commit;
- dataset size and changed-row count;
- run id or native job/query id;
- elapsed seconds;
- rows read, rows written and hash-diff candidate rows;
- cost signal rows;
- table version or equivalent post-write state;
- failure evidence for negative cases;
- cleanup status.

## AWS Command Pattern

```bash
contractforge-aws deploy-project <benchmark-project.yaml> \
  --run \
  --wait \
  --record-cost-evidence \
  --audit-evidence \
  --athena-output-location <s3-query-output>

contractforge-aws performance-report <hash-diff-contract.yaml> \
  --environment <aws.environment.yaml> \
  --run \
  --athena-output-location <s3-query-output>
```

AWS evidence must include Glue job run ids, Athena audit rows, Iceberg snapshot
metrics and `ctrl_ingestion_cost` rows with `glue_dpu_seconds`.

## GCP Command Pattern

```bash
contractforge-gcp smoke <hash-diff-contract.yaml> \
  --environment <gcp.environment.yaml> \
  --execute \
  --allow-review-required \
  --runtime bq
```

GCP evidence must include BigQuery job ids, DML row counts, bytes processed,
bytes billed, slot milliseconds, failed-run evidence for negative cases and a
readback proving no duplicate rows after replay or concurrent execution.

## Snowflake Command Pattern

```bash
contractforge-snowflake run-project <benchmark-project.yaml> \
  --connect-options <connection.yaml> \
  --wait

contractforge-snowflake cost-report \
  --connect-options <connection.yaml> \
  --environment <environment.json> \
  --run-id <contractforge-run-id> \
  --target-table <qualified-target-table> \
  --wait \
  --max-wait-seconds 3600
```

Snowflake evidence must include query ids, control-table rows,
`QUERY_HISTORY`/query-attribution cost signals when Account Usage has caught
up, and task/procedure ids when the project path is used.

## Closure Rule

The adapter-specific benchmark manifest may move from `READY_TO_RUN` to `PASS`
only after:

1. all required cases have live evidence;
2. cost and state evidence are present;
3. failure cases show redacted error evidence;
4. cleanup is verified;
5. the matching maturity tracker gate is updated.
