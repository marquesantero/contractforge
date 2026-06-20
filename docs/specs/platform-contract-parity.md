# Platform Contract Parameter Parity

## Purpose

This document defines how each ContractForge contract parameter maps to supported platform adapters.

ContractForge contracts are the source of truth. Adapters conform to the contract vocabulary and translate parameters into native capabilities when the platform can preserve the intended semantics.

Naming and extension rules are defined in [adapter-parameter-policy.md](adapter-parameter-policy.md).

Evidence/control-table column parity is defined separately in [control-table-parity.md](control-table-parity.md).

## Status Legend

| Status | Meaning |
| --- | --- |
| `SUPPORTED` | The adapter can preserve the ContractForge semantics directly. |
| `SUPPORTED_WITH_WARNINGS` | The adapter can implement the intent, but there are behavioral differences that must be surfaced. |
| `REVIEW_REQUIRED` | The platform has related primitives, but equivalence depends on project design or runtime choices. |
| `UNSUPPORTED` | The adapter cannot safely preserve the intent. |
| `PLATFORM_EXTENSION` | The concept exists only as a platform-specific extension and must not be treated as portable. |

## Platforms

Initial parity targets:

- Databricks
- AWS
- GCP
- Snowflake
- Fabric

Future adapters must add columns instead of weakening the ContractForge parameter definitions.

## Ingestion Contract Parameters

