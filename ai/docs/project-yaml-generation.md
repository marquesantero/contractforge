# Project YAML Generation

`project.yaml` is the portable project control plane. It should describe the DAG and deployment targets without duplicating ingestion semantics.

## Generated Shape

```yaml
name: supabase_medallion

environments:
  databricks: environments/databricks.environment.yaml
  aws: environments/aws.environment.yaml

connections:
  supabase_postgres: connections/supabase.yaml

schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false

execution_order:
  - name: bronze_products
    layer: bronze
    contracts:
      databricks: contracts/bronze/products/products.ingestion.yaml
      aws: contracts/bronze/products/products.ingestion.yaml

  - name: silver_products
    layer: silver
    depends_on: [bronze_products]
    contracts:
      databricks: contracts/silver/products/products.ingestion.yaml
      aws: contracts/silver/products/products.ingestion.yaml
```

## Rules

- `execution_order[].depends_on` is portable.
- `schedule.cron` and `schedule.timezone` are core-owned project semantics.
- Adapter-specific schedule flags belong under `schedule.adapters.<adapter>`.
- Adapter deployment fields belong under `deployment.<adapter>` or the environment file.
- Use the same contract path for multiple adapters when the contract intent is identical.

## AI Acceptance

AI generation is acceptable when:

- missing schedule timezone becomes a `RequiredDecision`;
- cron values are preserved as user input, not guessed;
- adapter-specific deployment data does not leak into ingestion contracts;
- generated Databricks and AWS projects differ mostly by environment/deployment fields.
