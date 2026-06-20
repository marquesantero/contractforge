# S3 File Medallion E2E

This project validates the AWS adapter with file and object-storage ingestion,
without JDBC or external APIs.

It uses S3 CSV files as the source, AWS Glue job bookmarks for incremental file
tracking, Apache Iceberg target tables and ContractForge evidence tables.

## Coverage

- `source.type: incremental_files` over S3;
- CSV reader options;
- Glue job bookmarks;
- `hash_diff_upsert` on the bronze table;
- `overwrite` SQL promotions;
- quality `abort`, `warn` and row-level `quarantine`;
- annotations, operations and Iceberg evidence/control tables;
- S3 artifact publication and Glue job deployment through `contractforge-aws`.

## Seed Data

Local seed files live under `data/orders/`.

Upload them before running the AWS project:

```powershell
$AWS_REGION = "us-east-1"
$AWS_BUCKET = "contractforge-aws-smoke-000000000000-us-east-1"

aws s3 cp `
  examples/real-world/s3-file-medallion/data/orders/ `
  s3://$AWS_BUCKET/data/s3-file-medallion/orders/ `
  --recursive `
  --region $AWS_REGION
```

## Run

Run contracts in `project.yaml` order:

1. `bronze_s3_orders_files`
2. `silver_s3_orders_daily`
3. `gold_s3_revenue_by_status`

The first run should process the seed files. A second run with no new files
should be a bookmark no-op for the bronze read, while downstream overwrite
contracts remain deterministic.