| ContractForge parameter | Semantics | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- | --- |
| `source.type: table` | Read from governed table. | `SUPPORTED`: UC/Hive table. | `SUPPORTED`: Glue Catalog table. | `SUPPORTED`: BigQuery/Dataproc catalog table. | `SUPPORTED`: table/view. | `SUPPORTED`: Lakehouse/Warehouse table. |
| `source.ref` / `source.table_ref` | Logical reference to another ContractForge-managed table using `layer.table` intent. | `SUPPORTED`: adapter resolves to catalog/schema/table. | `SUPPORTED`: adapter resolves to Glue Catalog/Iceberg table. | `SUPPORTED_WITH_WARNINGS`: adapter must define dataset/project naming. | `SUPPORTED_WITH_WARNINGS`: adapter must define database/schema naming. | `SUPPORTED_WITH_WARNINGS`: adapter must define lakehouse/warehouse naming. |
| `source.type: view` | Read from governed view. | `SUPPORTED`: UC/Hive view. | `SUPPORTED_WITH_WARNINGS`: engine/catalog dependent. | `SUPPORTED`: BigQuery view. | `SUPPORTED`: view. | `SUPPORTED_WITH_WARNINGS`: endpoint dependent. |
| `source.type: sql` | Read from declared SQL query. | `SUPPORTED`: Spark SQL. | `SUPPORTED_WITH_WARNINGS`: Athena/Glue/EMR dialect varies. | `SUPPORTED_WITH_WARNINGS`: BigQuery/Dataproc dialect varies. | `SUPPORTED`: Snowflake SQL. | `SUPPORTED_WITH_WARNINGS`: SQL endpoint/pipeline dialect varies. |
| `{{ table_ref:layer.table }}` in SQL | Logical table reference inside reviewed SQL. | `SUPPORTED`: adapter resolves before execution/rendering. | `SUPPORTED`: adapter resolves before Glue job rendering. | `SUPPORTED_WITH_WARNINGS`: SQL dialect and naming policy required. | `SUPPORTED_WITH_WARNINGS`: SQL dialect and naming policy required. | `SUPPORTED_WITH_WARNINGS`: SQL dialect and naming policy required. |
| `source.type: csv/json/parquet/orc/text/avro/xml` | Read bounded files in declared format. | `SUPPORTED_WITH_WARNINGS`: Spark readers; XML requires a runtime with native XML support or compatible parser options. | `SUPPORTED_WITH_WARNINGS`: Glue/EMR readers; XML parser options vary. | `SUPPORTED_WITH_WARNINGS`: Dataflow/Dataproc/BigQuery external flow; XML shape handling varies. | `SUPPORTED_WITH_WARNINGS`: staged file load semantics. | `SUPPORTED_WITH_WARNINGS`: Lakehouse/Dataflow readers; XML parser support varies. |
| `source.type: delta` | Read Delta data. | `SUPPORTED`: native Delta. | `REVIEW_REQUIRED`: connector/runtime dependent. | `REVIEW_REQUIRED`: connector/runtime dependent. | `REVIEW_REQUIRED`: external integration dependent. | `REVIEW_REQUIRED`: shortcut/runtime dependent. |
| `source.type: iceberg_table` | Read Iceberg table. | `SUPPORTED_WITH_WARNINGS`: runtime/catalog dependent. | `SUPPORTED`: Glue/Iceberg. | `SUPPORTED_WITH_WARNINGS`: BigLake/Dataproc dependent. | `SUPPORTED_WITH_WARNINGS`: external Iceberg support dependent. | `REVIEW_REQUIRED`: engine support varies. |
| `source.type: object_storage` | Read files from object storage. | `SUPPORTED`: S3/ADLS/GCS by runtime config. | `SUPPORTED`: S3. | `SUPPORTED`: GCS. | `SUPPORTED_WITH_WARNINGS`: stages required. | `SUPPORTED`: OneLake/shortcuts/ADLS. |
| `source.type: incremental_files` | Read newly discovered files with progress/checkpoint semantics. | `SUPPORTED`: Auto Loader/cloudFiles. | `SUPPORTED_WITH_WARNINGS`: Glue bookmarks or custom tracking. | `REVIEW_REQUIRED`: Dataflow/Dataproc/storage notifications. | `REVIEW_REQUIRED`: Snowpipe/copy history semantics. | `REVIEW_REQUIRED`: Dataflow Gen2/pipeline semantics. |
| `source.type: http_file/http_csv/http_json/http_text` | Bounded HTTP file fetch, then parse as file. | `SUPPORTED`: Python + Spark file read. | `SUPPORTED_WITH_WARNINGS`: job/runtime implementation. | `SUPPORTED_WITH_WARNINGS`: job/runtime implementation. | `REVIEW_REQUIRED`: stage/procedure pattern. | `SUPPORTED_WITH_WARNINGS`: pipeline/runtime implementation. |
| `source.type: jdbc/postgres/mysql/sqlserver/oracle/redshift/db2/mariadb` | Bounded JDBC batch source. | `SUPPORTED`: Spark JDBC, driver required. | `SUPPORTED`: Glue/EMR JDBC, driver required. | `SUPPORTED_WITH_WARNINGS`: Dataproc/Dataflow connector dependent. | `REVIEW_REQUIRED`: external access or Snowpark pattern. | `SUPPORTED_WITH_WARNINGS`: Dataflow/Pipeline connector dependent. |
| `source.type: kafka_bounded` | Bounded Kafka replay, not continuous streaming. | `SUPPORTED`: Spark Kafka batch read. | `SUPPORTED_WITH_WARNINGS`: Glue/EMR Kafka replay. | `SUPPORTED_WITH_WARNINGS`: Dataflow/Dataproc pattern. | `REVIEW_REQUIRED`: connector/Snowpipe Streaming differs. | `REVIEW_REQUIRED`: Real-Time/Fabric event semantics differ. |
| `source.type: eventhubs_bounded` | Bounded Event Hubs replay, not continuous streaming. | `SUPPORTED`: connector-backed batch read. | `REVIEW_REQUIRED`: cross-cloud connector design. | `REVIEW_REQUIRED`: cross-cloud connector design. | `REVIEW_REQUIRED`: connector design. | `SUPPORTED_WITH_WARNINGS`: Fabric/Eventstream semantics differ. |
| `source.type: delta_share` | Consume Delta Sharing table. | `SUPPORTED`: deltaSharing reader. | `SUPPORTED_WITH_WARNINGS`: connector dependent. | `SUPPORTED_WITH_WARNINGS`: connector dependent. | `SUPPORTED_WITH_WARNINGS`: marketplace/external table path. | `REVIEW_REQUIRED`: connector dependent. |
| `source.type: native_passthrough` | Delegate extraction to native platform connector. | `SUPPORTED_WITH_WARNINGS`: Lakeflow Connect/Connections. | `SUPPORTED_WITH_WARNINGS`: AppFlow/DMS/Glue native. | `SUPPORTED_WITH_WARNINGS`: Dataflow/Datastream/native connector. | `SUPPORTED_WITH_WARNINGS`: Snowflake connector/native ingestion. | `SUPPORTED_WITH_WARNINGS`: Dataflow Gen2/Pipeline connector. |
| `source.intent` | Optional planning intent layered on top of the source family. | `SUPPORTED_WITH_WARNINGS`: maps to native source strategy when declared. | `SUPPORTED_WITH_WARNINGS`: maps to Glue/EMR/AppFlow strategy when declared. | `SUPPORTED_WITH_WARNINGS`: maps to BigQuery/Dataflow/Dataproc strategy when declared. | `SUPPORTED_WITH_WARNINGS`: maps to Snowflake stage/stream/task strategy when declared. | `SUPPORTED_WITH_WARNINGS`: maps to Fabric pipeline/Dataflow strategy when declared. |
| `source.discovery` | Declares how new source data is discovered and tracked. | `SUPPORTED_WITH_WARNINGS`: file listing, Auto Loader notification or checkpoint behavior varies. | `SUPPORTED_WITH_WARNINGS`: S3 listing, notifications, Glue bookmarks or custom state. | `REVIEW_REQUIRED`: storage notifications/Dataflow design. | `REVIEW_REQUIRED`: stage listing, copy history or Snowpipe design. | `REVIEW_REQUIRED`: pipeline/Dataflow/Eventstream design. |
| `source.state` | Declares source progress state ownership/location. | `SUPPORTED_WITH_WARNINGS`: checkpoint/evidence location must be reachable. | `SUPPORTED_WITH_WARNINGS`: bookmarks, S3 state or evidence state. | `REVIEW_REQUIRED`: runner/state store design. | `REVIEW_REQUIRED`: table/stage/task state design. | `REVIEW_REQUIRED`: pipeline/lakehouse state design. |
| `source.watermark` | Incremental high-watermark intent. | `SUPPORTED`: query/filter/checkpoint dependent. | `SUPPORTED_WITH_WARNINGS`: bookmark/query dependent. | `SUPPORTED_WITH_WARNINGS`: query/pipeline dependent. | `SUPPORTED_WITH_WARNINGS`: streams/tasks/query dependent. | `SUPPORTED_WITH_WARNINGS`: pipeline/Dataflow dependent. |
| `source.progress_location` | Portable progress/checkpoint state location for incremental reads. | `SUPPORTED`: streaming checkpoint location. | `SUPPORTED_WITH_WARNINGS`: external state/bookmark path when needed. | `REVIEW_REQUIRED`: runner/state design. | `REVIEW_REQUIRED`: stage/copy-history/state design. | `REVIEW_REQUIRED`: pipeline state design. |
| `source.schema_tracking_location` | Portable schema inference/evolution tracking location. | `SUPPORTED`: `cloudFiles.schemaLocation`. | `SUPPORTED_WITH_WARNINGS`: schema registry/catalog location when needed. | `REVIEW_REQUIRED`: schema tracking design. | `REVIEW_REQUIRED`: stage/table schema design. | `REVIEW_REQUIRED`: Dataflow/lakehouse schema design. |
| `source.options` | Source read options. | `SUPPORTED_WITH_WARNINGS`: adapter must classify options. | `SUPPORTED_WITH_WARNINGS`: adapter must classify options. | `SUPPORTED_WITH_WARNINGS`: adapter must classify options. | `SUPPORTED_WITH_WARNINGS`: adapter must classify options. | `SUPPORTED_WITH_WARNINGS`: adapter must classify options. |
| `source.auth` | Authentication metadata or secret reference. | `REVIEW_REQUIRED`: secrets/workspace policy. | `REVIEW_REQUIRED`: IAM/Secrets Manager. | `REVIEW_REQUIRED`: IAM/Secret Manager. | `REVIEW_REQUIRED`: integrations/secrets. | `REVIEW_REQUIRED`: connections/key vault. |
| `environment.parameters.<adapter>` | Environment-level native adapter parameters and defaults. | `PLATFORM_EXTENSION`: Databricks parameters. | `PLATFORM_EXTENSION`: AWS parameters. | `PLATFORM_EXTENSION`: GCP parameters. | `PLATFORM_EXTENSION`: Snowflake parameters. | `PLATFORM_EXTENSION`: Fabric parameters. |
| `target.catalog` | Top-level governed namespace. | `SUPPORTED`: catalog. | `SUPPORTED_WITH_WARNINGS`: catalog/account/database mapping. | `SUPPORTED`: project or catalog mapping. | `SUPPORTED`: database mapping. | `SUPPORTED_WITH_WARNINGS`: workspace/lakehouse mapping. |
| `target.catalog_type` | Optional neutral classification for a logical catalog name. | `SUPPORTED`: metastore/catalog mapping. | `SUPPORTED_WITH_WARNINGS`: Glue Catalog/database mapping. | `SUPPORTED_WITH_WARNINGS`: project/dataset/catalog mapping. | `SUPPORTED`: database/catalog mapping. | `SUPPORTED_WITH_WARNINGS`: workspace/lakehouse mapping. |
| `target.schema` | Schema/database namespace. | `SUPPORTED`: schema. | `SUPPORTED`: database/schema. | `SUPPORTED`: dataset. | `SUPPORTED`: schema. | `SUPPORTED`: lakehouse/schema equivalent where available. |
| `target.table` | Target object name. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `layer` | Logical medallion or delivery layer. | `SUPPORTED`: metadata/naming. | `SUPPORTED`: metadata/naming. | `SUPPORTED`: metadata/naming. | `SUPPORTED`: metadata/naming. | `SUPPORTED`: metadata/naming. |
| `mode: append` | Append rows. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `mode: overwrite` | Replace target or declared overwrite scope. | `SUPPORTED`: Delta overwrite. | `SUPPORTED_WITH_WARNINGS`: atomicity by format/engine. | `SUPPORTED_WITH_WARNINGS`: table/file semantics vary. | `SUPPORTED`: table replacement/overwrite. | `SUPPORTED_WITH_WARNINGS`: pipeline/lakehouse semantics vary. |
| `mode: upsert` | Current-state merge by keys. | `SUPPORTED`: Delta MERGE. | `SUPPORTED_WITH_WARNINGS`: Iceberg/Hudi/engine dependent. | `SUPPORTED`: BigQuery MERGE, or Dataproc table format. | `SUPPORTED`: MERGE. | `REVIEW_REQUIRED`: pipeline/SQL endpoint capability. |
| `mode: hash_diff_upsert` | current-state merge with hash change detection. | `SUPPORTED`: ContractForge hash prep + Delta MERGE. | `SUPPORTED_WITH_WARNINGS`: hash function/type semantics. | `SUPPORTED_WITH_WARNINGS`: hash function/type semantics. | `SUPPORTED_WITH_WARNINGS`: hash function/type semantics. | `REVIEW_REQUIRED`: implementation design. |
| `mode: historical` | Preserve history with current/validity markers. | `SUPPORTED`: Delta MERGE pattern; Lakeflow requires review. | `REVIEW_REQUIRED`: table format and delete/update semantics. | `REVIEW_REQUIRED`: MERGE and late-arriving policy design. | `REVIEW_REQUIRED`: MERGE/streams/tasks design. | `REVIEW_REQUIRED`: pipeline/lakehouse design. |
| `mode: snapshot_reconcile_soft_delete` | Mark missing snapshot keys inactive/deleted. | `SUPPORTED_WITH_WARNINGS`: Delta `NOT MATCHED BY SOURCE` semantics. | `REVIEW_REQUIRED`: engine/table-format dependent. | `REVIEW_REQUIRED`: MERGE semantics. | `SUPPORTED_WITH_WARNINGS`: MERGE semantics. | `REVIEW_REQUIRED`: pipeline design. |
| `schema_policy: strict` | Reject schema drift. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `schema_policy: additive_only` | Allow nullable additive columns only. | `SUPPORTED`: Delta evolution plus preflight. | `SUPPORTED_WITH_WARNINGS`: format/catalog dependent. | `SUPPORTED_WITH_WARNINGS`: platform type rules. | `SUPPORTED_WITH_WARNINGS`: DDL/type rules. | `SUPPORTED_WITH_WARNINGS`: lakehouse/pipeline rules. |
| `schema_policy: permissive` | Allow reviewed schema evolution. | `SUPPORTED_WITH_WARNINGS`: type widening must be reviewed. | `SUPPORTED_WITH_WARNINGS`. | `SUPPORTED_WITH_WARNINGS`. | `SUPPORTED_WITH_WARNINGS`. | `SUPPORTED_WITH_WARNINGS`. |
| `quality_rules.not_null` | Assert columns are not null. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `quality_rules.required_columns` | Assert required schema columns exist. | `SUPPORTED`: schema inspection or information schema. | `SUPPORTED`: catalog/schema inspection. | `SUPPORTED`: catalog/schema inspection. | `SUPPORTED`: information schema. | `SUPPORTED_WITH_WARNINGS`: lakehouse metadata dependent. |
| `quality_rules.unique_key` | Assert no duplicate key groups. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `quality_rules.accepted_values` | Assert finite accepted values. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `quality_rules.min_rows` | Assert minimum row count. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `quality_rules.max_null_ratio` | Assert column null ratio is below threshold. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `quality_rules.expressions` | Assert custom boolean expressions. | `SUPPORTED_WITH_WARNINGS`: SQL dialect review. | `SUPPORTED_WITH_WARNINGS`: SQL dialect review. | `SUPPORTED_WITH_WARNINGS`: SQL dialect review. | `SUPPORTED_WITH_WARNINGS`: SQL dialect review. | `SUPPORTED_WITH_WARNINGS`: SQL dialect review. |
| `on_quality_fail` | Global action when quality checks fail: fail, warn or quarantine. | `SUPPORTED`: runtime quality action. | `SUPPORTED_WITH_WARNINGS`: runtime enforcement/evidence design. | `SUPPORTED_WITH_WARNINGS`: runtime enforcement/evidence design. | `SUPPORTED_WITH_WARNINGS`: task/procedure enforcement design. | `SUPPORTED_WITH_WARNINGS`: pipeline enforcement design. |
| `shape` | Structural shaping before write. | `SUPPORTED_WITH_WARNINGS`: PySpark shape algorithms. | `SUPPORTED_WITH_WARNINGS`: Spark/Glue or equivalent. | `REVIEW_REQUIRED`: BigQuery/Dataflow/Dataproc mapping. | `REVIEW_REQUIRED`: Snowpark/SQL mapping. | `REVIEW_REQUIRED`: Dataflow/Pipeline mapping. |
| `transform` | Lightweight cast/derive/standardize/deduplicate. | `SUPPORTED_WITH_WARNINGS`: PySpark/SQL mapping. | `SUPPORTED_WITH_WARNINGS`: Spark/SQL mapping. | `REVIEW_REQUIRED`: dialect mapping. | `REVIEW_REQUIRED`: SQL/Snowpark mapping. | `REVIEW_REQUIRED`: pipeline mapping. |
| `execution.freshness` | Desired freshness class, not a scheduler primitive. | `SUPPORTED_WITH_WARNINGS`: jobs, workflows or streams depending on adapter plan. | `SUPPORTED_WITH_WARNINGS`: Glue schedules, EventBridge, streaming or review. | `SUPPORTED_WITH_WARNINGS`: scheduler/Dataflow/BigQuery design. | `SUPPORTED_WITH_WARNINGS`: tasks/streams design. | `SUPPORTED_WITH_WARNINGS`: pipeline/Eventstream design. |
| `execution.latency_target` | Readable latency objective for planning/evidence. | `SUPPORTED`: preserved in plan/evidence; enforcement varies. | `SUPPORTED`: preserved in plan/evidence; enforcement varies. | `SUPPORTED`: preserved in plan/evidence; enforcement varies. | `SUPPORTED`: preserved in plan/evidence; enforcement varies. | `SUPPORTED`: preserved in plan/evidence; enforcement varies. |
| `execution.preferred` | Preferred execution style such as scheduled, event-driven, continuous or available-now. | `SUPPORTED_WITH_WARNINGS`: depends on declared source/write semantics. | `SUPPORTED_WITH_WARNINGS`: depends on Glue/EMR/EventBridge capability. | `REVIEW_REQUIRED`: runner choice affects semantics. | `REVIEW_REQUIRED`: stream/task/Snowpipe design. | `REVIEW_REQUIRED`: pipeline/Eventstream design. |
| `execution.fallback` | Declared behavior if preferred execution cannot be preserved. | `SUPPORTED`: adapter must honor fallback or block. | `SUPPORTED`: adapter must honor fallback or block. | `SUPPORTED`: adapter must honor fallback or block. | `SUPPORTED`: adapter must honor fallback or block. | `SUPPORTED`: adapter must honor fallback or block. |

