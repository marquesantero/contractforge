# Project Template

This is a recommended layout for a team using ContractForge Core with one or more adapters.

```text
data-platform/
  pyproject.toml
  contracts/
    environments/
      dev.databricks.yaml
      prod.databricks.yaml
      prod.snowflake.yaml
    bronze/
      orders.ingestion.yaml
      orders.annotations.yaml
      orders.operations.yaml
      orders.access.yaml
    silver/
      orders_current.ingestion.yaml
      orders_current.annotations.yaml
      orders_current.operations.yaml
      orders_current.access.yaml
  adapters/
    databricks/
      bundles/
      notebooks/
      jobs/
    snowflake/
      sql/
      tasks/
  tests/
    test_contracts_validate.py
    test_platform_planning.py
  docs/
    platform-decisions.md
```

## Contract Ownership

- Data engineering owns ingestion semantics.
- Governance owns annotations and access intent.
- Operations owns SLA, support and runbook metadata.
- Platform teams own environment files and adapter parameters.

## Environment Files

Keep environments separate from table contracts:

```yaml
environment:
  name: prod
  adapter: databricks
  evidence:
    catalog: main
    schema: ops
  runtime:
    kind: serverless
  parameters:
    databricks:
      workspace_path: /Shared/contractforge
```

Do not put source, target, mode, quality or access semantics in the environment file.

## CI Checks

Recommended checks:

- validate all contract files;
- compose split contract bundles;
- plan representative contracts against each target adapter capability profile;
- fail on `UNSUPPORTED`;
- require manual approval for `REVIEW_REQUIRED`;
- render artifacts and store them as build outputs;
- run adapter-specific tests in platform integration pipelines.
