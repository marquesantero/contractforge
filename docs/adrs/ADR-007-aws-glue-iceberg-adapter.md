# ADR-007: AWS Glue Iceberg Adapter Strategy

## Status

Accepted

## Context

ContractForge needs a second platform adapter to validate that the core is genuinely platform-neutral. AWS has multiple possible ingestion paths:

- AWS Glue Spark;
- AWS Glue Data Catalog;
- Apache Iceberg tables on S3;
- Lake Formation;
- Athena;
- EMR Serverless;
- AppFlow;
- DMS;
- vendor and marketplace connectors.

A generic "AWS adapter" would hide too many runtime differences and would likely overpromise portability. The adapter needs a clear first target.

## Decision

The first AWS adapter target is `aws_glue_iceberg`.

It uses:

- AWS Glue Spark as the primary runtime;
- Apache Iceberg on S3 as the primary table format;
- AWS Glue Data Catalog as the table catalog;
- AWS Lake Formation as the governance target;
- Iceberg tables as the default evidence store.

Other AWS paths are modeled as future subtargets:

- `aws_athena_iceberg`;
- `aws_emr_serverless_iceberg`;
- `aws_native_passthrough`.

The implementation declares capabilities, returns core `PlanningResult` objects, renders review artifacts, renders Iceberg DDL for canonical evidence/control tables, and generates Glue Spark/Iceberg scripts for append, overwrite, upsert and hash-diff paths.

The base package remains importable without AWS SDK dependencies. Optional runtime helpers may publish artifacts to S3, create or update Glue jobs, start/wait Glue job runs and map Glue run metadata into evidence records. Those helpers must import AWS SDKs lazily or accept caller-provided clients.

## Consequences

### Positive

- The core can be validated against a non-Databricks adapter without introducing AWS SDK dependencies.
- The adapter can return honest `SUPPORTED`, `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` and `UNSUPPORTED` results.
- AWS implementation details such as Glue bookmarks stay outside the core.
- Evidence/control table schemas remain core-owned; AWS only renders them as Iceberg tables.
- The adapter can evolve by subtarget instead of becoming a god object.

### Negative

- AWS execution is adapter-owned and optional; deployment helpers exist, but the core remains execution-free and SDK-free.
- historical, snapshot soft delete and Lake Formation access mappings are initially review-required.
- The current core capability model is less expressive than AWS eventually needs.

## Initial Capability Policy

The `aws_glue_iceberg` target declares append, overwrite, merge, hash diff, schema evolution, transforms, shape and expression quality as supported.

Append, overwrite, current-state upsert and hash-diff upsert have generated Glue Spark runtime scripts. Hash diff remains `SUPPORTED_WITH_WARNINGS` until performance and concurrency behavior are validated more broadly.

It marks these semantics as review-required:

- `historical`;
- `snapshot_reconcile_soft_delete`;
- `row_filters`;
- `column_masks`;
- some available-now streaming combinations, when checkpoint/write semantics cannot be preserved.

Databricks-specific source types such as `autoloader` are unsupported. Contracts should use portable `incremental_files` when the intent is checkpointed new-file discovery.

## Alternatives Considered

### Generic AWS Adapter

Rejected. AWS has too many materially different execution paths. A single generic adapter would either overpromise or hide meaningful runtime decisions.

### Athena First

Rejected as the first target. Athena is valuable for SQL and Iceberg access, but it is not a complete ingestion executor for ContractForge semantics.

### EMR Serverless First

Deferred. EMR Serverless offers more control than Glue but increases the setup surface for the first AWS proof.

### Native Passthrough First

Rejected as the foundation. AppFlow and DMS are important, but they validate native connector delegation rather than the core ingestion semantics.

## Follow-up Work

- Keep AWS adapter package skeleton and domain split aligned with the Databricks adapter style.
- Keep tests for core planning with AWS capabilities, rendering and runtime helper boundaries.
- Maintain review rendering and Glue Spark script rendering for append, overwrite, upsert and hash diff.
- Keep Iceberg evidence/state DDL rendered from the core evidence model.
- Preserve the one-command deployment path through `contractforge-aws deploy`.
- Validate Iceberg merge and hash-diff performance before promoting hash-diff upsert beyond warning.
- Validate historical, snapshot soft delete and Lake Formation data-filter equivalence before promoting those semantics beyond review.
- Design richer capability metadata only after the AWS skeleton proves the need.
