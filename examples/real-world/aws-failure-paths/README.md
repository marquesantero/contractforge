# AWS Failure Paths

This project validates AWS adapter failure evidence with normal ContractForge
contracts. It is expected to fail at runtime and should not require Glue Studio
edits or generated script workarounds.

The project covers two controlled cases:

- `quality_abort_orders`: reads a valid CSV file, evaluates an abort-level
  quality expression that intentionally fails, writes quality evidence, writes
  error evidence and records a failed run.
- `missing_s3_source`: reads a missing S3 object path, writes error evidence
  and records a failed run.

## Runtime Contract

Use the same AWS CLI flow as successful projects:

```powershell
$env:AWS_REGION = "us-east-1"
$project = "examples/real-world/aws-failure-paths"
$environment = "$project/environments/aws.environment.yaml"

aws s3 cp "$project/data/orders/" `
  "s3://contractforge-aws-smoke-449112696824-us-east-1/data/aws-failure-paths/orders/" `
  --recursive `
  --region $env:AWS_REGION

$contracts = @(
  "$project/contracts/aws/quality_abort_orders/quality_abort_orders.ingestion.yaml",
  "$project/contracts/aws/missing_s3_source/missing_s3_source.ingestion.yaml"
)

foreach ($contract in $contracts) {
  uv run contractforge-aws deploy `
    $contract `
    --environment $environment
}
```

When starting the jobs, a terminal failed state is the expected result. Validate
the failure through the evidence tables, not through manual Glue edits.