## Annotations Contract Parameters

| ContractForge parameter | Semantics | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- | --- |
| `annotations.policy` | `fail`, `warn` or `ignore` application behavior. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `annotations.table.description` | Readable table description. | `SUPPORTED`: table comment. | `SUPPORTED_WITH_WARNINGS`: Glue description/catalog metadata. | `SUPPORTED`: BigQuery/Dataplex description. | `SUPPORTED`: COMMENT. | `SUPPORTED_WITH_WARNINGS`: Lakehouse/Purview metadata. |
| `annotations.table.aliases` | Alternate business names. | `SUPPORTED_WITH_WARNINGS`: UC tags. | `SUPPORTED_WITH_WARNINGS`: Glue/LF tags. | `SUPPORTED_WITH_WARNINGS`: Data Catalog tags. | `SUPPORTED_WITH_WARNINGS`: tags. | `SUPPORTED_WITH_WARNINGS`: Purview/Fabric metadata. |
| `annotations.table.tags` | Table classification metadata. | `SUPPORTED`: UC tags. | `SUPPORTED_WITH_WARNINGS`: Glue/LF tags. | `SUPPORTED_WITH_WARNINGS`: Data Catalog tags/policy tags. | `SUPPORTED`: tags. | `SUPPORTED_WITH_WARNINGS`: Purview/Fabric metadata. |
| `annotations.table.deprecated.since` | Deprecation start metadata. | `SUPPORTED_WITH_WARNINGS`: UC tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: metadata/tag. |
| `annotations.table.deprecated.replacement` | Replacement object metadata. | `SUPPORTED_WITH_WARNINGS`: UC tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: metadata/tag. |
| `annotations.table.deprecated.removal_date` | Planned removal metadata. | `SUPPORTED_WITH_WARNINGS`: UC tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: metadata/tag. |
| `annotations.columns.*.description` | Readable column description. | `SUPPORTED`: column comment. | `SUPPORTED_WITH_WARNINGS`: catalog column comment. | `SUPPORTED`: BigQuery column description. | `SUPPORTED`: COMMENT. | `SUPPORTED_WITH_WARNINGS`: model/catalog metadata. |
| `annotations.columns.*.aliases` | Alternate column business names. | `SUPPORTED_WITH_WARNINGS`: UC tags. | `SUPPORTED_WITH_WARNINGS`: tags. | `SUPPORTED_WITH_WARNINGS`: Data Catalog tags. | `SUPPORTED_WITH_WARNINGS`: tags. | `SUPPORTED_WITH_WARNINGS`: metadata/tag. |
| `annotations.columns.*.tags` | Column classification metadata. | `SUPPORTED`: UC tags. | `SUPPORTED_WITH_WARNINGS`: LF tags/classification. | `SUPPORTED_WITH_WARNINGS`: policy tags/Data Catalog. | `SUPPORTED`: tags. | `SUPPORTED_WITH_WARNINGS`: Purview/Fabric metadata. |
| `annotations.columns.*.pii.enabled` | Marks column as PII. | `SUPPORTED_WITH_WARNINGS`: tag; enforcement separate. | `SUPPORTED_WITH_WARNINGS`: LF tag/classification. | `SUPPORTED_WITH_WARNINGS`: policy tag/classification. | `SUPPORTED_WITH_WARNINGS`: tag/masking review. | `SUPPORTED_WITH_WARNINGS`: Purview sensitivity. |
| `annotations.columns.*.pii.type` | PII type taxonomy. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: tag/classification. | `SUPPORTED_WITH_WARNINGS`: policy tag taxonomy. | `SUPPORTED_WITH_WARNINGS`: tag/classification. | `SUPPORTED_WITH_WARNINGS`: Purview classification. |
| `annotations.columns.*.pii.sensitivity` | Sensitivity level. | `SUPPORTED_WITH_WARNINGS`: tag. | `SUPPORTED_WITH_WARNINGS`: LF/Purview-equivalent tag. | `SUPPORTED_WITH_WARNINGS`: policy tag. | `SUPPORTED_WITH_WARNINGS`: tag/classification. | `SUPPORTED_WITH_WARNINGS`: sensitivity label. |
| `annotations.columns.*.deprecated.*` | Column lifecycle metadata. | `SUPPORTED_WITH_WARNINGS`: UC tags. | `SUPPORTED_WITH_WARNINGS`: tags. | `SUPPORTED_WITH_WARNINGS`: tags. | `SUPPORTED_WITH_WARNINGS`: tags. | `SUPPORTED_WITH_WARNINGS`: metadata/tag. |

