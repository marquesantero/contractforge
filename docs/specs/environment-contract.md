# Environment Contract Specification

## Purpose

The environment contract describes where and how an adapter is allowed to execute, render, publish evidence and resolve infrastructure.

It is not a semantic ingestion contract. Changing `environment.yaml` must not change what data is ingested, which write mode is requested, which annotations exist, which operations metadata is declared or which access policy is intended.

## File Name

Recommended file name:

```text
environment.yaml
```

## Shape

```yaml
environment:
  name: prod
  adapter: databricks

  runtime:
    kind: serverless
    warehouse_id: ${DATABRICKS_WAREHOUSE_ID}

  deployment:
    artifact: databricks_asset_bundle
    workspace_path: /Workspace/ContractForge

  artifacts:
    uri: s3://contractforge-artifacts/prod/orders/
    include_contract_bundle: true
    include_normalized_contract: true

  evidence:
    catalog: main
    schema: contractforge_ops

  secrets:
    strategy: secret_scope
    scope: prod-secrets

  defaults:
    timezone: UTC
    fail_fast: true

  capabilities:
    require:
      - merge
      - evidence_store

  parameters:
    databricks:
      cloudFiles.inferColumnTypes: true
      job.max_concurrent_runs: 1
```

## Fields

| Field | Owner | Purpose |
| --- | --- | --- |
| `name` | Core | Logical environment name, such as `dev`, `qa`, `prod` or `client-a-prod`. |
| `adapter` | Core | Adapter selector, such as `databricks`, `aws`, `gcp`, `snowflake` or `fabric`. |
| `runtime` | Adapter | Compute/runtime context. |
| `deployment` | Adapter | Artifact and deployment context. |
| `artifacts` | Adapter | Artifact publication location and retention options. AWS uses this for rendered Glue scripts, manifests and original/normalized contract artifacts in S3. |
| `evidence` | Adapter | Evidence store location and persistence context. |
| `secrets` | Adapter | Secret resolution strategy. |
| `defaults` | Adapter | Environment-level execution defaults. |
| `capabilities` | Core + adapter | Required, preferred or forbidden capability names. |
| `parameters.<adapter>` | Adapter | Native adapter parameters. |

## Fabric Secret Bindings

Fabric authenticated HTTP/REST notebook drafts resolve
`{{ secret:scope/key }}` placeholders through Azure Key Vault at runtime. The
contract keeps only the placeholder; the environment binds the placeholder
scope to a vault URL:

```yaml
environment:
  adapter: fabric
  secrets:
    vault_url: https://contractforge-default.vault.azure.net/
    scopes:
      fabric: https://contractforge-fabric.vault.azure.net/
```

Generated notebooks call `notebookutils.credentials.getSecret(vault_url, key)`.
The Fabric runtime identity must be allowed to read the declared Key Vault
secret. Inline bearer tokens, API keys and passwords remain outside the stable
contract boundary.

## Defaults

`environment.name` defaults to `dev` when omitted. The adapter selector remains
required because it chooses the platform boundary.

Adapter runtime knobs should default in the adapter when the default is stable
and documented. For the broader default policy, see
[Parameter defaults](parameter-defaults.md).

## Forbidden Fields

The environment contract must not contain semantic contract fields:

- `source`
- `target`
- `target_table`
- `mode`
- `merge_keys`
- `schema_policy`
- `quality_rules`
- `annotations`
- `operations`
- `access`
- `transform`

If a field changes the ingestion intent, it belongs in the ingestion, annotations, operations or access contract instead.

## Core Boundary

The core validates the generic environment shape and rejects semantic fields.

The core does not interpret platform-specific keys inside:

- `runtime`
- `deployment`
- `artifacts`
- `evidence`
- `secrets`
- `defaults`
- `parameters`

Adapters own those meanings.

## Adapter Binding Rule

An adapter may use environment values to choose runtime, deployment, evidence location and native defaults.

An adapter must not use environment values to override semantic contract fields such as source, target, write mode, annotations, operations or access.

## AWS Artifact Publication

AWS Glue jobs cannot read local YAML files from a developer workstation. The AWS
adapter therefore renders runtime artifacts locally or in CI, publishes them to
the `artifacts.uri` S3 prefix, materializes the Glue job definition with the
published script URI and registers the native Glue job.

This is an environment concern because it describes where adapter artifacts are
stored, not what the ingestion does.
