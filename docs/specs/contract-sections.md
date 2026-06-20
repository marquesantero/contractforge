# Contract Sections Specification

## Purpose

ContractForge Core owns the full contract vocabulary for governed ingestion.

The contract is not a Databricks contract with portable subsets. It is a ContractForge contract made of stable sections that adapters translate to each platform when semantics are equivalent.

Required contract sections:

- ingestion
- annotations
- operations
- access
- environment

Optional semantic sections:

- quality rules
- shape
- transform
- naming
- adapter parameters through `environment.parameters`

The environment contract is not semantic. It selects execution/deployment context and must not repeat ingestion, annotations, operations or access fields.

## Bundle Composition

The core provides a pure composition helper for responsibility-separated contracts:

- `ingestion` is required.
- `annotations`, `operations` and `access` are optional semantic sections.
- `environment` is optional and validated separately.
- sibling semantic sections may declare `target` for reviewability.
- sibling section targets must not conflict with the ingestion target.

Composition produces a semantic contract plus the validated environment mapping. It does not read YAML files, call platform SDKs or render platform artifacts.

File discovery, CLI behavior and deployment repository layout are adapter/tooling concerns. This prevents the semantic core from inheriting Databricks project structure assumptions from the Databricks adapter baseline.

## Ingestion Contract

The ingestion contract declares source, target, write semantics, schema policy, quality rules and optional shape/transform intent.

The optional naming block defines derived artifact names. It does not replace `target.catalog`, `target.schema` or `target.table`.

Portable ingestion concepts include:

- source type and source metadata
- target namespace and table
- layer
- write mode
- merge keys and history keys
- schema policy
- quality rules
- bounded/incremental source intent
- lineage and evidence requirements

Adapters map these concepts to native runtime features:

| ContractForge intent | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- |
| append | Delta append | Iceberg/Hudi/Parquet append | BigQuery/Dataproc append | table insert/copy | Lakehouse append |
| overwrite | Delta overwrite | table/file replacement | BigQuery overwrite | table replacement | Lakehouse overwrite |
| current-state upsert | Delta MERGE | Iceberg/Hudi MERGE or Glue job | BigQuery MERGE | MERGE | reviewed pipeline/MERGE |
| Historical | Delta MERGE pattern or Lakeflow AUTO CDC | reviewed Iceberg/Hudi pattern | reviewed BigQuery pattern | reviewed MERGE/stream pattern | reviewed pipeline pattern |
| incremental files | Auto Loader/cloudFiles | Glue bookmarks or managed file tracking | Storage notifications/Dataflow/Dataproc | stage/copy tracking | OneLake/Dataflow pattern |

If the native platform behavior is not equivalent, the adapter must return `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or `UNSUPPORTED`.

## Annotations Contract

Annotations describe catalog metadata. They are ContractForge concepts even when the first implementation uses Unity Catalog.

Portable annotation concepts include:

- table description
- column description
- table tags
- column tags
- aliases
- PII marker
- sensitivity
- deprecated marker
- replacement and removal metadata

Adapter examples:

| ContractForge annotation | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- |
| table description | table comment | Glue table description | Dataplex/BigQuery description | COMMENT | item/table description |
| column description | column comment | Glue column comment | BigQuery column description | COMMENT | semantic/model metadata |
| tags | Unity Catalog tags | Glue/Lake Formation tags | Data Catalog tags/policy tags | tags/classification | Purview/Fabric metadata |
| PII/sensitivity | UC tags/masks review | Lake Formation/Purview tags | policy tags | tags/masking policy review | Purview sensitivity |

Adapters must not force the contract to use platform field names such as Unity Catalog tags, Lake Formation tags or BigQuery policy tags.

## Operations Contract

Operations describe ownership, reliability and support metadata.

Portable operations concepts include:

- business owner
- technical owner
- steward
- support group
- escalation group
- criticality
- expected frequency
- freshness SLA
- alerting intent
- runbook URL
- operational tags

Adapters persist or render these concepts into the platform evidence store, catalog metadata, monitoring configuration or review artifacts.

The core does not send alerts and does not schedule jobs. It preserves the operational intent so platform adapters and delivery pipelines can wire native monitoring.

## Access Contract

Access describes security intent.

Portable access concepts include:

- principal
- privileges
- access mode: `apply`, `validate_only`, `ignore`
- drift policy: `warn`, `fail`
- revoke-unmanaged intent

Review-prone access concepts include:

- row filters
- column masks
- policy functions
- platform-native grants with different inheritance semantics

Adapters translate the access contract to native controls when equivalent. If semantics differ, the adapter must require review.

Examples:

| ContractForge access intent | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- |
| table grants | Unity Catalog grants | Lake Formation grants | IAM/BigQuery grants | GRANT | workspace/lakehouse permissions |
| row filters | UC row filters | Lake Formation row filters | row access policies | row access policies | reviewed/security artifact |
| column masks | UC masks | LF tags/policies | policy tags/masking | masking policies | Purview/security review |

## Platform Extensions

Adapters may support platform-specific extensions, but those extensions must be explicit.

Allowed extension handling:

- keep the portable ContractForge field as the primary intent
- add an adapter-specific extension block for native options
- return `REVIEW_REQUIRED` when native behavior may not preserve intent
- return `UNSUPPORTED` when no safe mapping exists

Disallowed handling:

- weakening write modes silently
- renaming core contract parameters to match one platform
- making Databricks, AWS, GCP, Snowflake or Fabric SDK concepts required by the core
- hiding platform-specific behavior inside portable fields

## Adapter Rule

Adapters conform to ContractForge contracts. ContractForge contracts do not conform to adapters.

When a platform cannot represent a ContractForge concept directly, the adapter must surface that gap as planning evidence.

Parameter-level parity by platform is maintained in [platform-contract-parity.md](platform-contract-parity.md).
