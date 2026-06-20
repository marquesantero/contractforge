# ADR-002: Databricks Reference Adapter

## Status

Accepted

## Context

The Databricks adapter baseline is Databricks adapter and contains mature ideas around Delta writes, Unity Catalog governance, jobs, Auto Loader, Lakeflow, and control tables.

## Decision

Databricks will be the first reference adapter for ContractForge Core, but Databricks runtime logic will not be placed in the core package.

The adapter consumes public core models and renders Databricks-native artifacts. The core owns ContractForge semantics; the adapter owns Databricks interpretation, rendering, optional execution helpers and runtime evidence collection.

Core-owned surfaces consumed by the adapter:

- semantic contracts for ingestion, annotations, operations, access and environment
- platform capabilities, capability matching and planning results
- abstract execution plans and write strategy records
- portable source metadata, connector intent and source portability classification
- schema policy intent, schema diffs and preparation specs
- quality result, execution outcome, evidence record and runtime handoff models
- redaction, error normalization, lineage, diagnostics and reporting model shapes

Databricks-owned surfaces:

- Delta-oriented SQL
- Python job code
- Databricks Asset Bundles
- Databricks Jobs task definitions and workspace paths
- Unity Catalog comments, tags, grants, row filters and column masks
- Delta evidence/control table definitions and migrations
- Delta MERGE, SCD, hash-diff, snapshot, append and overwrite execution helpers
- Auto Loader/cloudFiles rendering for portable `incremental_files`
- Lakeflow AUTO CDC and Lakeflow Connect compatibility artifacts
- Delta Sharing, JDBC, HTTP/file/object source rendering on Databricks
- Databricks SQL quality checks, quarantine references and evidence inserts
- Delta table maintenance such as table properties, `OPTIMIZE`, `VACUUM` and statistics
- Databricks runtime capability detection and optional PySpark preparation helpers
- Databricks system-table, Delta history and DBU/cost evidence extraction
- Databricks SQL/Lakeview dashboard artifacts

The adapter may preserve mature ContractForge algorithms when Databricks has no better native equivalent. It should prefer native Databricks behavior when that preserves the ContractForge intent with higher compatibility, performance or operational evidence.

The adapter must not ask the core to know Databricks names such as `cloudFiles`, Unity Catalog DDL, Delta table properties, Jobs API payloads, Lakeflow pipeline syntax or Asset Bundle YAML.

The core must not import `contractforge_databricks`, Spark, Databricks SDK, Databricks Connect or Databricks CLI code.

## Execution Boundary

Rendering is adapter-owned and safe to run in a local Python process without PySpark.

Execution is optional and adapter-owned. Runtime helpers may accept injected SQL/Spark runners, but imports of PySpark or Databricks runtime objects must stay lazy and isolated. The core planning path remains pure Python.

## Parity Rule

The Databricks adapter should target behavior and evidence parity with the Databricks adapter implementation:

- no supported ContractForge write mode may silently degrade to another mode
- no Databricks capability may disappear without a tracked parity status
- platform-specific behavior must be represented as adapter behavior, review artifacts, warnings or blockers
- control/evidence tables remain a first-class adapter implementation of the core evidence model

## Consequences

The Databricks adapter can reuse mature ContractForge behavior, but only behind the adapter boundary.

The core remains useful for AWS, Fabric, Snowflake, and future platforms.