## Operations Contract Parameters

| ContractForge parameter | Semantics | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- | --- |
| `operations.ownership.business_owner` | Business accountable owner. | `SUPPORTED`: evidence/catalog metadata. | `SUPPORTED`: evidence/catalog metadata. | `SUPPORTED`: evidence/catalog metadata. | `SUPPORTED`: evidence/tag metadata. | `SUPPORTED`: evidence/Purview metadata. |
| `operations.ownership.technical_owner` | Technical accountable owner. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.ownership.steward` | Data steward. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.ownership.support_group` | Support team. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.ownership.escalation_group` | Escalation team. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.criticality` | Operational criticality. | `SUPPORTED`: evidence/control table. | `SUPPORTED`: evidence store. | `SUPPORTED`: evidence store. | `SUPPORTED`: evidence/audit table. | `SUPPORTED`: evidence/lakehouse table. |
| `operations.expected_frequency` | Expected ingestion cadence. | `SUPPORTED`: evidence and dashboard logic. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.freshness_sla_minutes` | SLA threshold for freshness. | `SUPPORTED`: evidence/dashboard logic. | `SUPPORTED_WITH_WARNINGS`: monitor implementation varies. | `SUPPORTED_WITH_WARNINGS`: monitor implementation varies. | `SUPPORTED_WITH_WARNINGS`: task/monitor implementation. | `SUPPORTED_WITH_WARNINGS`: monitor implementation varies. |
| `operations.alert_on_failure` | Alerting intent. | `REVIEW_REQUIRED`: platform alert integration. | `REVIEW_REQUIRED`: CloudWatch/EventBridge/SNS. | `REVIEW_REQUIRED`: Cloud Monitoring/PubSub. | `REVIEW_REQUIRED`: alerts/tasks/external integration. | `REVIEW_REQUIRED`: Fabric/Data Activator/Power Automate. |
| `operations.alert_on_quality_fail` | Quality alerting intent. | `REVIEW_REQUIRED`. | `REVIEW_REQUIRED`. | `REVIEW_REQUIRED`. | `REVIEW_REQUIRED`. | `REVIEW_REQUIRED`. |
| `operations.runbook_url` | Runbook reference. | `SUPPORTED`: evidence/catalog metadata. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.owners` | Additional owners. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.groups` | Additional groups. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `operations.tags` | Operational metadata tags. | `SUPPORTED_WITH_WARNINGS`: evidence/tags. | `SUPPORTED_WITH_WARNINGS`: evidence/tags. | `SUPPORTED_WITH_WARNINGS`: evidence/tags. | `SUPPORTED_WITH_WARNINGS`: tags. | `SUPPORTED_WITH_WARNINGS`: Purview/Fabric metadata. |

## Access Contract Parameters

| ContractForge parameter | Semantics | Databricks | AWS | GCP | Snowflake | Fabric |
| --- | --- | --- | --- | --- | --- | --- |
| `access.access_policy.mode` | `apply`, `validate_only` or `ignore`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. | `SUPPORTED`. |
| `access.access_policy.on_drift` | Drift behavior: `warn`, `fail`, `reconcile`. | `SUPPORTED_WITH_WARNINGS`: reconcile needs explicit runtime path. | `SUPPORTED_WITH_WARNINGS`: reconcile risk with LF/IAM inheritance. | `SUPPORTED_WITH_WARNINGS`: IAM inheritance. | `SUPPORTED_WITH_WARNINGS`: role hierarchy. | `SUPPORTED_WITH_WARNINGS`: workspace inheritance. |
| `access.access_policy.revoke_unmanaged` | Remove privileges not declared by contract. | `REVIEW_REQUIRED`: destructive access change. | `REVIEW_REQUIRED`: IAM/LF inheritance risk. | `REVIEW_REQUIRED`: IAM inheritance risk. | `REVIEW_REQUIRED`: role hierarchy risk. | `REVIEW_REQUIRED`: workspace inheritance risk. |
| `access.grants[].principal` | User/group/service principal. | `SUPPORTED`: UC principal. | `SUPPORTED_WITH_WARNINGS`: IAM/LF principal mapping. | `SUPPORTED_WITH_WARNINGS`: IAM principal mapping. | `SUPPORTED`: role/user mapping. | `SUPPORTED_WITH_WARNINGS`: workspace/AAD principal mapping. |
| `access.grants[].privileges` | ContractForge privilege vocabulary. | `SUPPORTED_WITH_WARNINGS`: UC privilege subset. | `SUPPORTED_WITH_WARNINGS`: LF/IAM action mapping. | `SUPPORTED_WITH_WARNINGS`: IAM/BigQuery role mapping. | `SUPPORTED_WITH_WARNINGS`: Snowflake privilege mapping. | `SUPPORTED_WITH_WARNINGS`: Fabric permission mapping. |
| `access.row_filters[].name` | Named row filter intent. | `SUPPORTED`: UC row filter. | `REVIEW_REQUIRED`: LF row-level filters. | `SUPPORTED_WITH_WARNINGS`: row access policy. | `SUPPORTED`: row access policy. | `REVIEW_REQUIRED`: security model differs. |
| `access.row_filters[].function` | Function/policy expression reference. | `SUPPORTED`: UC function. | `REVIEW_REQUIRED`: LF expression/model differs. | `SUPPORTED_WITH_WARNINGS`: row access policy expression. | `SUPPORTED_WITH_WARNINGS`: policy function/expression. | `REVIEW_REQUIRED`: pipeline/security artifact. |
| `access.row_filters[].columns` | Columns used by row filter. | `SUPPORTED`. | `REVIEW_REQUIRED`. | `SUPPORTED_WITH_WARNINGS`. | `SUPPORTED_WITH_WARNINGS`. | `REVIEW_REQUIRED`. |
| `access.row_filters[].applies_to.principals` | Principal scope for row filter. | `SUPPORTED_WITH_WARNINGS`: policy function may encode principal logic. | `REVIEW_REQUIRED`. | `SUPPORTED_WITH_WARNINGS`: policy design. | `SUPPORTED_WITH_WARNINGS`: policy design. | `REVIEW_REQUIRED`. |
| `access.column_masks.*.function` | Column mask function/policy reference. | `SUPPORTED`: UC mask. | `REVIEW_REQUIRED`: LF tags/policies. | `SUPPORTED_WITH_WARNINGS`: policy tags/masking. | `SUPPORTED`: masking policy. | `REVIEW_REQUIRED`: sensitivity/security model. |
| `access.column_masks.*.using_columns` | Columns passed to mask function. | `SUPPORTED`. | `REVIEW_REQUIRED`. | `REVIEW_REQUIRED`: policy-tag model may not match. | `SUPPORTED_WITH_WARNINGS`: policy signature semantics. | `REVIEW_REQUIRED`. |
| `access.column_masks.*.applies_to.principals` | Principal scope for mask. | `SUPPORTED_WITH_WARNINGS`: mask function may encode principal logic. | `REVIEW_REQUIRED`. | `REVIEW_REQUIRED`. | `SUPPORTED_WITH_WARNINGS`: policy/role design. | `REVIEW_REQUIRED`. |

## Platform Extension Parameters

Platform-specific parameters must live under the environment contract or adapter-owned artifacts.

| Concept | ContractForge portable parameter | Databricks extension | AWS extension | GCP extension | Snowflake extension | Fabric extension |
| --- | --- | --- | --- | --- | --- | --- |
| File incremental engine | `source.type: incremental_files` | `cloudFiles` options | bookmark options | Dataflow/Dataproc notification options | Snowpipe/copy-history options | Dataflow Gen2/pipeline options |
| Native SaaS ingestion | `source.type: native_passthrough` | Lakeflow Connect / Connections | AppFlow / DMS / Glue connector | Dataflow / Datastream connector | Native connector / marketplace / external access | Dataflow Gen2 / Data Pipeline |
| Table optimization | no portable core execution parameter yet | OPTIMIZE, VACUUM, liquid clustering | compaction, table optimization | BigQuery clustering/partitioning | clustering/search optimization | Lakehouse optimization |
| Catalog security tags | `annotations.*.tags`, `access.*` | UC tags and policies | LF tags | policy tags/Data Catalog | tags/classifications | Purview/Fabric metadata |
| Jobs/deployment | adapter rendering only | Databricks Asset Bundles/Jobs | Glue workflows/Step Functions | Cloud Composer/Workflows | Tasks | Fabric pipelines |
| Evidence location | `environment.evidence` | Delta evidence catalog/schema | Glue/Iceberg/S3 evidence location | BigQuery/GCS evidence location | audit schema/table location | Lakehouse evidence location |
| Runtime binding | `environment.runtime` | warehouse/job/cluster/serverless context | Glue/EMR/Lambda context | Dataflow/Dataproc/BigQuery context | warehouse/task context | Fabric capacity/pipeline context |

## Adapter Planning Rules

1. Validate the full ContractForge contract first.
2. Normalize to semantic core models.
3. Match every declared parameter against platform capabilities.
4. Return `SUPPORTED` only when all declared semantics can be preserved.
5. Return `SUPPORTED_WITH_WARNINGS` when implementation is possible but behavior differs.
6. Return `REVIEW_REQUIRED` when design choices affect equivalence.
7. Return `UNSUPPORTED` when the adapter cannot preserve the intent.
8. Never drop, rename or weaken a ContractForge parameter to fit a platform.

## Maintenance Rule

Every new ContractForge contract parameter requires:

- update this parity matrix
- core validation
- semantic normalization when applicable
- capability mapping
- adapter behavior, warning, review marker or blocker
- tests showing at least one supported and one non-supported planning path when portability is not universal
