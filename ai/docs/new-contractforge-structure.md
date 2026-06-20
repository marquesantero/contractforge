# New ContractForge Structure

ContractForge AI targets the current ContractForge architecture: a platform-neutral core, platform adapters and optional AI assistance. The product is ContractForge; package names describe functional boundaries.

## Canonical Files

A complete project may include:

| File | Purpose |
| --- | --- |
| `project.yaml` | Project inventory, execution order, dependencies, schedule and adapter deployment targets. |
| `environment.yaml` | Runtime binding, evidence location, artifact destination and guarded adapter parameters. |
| `connections/*.yaml` | Shared connector defaults such as endpoint, auth reference, driver and common read settings. |
| `*.ingestion.yaml` | Source, target, write mode, schema policy, transform, quality and dataset-specific source overrides. |
| `*.annotations.yaml` | Table and column documentation, tags and metadata. |
| `*.operations.yaml` | Ownership, SLA, criticality, runbook and alert metadata. |
| `*.access.yaml` | Access intent such as grants, row filters and masks. |

## Rejected Legacy Shapes

ContractForge AI should reject or flag legacy flat fields:

- `target_table`
- `target_schema`
- `catalog` as a top-level target alias
- `ctrl_schema` inside ingestion contracts
- `source_system` as a top-level ingestion field
- adapter fields such as `delta_properties` outside `extensions.databricks`

Canonical target shape:

```yaml
target:
  catalog: analytics
  schema: bronze
  table: b_orders
```

Canonical source system shape:

```yaml
source:
  type: postgres
  system: supabase_inventory
```

Canonical adapter extension shape:

```yaml
extensions:
  databricks:
    delta_properties:
      delta.enableChangeDataFeed: "true"
```

## Deterministic Rule

AI must run deterministic parsing, validation and adapter planning before provider-backed enrichment. Provider output may explain, suggest or fill review placeholders, but it must not override deterministic support status or silently change identity fields such as connector, source path, target, layer, write mode or adapter.
