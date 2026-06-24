# ContractForge AWS Adapter

`contractforge-aws` is the AWS adapter package for ContractForge.

The initial target is `aws_glue_iceberg`: AWS Glue Spark jobs writing Apache Iceberg tables in Amazon S3, cataloged through AWS Glue Data Catalog and governed by AWS Lake Formation.

The base package declares capabilities, calls the core planner and renders review artifacts. The documented `aws_glue_iceberg` surface is stable-supported: real AWS projects have validated rendering, S3 publication, Glue job registration, runtime execution, evidence audit, failure evidence, cleanup planning, reference hash-diff behavior and Lake Formation consumer-engine behavior through ContractForge commands. SCD2 and snapshot soft delete are excluded from stable-final, while generic streaming providers and contract-specific governance or workload SLA claims remain explicit review or final-certification items.

JDBC credentials are never baked into generated scripts: `{{ secret:scope/key }}` placeholders render an AWS Secrets Manager lookup that resolves when the Glue job runs, and inline passwords are refused. JDBC `auth.type: rds_iam` renders a runtime RDS IAM token (`rds.generate_db_auth_token`) instead of a static password.

The default install intentionally does not depend on `boto3`. Runtime/apply commands that call AWS APIs will live behind the optional `runtime` extra.

## Install

```bash
pip install contractforge-core contractforge-aws
```

For AWS API helpers such as S3 artifact publishing:

```bash
pip install "contractforge-aws[runtime]"
```

## Minimal usage

```python
from contractforge_aws import plan_aws_contract, render_aws_contract

contract = {
    "source": {"type": "s3", "path": "s3://landing/orders", "format": "parquet"},
    "target": {"catalog": "glue", "schema": "bronze", "table": "orders"},
    "mode": "append",
}

result = plan_aws_contract(contract)
print(result.status)

artifacts = render_aws_contract(contract)
print(artifacts.artifacts["glue_bronze_orders.glue_job.py"])
```

The SCD1 upsert script uses Iceberg `MERGE INTO` and validates missing, null and duplicate merge keys before executing the merge. Rendered Glue job definitions include the adapter-owned Iceberg Spark extension startup configuration through `--conf`; user-provided Glue `default_arguments` cannot override this managed argument.

The runtime renderer preserves top-level `select_columns`, `column_mapping`, `filter_expression`, portable transforms for `cast`, `standardize`, `derive`, `composite_keys` and `deduplicate`, plus supported `shape` sections (`parse_json`, arrays, columns and flattening). If a section cannot be preserved faithfully, the adapter emits a review artifact instead of a runnable Glue job.

Quality rules are evaluated in-job. Rules with faithful AWS Glue Data Quality equivalents (`required_columns`, `not_null`, `unique_key`, `row_count_minimum`, `accepted_values`, `max_null_ratio`) use `EvaluateDataQuality` against a DQDL ruleset. `expression` rules use Spark SQL DataFrame filters because they have no faithful DQDL mapping. Enforcement stays consistent: `abort` rules raise and fail the run; `warn` rules are recorded and continue; row-level `quarantine` rules write offending rows to `ctrl_ingestion_quarantine`, remove them before the target write and record quality evidence. Every evaluated rule appends one immutable row to `ctrl_ingestion_quality`.

Portable quality rules are also rendered as an AWS Glue Data Quality DQDL ruleset (`*.quality.dqdl`) for native evaluation:

```python
from contractforge_aws import render_aws_quality_dqdl

dqdl = render_aws_quality_dqdl(contract)
print(dqdl)  # Rules = [ ColumnExists "order_id", IsUnique "order_id", ... ]
```

`required_columns`, `not_null`, `unique_key`, `accepted_values`, `row_count_minimum` and `max_null_ratio` map to DQDL rules; `expression` rules are reported as unmapped rather than approximated.

The `access` section renders Lake Formation review/apply artifacts (`*.lakeformation.json`):

```python
from contractforge_aws import render_aws_lake_formation_plan

plan = render_aws_lake_formation_plan(contract)
```

`access.grants` become applyable `GrantPermissions` requests. `access.row_filters` and `access.column_masks` render `CreateDataCellsFilter` scaffolds: row filters are fail-closed (`false`) because Lake Formation uses a SQL `FilterExpression`, not the contract's row-filter function; column masks exclude the column (LF has no value-masking function). These two stay `REVIEW_REQUIRED` in planning.

When Lake Formation artifacts are rendered, the adapter also renders `*.lakeformation_evidence.sql` for `ctrl_ingestion_access`: grants are recorded as `PLANNED`, while row-filter and column-mask scaffolds are recorded as `REVIEW_REQUIRED` until a reviewer completes the Lake Formation expression/design.

## Publish artifacts to S3

```python
from contractforge_aws import publish_aws_contract_artifacts_to_s3

published = publish_aws_contract_artifacts_to_s3(
    contract,
    bucket="contractforge-artifacts",
    prefix="dev/orders",
)

print([item.uri for item in published])
```

CLI:

