# Supabase JDBC Medallion E2E

This project validates that the same ContractForge ingestion intent can run
against Supabase/PostgreSQL on Databricks and AWS with only platform binding
differences.

It intentionally uses a shared connection file:

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
```

The connection owns JDBC endpoint and secret references. Each dataset contract
owns only dataset-specific details: source table/query intent, logical table
references, partitioning, transforms, quality, write mode and target.

## Coverage

The project exercises:

- shared `connection` source resolution through `project://`;
- portable downstream table refs through `source.ref` and `{{ table_ref:... }}`;
- JDBC/PostgreSQL with partitioned reads and fetch size;
- `hash_diff_upsert`, `upsert` and `overwrite`;
- SQL source contracts with joins and window functions;
- JSON parsing, array explode, standardization, derived columns and dedupe;
- quality rules with `abort`, `warn` and row-level `quarantine`;
- annotations, operations metadata, evidence/control tables and source state;
- Databricks Asset Bundle deployment and AWS Glue Iceberg rendering/runtime.

## Seed Data

The test uses the existing ContractForge Supabase schema:

```text
cf_supabase_newcore_demo
```

Expected source scale:

| Table | Rows |
| --- | ---: |
| `products` | 100,000 |
| `product_movements` | 1,000,500 |

The movement table contains intentional duplicate business keys and a small
number of invalid quantities so quality quarantine and deduplication are
observable.

Databricks serverless blocks Spark JDBC writes to external databases. The DAB
therefore starts with a preflight task that reads and validates Supabase counts.
The seed itself is an external test setup step, not part of the ingestion
runtime.

## Databricks

Databricks uses the DAB project in this folder. The workspace must already have
the following secrets in scope `contractforge-secrets`:

- `supabase-jdbc-url`
- `supabase-user`
- `supabase-password`

The DAB job tasks validate the Supabase source, execute each split bundle with
`ingest_databricks_bundle`, and validate target/control-table counts.

## AWS

AWS uses the same contract shape and the same secret placeholder names. Before
running the Glue jobs, create an AWS Secrets Manager secret named
`contractforge-secrets` with JSON keys:

- `supabase-jdbc-url`
- `supabase-user`
- `supabase-password`

Runtime artifacts should be rendered from the contract files and uploaded to the
AWS artifact bucket used by the test account.
