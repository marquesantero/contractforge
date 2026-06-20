# Semantic Contract Specification

## Purpose

The semantic contract is the normalized ingestion intent used by ContractForge Core after external contract files have been parsed and validated.

The semantic contract describes what must happen, not how a platform must execute it.

## Inputs

ContractForge Core keeps the split-contract vocabulary from ContractForge. These are ContractForge contracts, not Databricks contracts:

- ingestion/source contract
- annotations contract
- operations contract
- access contract
- shape and transform contract

These contracts are validated with platform-neutral Pydantic models in `contractforge_core.contracts`.

The complete contract-section rules are defined in [contract-sections.md](contract-sections.md).

Adapters must conform to these sections. A platform-specific adapter may translate a ContractForge concept to native features when semantics are equivalent, but it must not reshape the core contract to match one platform's API.

## Core Intents

Portable semantic objects are immutable and represent:

- source intent
- target intent
- write intent
- quality intent
- governance intent
- operations intent
- watermark intent and typed watermark values
- shape intent
- transform intent
- naming policy for derived artifacts

`source.type` is the concrete source family. `source.intent` may refine that family into adapter planning intent without replacing the raw source payload. For example, `source.type: s3` with `source.intent: file_stream` keeps the object-storage source explicit while telling adapters that newly discovered files and progress tracking are required.

The core also preserves optional source discovery and state intent:

- `source.discovery.strategy`: `file_listing`, `event_driven` or `queue_based`
- `source.discovery.tracking`: `modification_time`, `filename_pattern`, `external_state` or `external_queue`
- `source.state.storage`: `adapter_managed`, `external` or `job_local`
- `source.state.location`: neutral state location such as object storage, database table or key-value store

These are semantic planning hints, not runtime implementations. Adapters decide whether their native platform can preserve them.

`target.catalog_type` is optional target metadata for adapters that need to distinguish logical catalog mappings, such as `metastore`, `database` or `schema`. It does not name a vendor catalog product. Physical catalog binding belongs in environment configuration or adapter-owned parameters.

## Write Semantics

The initial write vocabulary follows ContractForge:

- `append`
- `overwrite`
- `upsert`
- `hash_diff_upsert`
- `historical`
- `snapshot_reconcile_soft_delete`
- `custom:<name>`

Adapters must never silently downgrade these modes. If an adapter cannot preserve the requested write semantics, planning must return `REVIEW_REQUIRED` or `UNSUPPORTED`.

`custom:<name>` is an explicit adapter-owned extension namespace. The core accepts it so contracts can be parsed and reviewed, but it is not portable semantic intent and requires adapter-declared support before planning can return `SUPPORTED`.

## Execution Intent

The ingestion contract may declare execution intent without naming a scheduler, stream runtime or platform primitive:

```yaml
execution:
  freshness: near_real_time
  latency_target: 5 minutes
  preferred: continuous
  fallback: batch_incremental
```

Portable fields:

- `freshness`: `batch`, `near_real_time` or `real_time`
- `latency_target`: readable SLA target preserved for planning and evidence
- `preferred`: `scheduled`, `event_driven`, `continuous` or `available_now`
- `fallback`: `scheduled`, `batch_incremental`, `review_required` or `fail`

`preferred: available_now` sets the semantic available-now marker used by capability matching. It does not require the core to know Spark Structured Streaming, Databricks Auto Loader, Glue Streaming, Snowpipe or Fabric Eventstream. If a platform can only approximate the preference, the adapter must return warnings or `REVIEW_REQUIRED` according to its capability declaration.

## Write Mode Portability

The core classifies write modes by semantic portability and platform requirements:

| Mode | Core semantic intent | Portable baseline | Platform requirements |
| --- | --- | --- | --- |
| `append` | Insert new rows without reconciling existing target rows. | Portable. | Append-capable storage or table API. |
| `overwrite` | Replace the target or declared target scope. | Portable with caution. | Atomic overwrite or adapter-declared replacement semantics. |
| `upsert` | Update current state by keys without history. | General semantic, not universally supported. | Merge/upsert capability and stable key semantics. |
| `hash_diff_upsert` | Current-state upsert with hash-based change detection. | General pattern, capability-gated. | Merge/upsert plus adapter-declared hash-diff support. |
| `historical` | Preserve historical versions with current-row markers and validity windows. | Review-prone across engines. | Merge/upsert plus explicit historical capability. |
| `snapshot_reconcile_soft_delete` | Reconcile full snapshots and mark missing target keys inactive/deleted. | Review-prone across engines. | Snapshot reconciliation capability or review marker. |
| `custom:<name>` | Adapter-owned write behavior. | Not portable. | Adapter-registered handler and explicit capability declaration. |

