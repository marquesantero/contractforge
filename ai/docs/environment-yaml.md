# Environment YAML

`environment.yaml` binds a ContractForge project to a platform runtime. It is the right place for evidence destinations, artifact paths, runtime defaults and guarded adapter parameters.

## Platform-Neutral Fields

```yaml
name: dev
adapter: aws

artifacts:
  uri: s3://contractforge-artifacts/dev/supabase/

evidence:
  database: contractforge_ops

defaults:
  target_catalog: contractforge
  target_schema: bronze
```

For Databricks:

```yaml
name: dev
adapter: databricks

evidence:
  catalog: workspace
  schema: contractforge_ops

defaults:
  target_catalog: workspace
  target_schema: bronze
```

## Adapter Parameters

Adapter-specific settings must be guarded:

```yaml
parameters:
  aws:
    glue_job:
      role_arn: arn:aws:iam::123456789012:role/ContractForgeGlueRole
      worker_type: G.1X
      number_of_workers: 2
    iceberg:
      warehouse: s3://contractforge-warehouse/dev/
```

```yaml
parameters:
  databricks:
    bundle:
      workspace_root_path: /Workspace/Shared/contractforge
    runtime:
      type: serverless
```

## Rules

- The core can understand the environment shape.
- The core must not import platform SDKs or execute runtime code.
- Adapters own interpretation of `parameters.<adapter>`.
- Ingestion contracts should not contain evidence storage, artifact storage or deploy credentials.
