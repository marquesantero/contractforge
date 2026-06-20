# Portability Boundaries Specification

## Purpose

ContractForge Core must be explicit about portability. The project must not imply that every contract runs everywhere.

Portability is evaluated from ContractForge semantics outward. A concept that originated in the Databricks adapter implementation can still be a ContractForge concept when it describes durable ingestion, annotation, operations or access intent. The adapter then maps that intent to Databricks, AWS, GCP, Snowflake, Fabric or another platform when equivalent.

## Portable Candidates

- source intent
- target intent
- layer
- append
- overwrite
- basic merge or upsert intent
- current-state current-state upsert intent when merge exists
- schema policies: `strict`, `additive_only`, `permissive`
- quality rules such as not-null, accepted values, and minimum row count
- ownership metadata
- basic lineage and evidence intent
- naming policy
- annotations metadata: descriptions, tags, aliases, PII and lifecycle markers
- operations metadata: ownership, support, criticality, freshness SLA and runbook
- access policy shell: principals, privileges, validation mode and drift policy

## Platform-Specific Candidates

- Delta table properties
- Liquid clustering
- Unity Catalog row filters and masks
- Databricks Jobs
- Auto Loader
- Lakeflow AUTO CDC
- Glue Catalog details
- Iceberg table properties
- Lake Formation grants
- Fabric Dataflow Gen2
- Purview integration
- adapter-specific source implementations such as Auto Loader/cloudFiles, Glue bookmarks, Dataflow Gen2, Snowpipe or Fabric shortcuts

## Review-Required Candidates

- historical equivalence across engines
- snapshot soft delete semantics
- available-now streaming semantics
- row filters and masks portability
- access-control inheritance and principal model differences
- catalog tag/classification equivalence
- operations alerting and monitoring integration
- schema evolution with type widening
- quarantine behavior across platforms

## Unsupported Behavior

Unsupported semantics must be reported as blockers. The planner must not rewrite the contract into a weaker behavior.
