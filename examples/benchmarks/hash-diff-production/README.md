# Hash-Diff Production Benchmark

This fixture is the executable starting point for the AWS, GCP and Snowflake
`hash_diff_upsert` production-certification gates.

The checked-in CSV waves are intentionally small. They validate contract shape,
rendering, report SQL and failure semantics before operators upload/generated
the `small`, `medium` or `large` datasets described in
`docs/specs/hash-diff-production-benchmark-runbook.md`.

Required live cases:

- `initial_load`
- `no_change_replay`
- `changed_row_wave`
- `concurrent_or_overlap_guard`
- `duplicate_key_failure`
- `null_key_failure`

AWS:

```bash
contractforge-aws deploy-project examples/benchmarks/hash-diff-production/project.yaml \
  --environment examples/benchmarks/hash-diff-production/environments/aws.environment.yaml \
  --run \
  --wait \
  --record-cost-evidence \
  --audit-evidence \
  --athena-output-location s3://contractforge-aws-smoke-449112696824-us-east-1/athena-results/hash-diff-production/
```

GCP:

```bash
contractforge-gcp smoke examples/benchmarks/hash-diff-production/contracts/gcp/customers_hashdiff.ingestion.yaml \
  --environment examples/benchmarks/hash-diff-production/environments/gcp.environment.yaml \
  --execute \
  --allow-review-required \
  --runtime bq
```

Snowflake:

```bash
snow sql -c cfingestsvc-pat -f examples/benchmarks/hash-diff-production/snowflake/seed_tables.sql

contractforge-snowflake run-project examples/benchmarks/hash-diff-production/project.yaml \
  --environment examples/benchmarks/hash-diff-production/environments/snowflake.environment.yaml \
  --connection cfingestsvc-pat \
  --wait
```
