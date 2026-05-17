# ADR-003: `snapshot_soft_delete` with SQL MERGE

**Status:** Accepted
**Date:** 2026-05-13

## Context

`snapshot_soft_delete` has different semantics from incremental loading. The source represents the full final state of the entity at execution time. Any active row that exists in the target but is absent from the source must be marked inactive (`is_active=false`, `deleted_at=now()`).

If the source is partial, for example because of `watermark_columns`, `filter_expression` or incremental Auto Loader, the framework cannot distinguish "record removed from the source" from "record outside the loaded slice". That would create false soft deletes.

There was also runtime divergence when the implementation depended on DeltaTable Python APIs. Databricks Serverless/Spark Connect and classic clusters have different API limits.

## Decision

The `snapshot_soft_delete` mode:

- requires the source to represent the complete current state;
- rejects `watermark_columns`, `filter_expression` and declarative `SourceSpec`;
- uses SQL `MERGE` in all runtimes, including classic and serverless;
- uses `WHEN NOT MATCHED BY SOURCE` to mark missing active rows as inactive;
- reactivates rows that reappear in the snapshot;
- calculates `row_hash` to update only changed records.

## Consequences

- Mode semantics stay predictable: complete snapshot in, consistent final state out.
- A single SQL path reduces divergence across classic, serverless and Spark Connect.
- The API fails early for conceptually invalid combinations.
- Cost may be higher than an incremental path because the source must represent the complete set.
- Incremental loads should use `scd1_upsert`, `scd1_hash_diff` or another appropriate mode.
