# Evidence Model Specification

## Purpose

The evidence model is the platform-neutral audit vocabulary for ingestion delivery.

The core does not call evidence storage "Delta control tables" or "Iceberg control tables". Those are adapter persistence choices.

The canonical control-table columns and their portability status are in [control-table-parity.md](control-table-parity.md); the column-by-column mapping to each platform's native evidence source (Databricks, AWS, GCP, Snowflake, Fabric) is in the [Evidence mapping matrix](evidence-mapping-matrix.md).

## Evidence Concepts

Core evidence concepts include:

- run
- error
- quality result
- quarantined record reference
- schema change
- lineage event
- source metadata
- stream batch evidence
- access or governance application evidence
- cost signal

## Portable Result Models

The core defines portable result objects for quality outcomes and execution outcomes:

- quality rule result: rule name, status, severity, failed count, message and details
- aggregate quality status: `PASSED`, `FAILED`, `WARNED` or `NOT_CONFIGURED`
- execution outcome: status, operation, target, metrics and optional platform statement/message
- logical write metrics: rows inserted, updated, deleted, expired and affected, normalized from the requested write semantics
- evidence records: run, error, quality, quarantine, schema change, lineage, source metadata, stream batch, access and cost records
- runtime handoff metrics: prepared rows read/quarantined, quarantine references and fallback rows-written derivation
- diagnostic records: explain-plan or platform review records with run, target, source, mode, format and redacted plan text
- source metadata extraction: source type, connector, provider, format, path/object, request/read/auth/pagination/response/incremental/limits and source capability flags
- reporting artifacts: dashboard query metadata with name, title, visualization hint and platform-rendered query text

Adapters may enrich these results with platform metrics, but they must preserve the core status vocabulary so evidence can be compared across platforms.

Platform-specific metric extraction remains adapter-owned. For example, Databricks may parse Delta `operationMetrics`, Snowflake may parse query history, and Fabric may use pipeline or Lakehouse execution telemetry.

## Redaction

The core owns platform-neutral redaction helpers for evidence and rendered review artifacts.

Adapters must redact sensitive keys and common secret patterns before persisting evidence, emitting diagnostics or rendering review artifacts. Platform adapters may add stricter patterns, but they must not weaken the core redaction behavior.

## Error Normalization

The core owns a small operational error normalization helper:

- redact sensitive text
- prefer the most relevant line from multi-line exceptions
- truncate messages for evidence persistence

Adapters may pass platform-specific preferred tokens, but evidence should preserve a comparable redacted error-message shape across platforms.

## Adapter Persistence

Adapters decide how evidence is persisted:

- Databricks: Delta control tables
- AWS: Iceberg/Glue tables or S3 audit artifacts
- Fabric: Lakehouse tables
- Snowflake: audit tables
- future adapters: platform-appropriate persistence

Detailed control-table and column-level portability is defined in [control-table-parity.md](control-table-parity.md).

## Production Requirement

Production plans require adapter-declared evidence storage. A platform that cannot record evidence must return `UNSUPPORTED` for production execution plans.
