# Quick Start

This guide validates the smallest useful ContractForge flow: create a contract,
plan it against platform capabilities, then render or deploy through a native
adapter.

## 1. Install

Core only:

```bash
pip install contractforge-core
```

Core plus Databricks adapter:

```bash
pip install contractforge-core contractforge-databricks
```

Core plus any stable adapter:

```bash
pip install contractforge-core contractforge-aws
pip install contractforge-core contractforge-snowflake
pip install contractforge-core contractforge-fabric
pip install contractforge-core contractforge-gcp
```

Install from PyPI where the runtime supports it. Databricks and Fabric commonly
install packages directly in the job/notebook environment; AWS Glue should
normally receive S3-hosted wheels; hosted Snowflake procedures use staged ZIP
imports; GCP BigQuery and Workflows execute native artifacts while the adapter
runs in CLI/CI helper environments.

Local repository checkout:

```bash
uv run pytest
```

## 2. Create A Portable Ingestion Contract

```yaml
source:
  type: incremental_files
  path: s3://landing/orders/
  format: json
  read:
    source_complete: false

target:
  catalog: main
  schema: bronze
  table: orders

layer: bronze
mode: append
schema_policy: additive_only

quality_rules:
  not_null: [order_id]
```

The contract describes intent. It does not say "use Databricks Auto Loader". `incremental_files` is portable intent; the Databricks adapter may render Auto Loader `cloudFiles`, while another adapter may render Glue bookmarks, a Fabric pipeline pattern or a review-required plan.

## 3. Validate And Plan With Core

```python
from contractforge_core.contracts import semantic_contract_from_mapping, validate_contract
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import plan_contract

raw_contract = {
    "source": {
        "type": "incremental_files",
        "path": "s3://landing/orders/",
        "format": "json",
    },
    "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
    "layer": "bronze",
    "mode": "append",
    "schema_policy": "additive_only",
    "quality_rules": {"not_null": ["order_id"]},
}

validated = validate_contract(raw_contract)
semantic = semantic_contract_from_mapping(validated)

capabilities = PlatformCapabilities(
    platform="example",
    supports_append=True,
    supports_overwrite=True,
    supports_merge=False,
    supports_schema_evolution=True,
    evidence_stores=("audit_tables",),
)

planning = plan_contract(semantic, capabilities)
print(planning.status)
```

Expected status: `SUPPORTED`.

## 4. Render Databricks Artifacts

```python
from contractforge_databricks import render_databricks_contract

artifacts = render_databricks_contract(
    raw_contract,
    runtime_type="serverless",
    spark_conf={"spark.databricks.serverless.enabled": "true"},
)

for name, content in artifacts.artifacts.items():
    print(name, len(content))
```

The Databricks adapter owns the Databricks rendering. Core validation and planning remain platform-neutral.

## 5. Deploy AWS Glue Artifacts

For AWS, the contract still describes ingestion intent. The environment selects
S3 artifact publication, Glue job settings and the Iceberg warehouse:

```yaml
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/prod/orders/
  include_contract_bundle: true
  include_normalized_contract: true
parameters:
  aws:
    iceberg:
      warehouse: s3://contractforge-warehouse/prod/
    glue_job:
      role_arn: arn:aws:iam::123456789012:role/ContractForgeGlueRole
```

`environment.name` defaults to `dev`. Glue version, worker type, worker count,
timeout, retries and bookmark behavior also use documented AWS adapter defaults
unless overridden.

```bash
contractforge-aws deploy contracts/bronze/orders.ingestion.yaml --environment environment.yaml
```

This renders artifacts, publishes them to S3 and creates or updates the Glue
job. The generated Glue job creates ContractForge evidence/control tables when
they do not exist.

## 6. Use Split Contracts

Production projects normally split table responsibilities:

```text
contracts/bronze/orders.ingestion.yaml
contracts/bronze/orders.annotations.yaml
contracts/bronze/orders.operations.yaml
contracts/bronze/orders.access.yaml
contracts/environments/prod.databricks.yaml
```

The `ingestion` contract owns the canonical target. Companion contracts normally omit target and inherit the ingestion target during bundle composition.

## 7. Use Logical Table References

For medallion projects, downstream contracts can reference tables produced by
earlier contracts without platform-specific qualifiers:

```yaml
source:
  type: table
  ref: bronze.b_products_jdbc
```

Inline SQL can use the same reference form:

```sql
FROM {{ table_ref:silver.s_product_tags }}
```

Databricks resolves the reference to Unity Catalog-style names. AWS resolves it
to Glue Catalog/Iceberg names. Snowflake, Fabric and GCP resolve the same
logical reference to their own native table naming models. The core only
validates the neutral reference.

## 8. Next Steps

- Read [Contracts](contracts.md) for each contract section.
- Read [Adapters](adapters.md) before creating a new platform adapter.
- Read [Databricks adapter](databricks.md) when targeting Databricks.
- Read [AWS adapter](adapters/aws.md) when targeting AWS Glue/Iceberg.
- Review the [USGS GeoJSON medallion example](../examples/real-world/usgs-earthquake-rest-medallion/README.md) for the current multi-adapter parity project.
- Read [Operations and evidence](operations.md) before running production workloads.