```bash
contractforge-aws publish-s3 contract.yaml --bucket contractforge-artifacts --prefix dev/orders
```

## Register a Glue job

After publishing the generated `.glue_job.py` artifact to S3, register or update an AWS Glue job definition:

```python
from contractforge_aws import register_aws_glue_job

registered = register_aws_glue_job(
    job_name="cf-orders",
    role_arn="arn:aws:iam::123456789012:role/ContractForgeGlueRole",
    script_s3_uri="s3://contractforge-artifacts/dev/orders/glue_bronze_orders.glue_job.py",
)

print(registered.action)
```

CLI:

```bash
contractforge-aws register-glue-job --job-name cf-orders --role-arn arn:aws:iam::123456789012:role/ContractForgeGlueRole --script-s3-uri s3://contractforge-artifacts/dev/orders/glue_bronze_orders.glue_job.py
```

## Start and inspect a Glue job run

```python
from contractforge_aws import get_aws_glue_job_run_status, start_aws_glue_job_run

run = start_aws_glue_job_run(
    job_name="cf-orders",
    arguments={"--contractforge-run-id": "run-123"},
)

status = get_aws_glue_job_run_status(job_name="cf-orders", run_id=run.run_id)
print(status.state)
```

Starting a job is intentionally separate from the post-hoc reconciliation API. The rendered Glue job itself writes evidence in-job: after the Iceberg write it reads the target snapshot (table version + summary), records AWS state as append-only observations in `ctrl_ingestion_state`, appends source metadata to `ctrl_ingestion_metadata`, appends an OpenLineage-compatible event to `ctrl_ingestion_lineage`, and only then appends the final successful row to `ctrl_ingestion_runs`. This prevents failed post-write evidence steps from leaving false successful run rows. Run evidence fills platform-neutral columns (`source_*`, `rows_read`, `rows_written` from `added-records`, `table_version_after` from the snapshot id, `operation_metrics_json`, `runtime_type`, `runtime_entrypoint`, engine/Python versions, etc.) per the [evidence mapping matrix](../../docs/specs/evidence-mapping-matrix.md). Available-now streaming jobs write per-micro-batch rows to `ctrl_ingestion_streams` and roll those totals into final run evidence. If the Glue script fails, it writes one row to `ctrl_ingestion_errors` and re-raises. The state, run, metadata, lineage, stream and error control tables are created (`CREATE TABLE IF NOT EXISTS`) by the job if missing.

## Reconcile Glue run evidence

```python
from contractforge_aws import reconcile_aws_glue_job_run_evidence

evidence = reconcile_aws_glue_job_run_evidence(
    job_name="cf-orders",
    run_id=run.run_id,
    target_table="glue.bronze.orders",
    mode="append",
)

print(evidence.run.status)
print(evidence.cost)
```

This maps Glue `JobRun` metadata into core evidence record objects. It does not persist control-table rows yet.

To render Iceberg `INSERT` statements for review or an explicit apply step:

```python
from contractforge_aws import render_aws_glue_job_run_evidence_sql

sql = render_aws_glue_job_run_evidence_sql(
    job_name="cf-orders",
    run_id=run.run_id,
    target_table="glue.bronze.orders",
    mode="append",
    database="contractforge_ops",
)
```

For query-only operational cost reporting over ContractForge evidence tables:

```python
from contractforge_aws import CostModel, render_aws_operational_cost_query

query = render_aws_operational_cost_query(
    database="lake_bronze_ops",
    cost_model=CostModel(dpu_hour_usd=0.44),
)
```

The query estimates cost only from `ctrl_ingestion_cost.signal_name = 'glue_dpu_seconds'`. If no explicit DPU-hour rate is supplied, cost fields stay `NULL`.

## Minimal AWS smoke test

The adapter includes a cost-gated smoke runner for the smallest real AWS validation path:

- creates/uses a tagged S3 bucket;
- uploads a tiny JSON input file;
- creates/uses a tagged Glue IAM role;
- renders and publishes ContractForge AWS artifacts through the adapter;
- registers a Glue Spark/Iceberg job;
- optionally starts one `overwrite` run.

Dry-run is the default and does not call AWS:

```bash
contractforge-aws smoke-minimal \
  --account-id 123456789012 \
  --bucket contractforge-aws-smoke-123456789012-us-east-1 \
  --max-estimated-cost-usd 1.00
```

Real execution requires both `--execute` and a cost ceiling that covers the configured timeout:

```bash
contractforge-aws smoke-minimal \
  --account-id 123456789012 \
  --bucket contractforge-aws-smoke-123456789012-us-east-1 \
  --max-estimated-cost-usd 1.00 \
  --execute \
  --wait
```

The default ceiling estimate is based on 2 `G.1X` workers, 10 minutes, and `$0.44` per DPU-hour. The actual successful smoke run is normally much cheaper, but the guardrail uses timeout ceiling rather than optimistic runtime.

## Scope

See `docs/specs/aws-adapter.md` and `docs/adapters/aws.md` in the repository root.