`historical` and `snapshot_reconcile_soft_delete` are intentionally not treated as universally portable. Similar platform features can differ in late-arriving event handling, delete semantics, validity interval closure, isolation guarantees, and generated metadata columns.

## Portable Validation

Portable validation checks contract shape, required fields, write mode names, schema policy names, quality declarations, governance declarations, and operational metadata.

Portable validation must not import Spark, Databricks SDKs, boto3, Azure SDKs, Fabric SDKs, or any platform runtime.

## Schema Diff Semantics

The core owns platform-neutral schema comparison:

- added columns
- removed columns, excluding ContractForge control columns
- type changes
- type widening classification
- validation against `strict`, `additive_only` and `permissive` schema policies

Adapters decide how to inspect physical schemas, apply allowed changes and persist schema-change evidence. For example, Databricks may render Delta `ALTER TABLE` statements, while another adapter may use Iceberg, Snowflake or Fabric-native schema APIs.

The core must not assume that all platforms support the same type-widening DDL. A core schema diff can be valid while an adapter still returns `REVIEW_REQUIRED` or `UNSUPPORTED` for applying it.

## Preparation Semantics

The core owns small staging specifications for ContractForge write algorithms:

- hash-diff staging metadata
- historical insert columns, merge keys, change columns and sequence column
- snapshot soft-delete source columns and soft-delete metadata columns

Hash-based write modes support two explicit strategies:

- `hash_strategy: explicit` (default): `hash_keys` lists the content columns that define a change. This is recommended for governed and high-value tables.
- `hash_strategy: all_columns_except`: all prepared source columns are candidates except `merge_keys`, user-declared `hash_exclude_columns`, and ContractForge/framework-generated columns such as `row_hash`, `source_loaded_at_utc`, SCD control columns, and `transform.derive` / `transform.composite_keys` outputs.

`hash_exclude_columns` remains a portable semantic field, not a Databricks option. Adapters must apply the exclusion when materializing hash-diff or historical change detection, or return a planning warning/blocker if they cannot preserve it.

Historical contracts may declare `scd2_effective_from_column` to use a source-provided timestamp as the new version's `valid_from` value. If omitted, adapters may use the execution timestamp. Adapters must validate that the column exists before execution and must not silently replace a declared effective-from column with runtime time.

Historical contracts may also declare `scd2_late_arriving_policy`:

- `apply`: process the row even if its `scd2_sequence_by` value is not newer than the current target version.
- `ignore`: skip late-arriving rows.
- `reject`: fail execution when late-arriving rows are detected.

`ignore` and `reject` require `scd2_sequence_by`. Adapters that cannot enforce the requested behavior must return a blocker or review-required result.

`scd2_apply_as_deletes` declares a boolean expression that classifies source rows as logical deletes for historical mode. A capable adapter should expire the current target version for matching keys, mark the change as a delete in its history metadata where supported, and prevent those delete rows from being inserted as new current versions.

Adapters decide how to materialize these staging specs. Databricks may use Spark SQL/DataFrames and Delta MERGE; other platforms may use temporary tables, native SQL, managed pipelines or review artifacts.

## Portable Connector Helpers

The core may define platform-neutral connector contracts and helper semantics for common protocols.

Examples:

- HTTP bounded file options: source type, URL, query parameters, headers, auth shape, retry intent and reader-neutral file options.
- JDBC batch options: URL, table/query exclusivity, read partitioning fields and auth shape.
- File, object-storage and catalog source options: source kind, provider, format normalization, reader options, table/path/query rules.
- Bounded event-stream replay options: Kafka and Event Hubs connection, topic/assignment, starting position and ending position for catch-up reads, not continuous streaming execution.
- Delta Sharing consumer options: profile reference, shared table name and reader-neutral options.
- Native passthrough and REST API descriptors: required source fields, request shape, pagination intent, watermark intent and secret-field redaction for review artifacts.
- RDS IAM token semantics: JDBC host/port parsing, region inference and SigV4 token generation.
- Connection references: `source.type: connection` with `connection_path` loads a reusable source YAML and merges dataset-specific fields before semantic normalization.
- Logical table references: catalog/table sources may use `source.ref: layer.table` or `source.table_ref: {layer, table}`; SQL sources may use `{{ table_ref:layer.table }}` placeholders. The core only validates/parses the portable reference. Adapters resolve it to native table names such as Unity Catalog, Glue Catalog/Iceberg, Snowflake databases or Fabric Lakehouse tables.

These helpers must not execute platform code. They cannot import Spark, Databricks SDK, boto3, Snowpark, Fabric SDK or cloud-specific runtime clients.

