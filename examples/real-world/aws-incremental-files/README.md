# AWS Incremental Files

This project is the dedicated AWS stabilization fixture for portable
`incremental_files` semantics. It validates that an ingestion project can be
declared entirely through ContractForge contracts while the AWS adapter maps the
intent to Glue/S3/Iceberg artifacts with job bookmarks enabled.

## Purpose

- Source: S3 CSV files split into upload waves.
- Target: Iceberg table in Glue Catalog.
- Write mode: `hash_diff_upsert`.
- Incremental behavior: Glue job bookmarks for the S3 file source.
- Evidence: canonical ContractForge control tables in the configured evidence
  database.

## Local validation

```powershell
uv run contractforge-aws deploy-project examples/real-world/aws-incremental-files/project.yaml `
  --dry-run `
  --summary-only
```

Dry-run loads the project, plans the contract, renders AWS artifacts and
compiles the generated Glue Python without AWS API calls.

## Runtime validation

After AWS credentials are refreshed and the seed files are uploaded to the S3
prefix declared in `project.yaml`:

```powershell
uv run contractforge-aws deploy-project examples/real-world/aws-incremental-files/project.yaml `
  --run `
  --wait `
  --max-wait-seconds 3600
```

Acceptance:

- first run processes wave 1;
- second run with no new files does not duplicate rows;
- after uploading wave 2, the next run picks up only new files;
- `ctrl_ingestion_state` records bookmark-oriented incremental evidence;
- `ctrl_ingestion_runs.write_committed = true` for successful runs.
