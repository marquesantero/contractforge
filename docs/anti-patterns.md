# Anti-Patterns

Avoid these patterns when using or extending ContractForge Core.

## Platform Logic In Core

Do not add Databricks, AWS, Fabric, GCP or Snowflake branches to the core planner.

Use capabilities and adapter logic instead.

## Silent Downgrades

Never convert:

- historical mode to append;
- merge to append;
- snapshot soft delete to overwrite;
- row filters to documentation-only metadata;
- column masks to tags only.

Return `REVIEW_REQUIRED` or `UNSUPPORTED`.

## Environment As A Second Contract

Do not place ingestion behavior in `environment`.

Bad:

```yaml
environment:
  mode: upsert
  target_table: orders
```

Good:

```yaml
environment:
  adapter: databricks
  evidence:
    catalog: main
    schema: ops
```

## Adapter God Files

Do not put all adapter behavior into one large module.

Split by durable domain:

- capabilities;
- sources;
- execution;
- quality;
- governance;
- evidence;
- runtime;
- rendering;
- CLI.

## Databricks Names In Portable Contracts

Prefer portable source types:

- `incremental_files` instead of `autoloader`;
- `native_passthrough` instead of `lakeflow_connect_*`;
- semantic write modes instead of Delta implementation names.

Adapter-specific names may exist in conversion tools or explicit non-portable extensions, but they should not become portable core vocabulary.