Adapters consume these helpers and translate them into native runtime artifacts.

Connection resolution is a contract-loading concern. Adapters must not be required to know where reusable connection files live; they receive the resolved source payload. `connection_path` may use `project://...` to resolve from the nearest `project.yaml` root, or a same-bundle relative path that stays under the ingestion bundle directory. Absolute paths and `..` traversal are rejected.

## Partitioning Semantics

The core owns partition predicate input validation, such as preserving distinct values in order and enforcing configured limits.

Adapters render platform-specific predicates. For example, Databricks renders SQL `IN` and `replaceWhere` expressions with Databricks quoting rules.

## Quality Semantics

The core carries quality intent for:

- required columns
- not-null checks
- unique keys
- accepted values
- minimum row count
- maximum null ratio
- named boolean expressions

Rules may carry severity such as `abort`, `warn` or `quarantine`. The contract-level `on_quality_fail` policy preserves the Databricks adapter baseline global behavior for failed quality checks: `fail`, `warn` or `quarantine`. The core preserves the intent, severity and global policy; adapters decide how to execute checks, isolate invalid rows, persist evidence and handle platform SQL dialect differences.

`quality_rules.custom` is accepted as an opaque extension payload. The core validates the basic custom rule shape and preserves evaluator-specific parameters under `extensions.quality.custom`, but it does not treat custom rules as portable quality semantics. Platform adapters may execute them through adapter-owned registries when they explicitly support that runtime extension.

## Shape And Transform Semantics

The core preserves ContractForge shape and transform intent as semantic data.

Portable transform concepts include:

- cast
- derive
- standardize
- deduplicate

Deduplication is declared only as `transform.deduplicate`. The core does not accept legacy top-level aliases for this behavior; adapters must consume the canonical transform intent and fail clearly when the required deterministic order is absent.

Composite key construction is declared as `transform.composite_keys`. It declares derived keys by concatenating source columns with ContractForge semantics. Adapters must materialize the key before write-mode key validation and before deduplication that depends on the derived key.

Shape concepts such as JSON parsing, array handling and flattening are also retained, but adapters decide whether they can execute them natively, through DataFrame preparation, through SQL, or require review.

Contracts may declare a top-level `schemas` registry for named structural schemas used by shape operations. When the registry is present, the core resolves `shape.parse_json[].schema_ref` into a concrete `schema` while preserving the reference name for review/evidence. If no registry is present, the reference is preserved for review artifacts and adapters must require a concrete schema before runtime execution. A parse-json declaration must use either `schema` or `schema_ref`, not both.

The core must not import Spark or implement DataFrame algorithms. Adapter renderers and runtimes translate these intents to platform-native preparation steps.

## Naming Policy

Naming policy is portable ContractForge metadata for derived artifacts.

It may control generated names such as:

- contract basename
- bundle name
- job name
- task key
- artifact prefix
- display/logical names

It must not rewrite physical target identifiers by default. Target catalog, schema and table remain the explicit ingestion target. Adapters may use naming policy for deployment artifacts while preserving the target namespace declared in the contract.

## Watermarks

Watermark intent is a ContractForge ingestion concept, not a Databricks concept.

The core owns the portable typed watermark value format:

- stable JSON
- one entry per watermark column
- each entry carries a logical type and serialized value
- simple and composite watermarks use the same payload shape

Adapters own how that value is applied. For example, Databricks can render a lexicographic SQL predicate and store the current value in Delta evidence/state tables, while another adapter may use a native bookmark, query predicate or workflow parameter.

The core must not import DataFrame APIs to compute or apply a watermark.

## Contract Metadata

Contract metadata that explains how the contract was produced is platform-neutral when it does not imply execution behavior. For example, `applied_presets` records the preset names expanded into the contract so adapters can include them in evidence and public run payloads. It must not change planning or execution by itself.

Operational source metadata such as `source.system` may be preserved as evidence metadata. Runtime artifact names such as Databricks notebook paths, Glue job names or Fabric item names are not ingestion semantics; adapters should populate them from runtime metadata or environment context. Evidence storage location is not an ingestion semantic: use the environment contract, for example `environment.evidence.catalog` and `environment.evidence.schema`, or adapter-owned runtime options. The core does not accept legacy root aliases such as `source_system`, `ctrl_schema` or `notebook_name` and does not add physical metadata columns by default.

## Platform Extensions

Platform-specific fields may exist in contract extension maps, but the core must classify them before planning:

- portable
- platform-specific
- supported with warnings
- review required
- unsupported

Platform extensions are additive. They do not replace the portable ingestion, annotations, operations or access contract sections.
