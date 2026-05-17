# Performance Guidelines

ContractForge standardizes ingestion patterns, but final performance depends on the write mode, source size, table layout and Spark runtime.

## Choose the Right Mode

| Scenario | Recommended mode | Note |
| --- | --- | --- |
| Append-only landing | `scd0_append` | Cheapest path; combine with idempotency when reprocessing batches. |
| Small full refresh | `scd0_overwrite` | Simple, but rewrites the whole target. |
| Current-state dimension by key | `scd1_upsert` | Requires `merge_keys`; protect against null keys. |
| Upsert with fewer unnecessary merges | `scd1_hash_diff` | Use deterministic `dedup_order_expr`. |
| Type 2 history | `scd2_historical` | More expensive; consider partitioning and change volume. |
| Complete snapshot with soft delete | `snapshot_soft_delete` | Requires a complete source, with no incremental watermark/filter. |

## Cache

- Use `use_cache=true` only when the same DataFrame is reused by expensive stages.
- Avoid caching large sources on clusters with limited memory.
- If you hit OOM, first disable cache and reduce read parallelism/partitions.

## JDBC

- Partition large reads by a stable numeric or temporal column.
- Avoid complex unindexed `query` values on the source database.
- Use incremental pushdown (`source.incremental.watermark_column` or `predicate`) to reduce volume.
- Tune `fetchsize` according to the database and driver.

## REST API

- Use `limits.max_pages`, `timeout_seconds`, `retry_attempts`, `retry_backoff_seconds` and `rate_limit_per_minute`.
- Do not use REST directly for massive loads or raw replay. Land raw files and process them with Auto Loader.
- Set `response.records_path` to avoid unnecessarily nested DataFrames.

## Delta Layout

- For new Databricks tables, prefer `cluster_columns` when Liquid Clustering fits the access pattern.
- Use `partition_column` only when cardinality and filter patterns justify it.
- `zorder_columns` only has an effect when `optimize_after_write=true` and the runtime supports the operation.

## Cost Observability

Monitor by table:

```sql
SELECT
  target_table,
  mode,
  AVG(duration_seconds) AS avg_duration_seconds,
  AVG(rows_written) AS avg_rows_written,
  AVG(rows_written / NULLIF(duration_seconds, 0)) AS avg_rows_per_second
FROM main.ops.ctrl_ingestion_runs
WHERE status = 'SUCCESS'
GROUP BY target_table, mode
ORDER BY avg_duration_seconds DESC;
```
