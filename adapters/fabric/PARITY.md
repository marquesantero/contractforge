# ContractForge Fabric Parity Review

This document is a local validation draft for the Microsoft Fabric adapter.
It is not a site publication document and it does not claim production maturity.

## Research Basis

This revision was checked against official Microsoft Fabric documentation through
Context7 and Microsoft Learn references.

| Official area | Finding that affects the adapter |
| --- | --- |
| Lakehouse and OneLake | Fabric Lakehouse standardizes on Delta tables in OneLake, and Fabric notebooks can read from `Files` and write Delta data under `Tables`. This makes a notebook-first Lakehouse runtime the most direct first execution path. |
| Shortcuts | Shortcuts in the Lakehouse `Tables` area can be queried as tables when the target data is compatible, such as Delta/Parquet. Shortcut-backed source support must stay review-required until the adapter validates table recognition and security behavior. |
| SQL endpoint and Warehouse | SQL is useful for validation, quality checks and downstream reads, but a first writer should not assume every Lakehouse write mode is better expressed through the SQL endpoint. Spark/Delta notebooks are the safer initial implementation path. |
| Fabric REST item APIs | Workspaces and items such as Lakehouses, Notebooks and Data Pipelines can be automated through Fabric REST APIs. Several item operations are long-running operations and must handle `Location`, `x-ms-operation-id`, `Retry-After` and `429` throttling. |
| Permissions | Item creation/update requires workspace roles such as contributor and delegated scopes such as `Item.ReadWrite.All` or item-specific scopes like `Notebook.ReadWrite.All`. Runtime execution needs explicit execute permissions. |
| Capacity | Creating non-Power BI Fabric items through REST requires the workspace to be on supported Fabric capacity. A smoke test must fail clearly when capacity is missing. |
| Spark pool sizing | Small capacities can fail when the workspace default Starter Pool uses Medium nodes. For FTL4, a single-node Small custom pool is the safer smoke-test default. |
| Data Factory CI/CD | Fabric Data Factory supports Git integration and deployment pipelines. Unlike Azure Data Factory, individual pipelines can be updated, but Git/deployment pipelines map workspaces to environments, so dev/test/prod should be modeled as separate workspaces. |
| Governance and sensitivity | Fabric governance integrates with Microsoft Purview and sensitivity labels, but some label scenarios limit Git integration or deployment pipelines. Access-policy apply mode must be a later gate, not part of the first runtime slice. |

Primary references used for this review:

- [Microsoft Fabric documentation](https://github.com/microsoftdocs/fabric-docs)
- [Fabric REST API overview](https://learn.microsoft.com/en-us/rest/api/fabric/articles)
- [Create Fabric item REST API](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/create-item)
- [Get Fabric item definition REST API](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/get-item-definition)
- [Data Factory CI/CD in Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/data-factory/cicd-pipelines)
- [Microsoft Fabric governance overview](https://learn.microsoft.com/en-us/fabric/governance/governance-compliance-overview)

## Current Status

| Area | Status | Notes |
| --- | --- | --- |
| Package shape | `SUPPORTED` | `contractforge-fabric` builds as an independent adapter wheel. |
| Public API | `SUPPORTED` | Exposes `plan_fabric_contract`, `render_fabric_contract`, source support helpers and subtarget helpers. |
| Subtarget | `SUPPORTED` | Initial target is `fabric_lakehouse`. |
| Planning | `SUPPORTED_WITH_WARNINGS` | Core planning works, but every supported contract receives a warning that full Fabric runtime parity is still pending. |
| Rendering | `SUPPORTED_WITH_WARNINGS` | Emits review, capability, source-support, runtime TODO, notebook draft, notebook definition draft, contract and manifest artifacts. |
| Source review artifacts | `SUPPORTED_LOCAL_TESTS` | Every contract render emits redacted `.fabric.source_review.json` and `.fabric.source_review.md` artifacts with source-specific Fabric prerequisites and graduation gates. |
| Runtime execution | `READ_WRITE_E2E` | Fabric REST preflight, Notebook deployment, run submission and terminal job classification exist. A public REST/GeoJSON bronze-to-gold chain completed on Fabric, and the SQL-source stable-surface suite validated core write modes plus failure-path evidence. Data Factory pipelines and adapter-wide source/governance parity remain outside the stable-final claim unless separately certified. |
| REST primitives | `SUPPORTED_LOCAL_TESTS` | Dependency-free client primitives cover Notebook create/update/get-definition request shape, async get-definition result polling, workspace discovery, capacity listing, Spark pool/settings management, item job-instance listing, LRO polling and `429` retry handling with fake transports. |
| Tenant/auth binding | `READ_ONLY_SMOKE` | Azure CLI can mint a Fabric API Bearer token for tenant `00000000-0000-0000-0000-000000000000`; read-only workspace listing succeeded. |
| Capacity preflight | `READ_ONLY_SMOKE` | Workspace `Manager` resolves to `00000000-0000-0000-0000-000000000000` with capacity `00000000-0000-0000-0000-000000000000`, SKU `FTL4`, assignment `Completed`, region `Brazil South`. The default Starter Pool was Medium; a `Small` single-node custom pool (`cf_small_single_node`, `00000000-0000-0000-0000-000000000000`) was created and set as the workspace default to fit FTL4. |
| Spark settings preflight | `READ_ONLY_SMOKE` | `contractforge-fabric preflight --check-spark-settings` resolves capacity SKU, default Spark pool and Starter Pool shape. The live workspace now reports `FABRIC_SPARK_POOL_COMPATIBLE` for `FTL4` with `cf_small_single_node` as default. |
| Notebook job preflight | `READ_ONLY_SMOKE` | `contractforge-fabric preflight --check-notebook-jobs` lists Notebook job instances and warns when active jobs can consume capacity. The live smoke Notebook currently reports eight historical runs, zero active jobs and latest completed run `00000000-0000-0000-0000-000000000000`. |
| Item preflight | `READ_WRITE_SMOKE` | Workspace item listing succeeded. Created empty Lakehouse `contractforge_lh` (`00000000-0000-0000-0000-000000000000`) and generated Notebook `cf_workspace_bronze_orders` (`00000000-0000-0000-0000-000000000000`) in `Manager`; required Lakehouse/Notebook preflight now resolves cleanly. |
| Notebook execution | `READ_WRITE_SMOKE` | A contract-generated SQL smoke Notebook (`cf_default_cf_smoke_sql`, `00000000-0000-0000-0000-000000000000`) was submitted with default Lakehouse binding. On June 11, 2026, the public Notebook API still failed with `TooManyRequestsForCapacity` / HTTP 430 while the workspace default was Starter Pool Medium (`00000000-0000-0000-0000-000000000000`). After switching the workspace default Spark pool to `cf_small_single_node`, the same generated smoke notebook completed successfully (`00000000-0000-0000-0000-000000000000`). |
| USGS REST/GeoJSON E2E | `READ_WRITE_E2E` | On June 11, 2026, the same USGS medallion intent used for Databricks/AWS/Snowflake ran in Fabric from bronze to silver to two gold outputs with generated notebooks only. Successful job ids: bronze `00000000-0000-0000-0000-000000000000`, silver `00000000-0000-0000-0000-000000000000`, gold daily `00000000-0000-0000-0000-000000000000`, gold bands `00000000-0000-0000-0000-000000000000`; validation contract `00000000-0000-0000-0000-000000000000` checked bronze count = 1 and downstream counts > 0. |
| Smoke workflow | `SUPPORTED_LOCAL_TESTS` | `run_fabric_contract_smoke()` and `contractforge-fabric smoke` perform preflight, Notebook deployment, run submission, terminal job waiting and normalized evidence serialization. Real execution still depends on capacity availability. |
| REST automation | `PARTIAL_SMOKE` | Azure CLI authentication, workspace/item resolution, capacity preflight, Spark pool checks, Notebook job-history checks, Notebook create/update/get-definition including async export results, workspace role assignment APIs, sensitivity-label APIs, OneLake data access role APIs with row/column constraints, deployment-pipeline list/stage/deploy APIs, Git connect API shape, definition fingerprinting, non-destructive update guards, LRO polling and throttling classification exist. |
| Evidence DDL/bootstrap | `SUPPORTED_LOCAL_TESTS` | Review bundles render Fabric Lakehouse Delta DDL for the shared ContractForge evidence and state tables. Generated notebooks bootstrap those evidence/state tables by default before execution, with an opt-out for managed environments. |
| Runtime run/error evidence | `READ_WRITE_E2E` | Generated notebooks record run and error rows to the shared evidence schema. The stable-surface suite probes successful and controlled-failure rows in live Fabric control tables. |
| Source metadata evidence | `READ_WRITE_E2E` | Generated notebooks write `ctrl_ingestion_metadata` source rows with core source metadata, observed row/column counts and Spark schema. The stable-surface suite probes metadata rows in live Fabric. |
| Schema policy and evidence | `READ_WRITE_E2E` | Generated notebooks validate `strict`, `additive_only` and `permissive` policy semantics before writes when Spark can read the target schema, then write policy-aware schema evidence to `ctrl_ingestion_schema_changes`. The stable-surface suite validates strict-schema failure evidence through live control-table rows. |
| Explain evidence | `READ_WRITE_E2E` | Generated notebooks write best-effort Spark query execution plans to `ctrl_ingestion_explain`; the stable-surface suite probes explain rows in live Fabric control tables. |
| Hash-diff upsert | `READ_WRITE_E2E` | Generated notebooks compute deterministic `row_hash` values for `hash_diff_upsert`, skip unchanged rows when target hashes are readable and merge only new or changed rows. The stable-surface suite validated seed, no-op and changed waves on Fabric. |
| Historical SCD2 | `READ_WRITE_E2E` | Generated notebooks support `historical` by computing `row_hash`, staging expire/insert rows, expiring changed current rows and inserting new versions. The stable-surface suite validated seed and changed waves on Fabric. |
| Snapshot reconciliation with soft delete | `READ_WRITE_E2E` | Generated notebooks support `snapshot_reconcile_soft_delete` when the contract declares a complete source snapshot, computing `row_hash`, upserting active rows and soft-deleting target rows no longer present in the source. The stable-surface suite validated seed and delete waves on Fabric. |
| Runtime state updates and locks | `SUPPORTED_WITH_WARNINGS` | Generated notebooks append successful-run state rows to `ctrl_ingestion_state`, including a single-column watermark candidate when declared; the stable-surface suite probes state rows in live Fabric. Opt-in `extensions.fabric.lock_enabled` renders Delta lock acquire/release SQL against `ctrl_ingestion_locks`; real concurrent execution semantics remain pending capacity-stable Fabric validation. |
| Quality gates | `READ_WRITE_E2E` | Generated notebooks render core Spark checks for required columns, not-null, accepted values, unique keys, minimum rows, max null ratio and expressions, and write per-rule quality evidence rows. The stable-surface suite validates successful and aborting quality evidence in live Fabric. |
| Quarantine evidence | `SUPPORTED_LOCAL_TESTS` | Generated notebooks write failed-row payloads to `ctrl_ingestion_quarantine` for row-predicate rules with `severity: quarantine`. Aggregate-rule quarantine remains summary-only. |
| Portable shape | `READ_WRITE_E2E` | Generated notebooks render `shape.parse_json`, single-step `shape.arrays` with `explode` or `explode_outer`, `shape.columns` and `shape.flatten` before transforms, quality, schema and writes. The USGS silver run validated `parse_json` + `explode_outer` on Fabric. Cartesian/zip-array semantics remain review-only. |
| Portable transforms | `SUPPORTED_LOCAL_TESTS` | Generated notebooks render `transform.cast`, `transform.standardize`, `transform.derive`, `transform.composite_keys` and deterministic `transform.deduplicate` before quality/schema/write. Non-portable deduplicate order expressions remain review-only. |
| Public bounded HTTP/REST sources | `READ_WRITE_E2E` for public REST, public `http_json`, public `http_csv`, public `http_text`, authenticated REST Basic/bearer/API-key/OAuth, authenticated `http_json` Basic/bearer/API-key, authenticated `http_csv` Basic/bearer/API-key and endpoint-enforced `http_text` Basic/bearer/API-key auth | Generated notebooks materialize public/no-auth `http_file`, `http_json`, `http_csv`, `http_text` and `rest_api` sources through the shared ContractForge core readers. The USGS REST/GeoJSON bronze-to-gold run proves the public REST path in live Fabric; `docs/reports/fabric-http-json-source-smoke.json` proves the public bounded HTTP JSON path; `docs/reports/fabric-http-csv-source-smoke.json` proves the public bounded HTTP CSV path; `docs/reports/fabric-http-text-source-smoke.json` proves the public bounded HTTP text path; `docs/reports/fabric-auth-rest-source-smoke.json` proves Basic-auth REST with Azure Key Vault placeholder resolution; `docs/reports/fabric-auth-rest-variants-source-smoke.json` proves bearer-token and API-key REST with the same secret path; `docs/reports/fabric-auth-rest-oauth-source-smoke.json` proves OAuth client-credentials REST; `docs/reports/fabric-auth-http-json-source-smoke.json` proves Basic-auth `http_json`; `docs/reports/fabric-auth-http-json-variants-source-smoke.json` proves bearer-token and API-key `http_json`; `docs/reports/fabric-auth-http-csv-variants-source-smoke.json` proves Basic, bearer-token and API-key `http_csv` Key Vault placeholder materialization; `docs/reports/fabric-auth-http-text-basic-source-smoke.json` proves endpoint-enforced Basic auth for `http_text`; `docs/reports/fabric-auth-http-text-bearer-source-smoke.json` proves endpoint-enforced bearer-scheme auth for `http_text`; `docs/reports/fabric-auth-http-text-api-key-source-smoke.json` proves endpoint-enforced API-key auth for `http_text`. OAuth is not currently part of the HTTP-file source vocabulary. |
| JDBC sources | `READ_WRITE_E2E` for Azure SQL/SQL Server and PostgreSQL Basic auth with Key Vault placeholders | Generated notebooks materialize SQL Server/Azure SQL and PostgreSQL sources through Spark JDBC and resolve JDBC URL/user/password through Azure Key Vault. `docs/reports/fabric-sqlserver-jdbc-source-smoke.json` proves the SQL Server JDBC source path in live Fabric; `docs/reports/fabric-postgres-jdbc-source-smoke.json` proves the PostgreSQL JDBC source path in live Fabric. Remaining JDBC dialects still need driver and network evidence. |
| Object storage and shortcuts | `READ_WRITE_E2E` for public/direct private Azure Blob CSV, external Azure Blob shortcut reads, external ADLS Gen2 shortcut reads, external Google Cloud Storage shortcut reads, external Amazon S3 shortcut reads, external S3-compatible shortcut reads and ADLS Gen2/Amazon S3/Google Cloud Storage Iceberg table shortcut reads | Generated notebooks materialize `azure_blob` CSV sources when `extensions.fabric.source_runtime_path` points to a Fabric Spark-readable object-store URI, Lakehouse file path or reviewed shortcut path. `docs/reports/fabric-azure-blob-source-smoke.json` proves the public Azure Blob CSV path in live Fabric; `docs/reports/fabric-private-azure-blob-source-smoke.json` proves direct private Azure Blob CSV using `extensions.fabric.storage_account_key_secret` and Key Vault runtime resolution; `docs/reports/fabric-onelake-shortcut-source-smoke.json` proves internal OneLake shortcut creation and Spark reads through a shortcut path; `docs/reports/fabric-external-azure-blob-shortcut-source-smoke.json` proves external Azure Blob shortcut creation through a Fabric AzureBlobs cloud connection and a contract-only CSV read through the shortcut path; `docs/reports/fabric-adls-shortcut-source-smoke.json` proves external ADLS Gen2 shortcut creation through a Fabric AzureDataLakeStorage cloud connection and a contract-only CSV read through the shortcut path; `docs/reports/fabric-gcs-shortcut-source-smoke.json` proves external Google Cloud Storage shortcut creation through a Fabric GoogleCloudStorage cloud connection and a contract-only CSV read through the shortcut path; `docs/reports/fabric-external-s3-shortcut-source-smoke.json` proves external Amazon S3 shortcut creation through a Fabric AmazonS3 cloud connection and a contract-only CSV read through the shortcut path; `docs/reports/fabric-s3-compatible-shortcut-source-smoke.json` proves external S3-compatible shortcut creation through a Fabric AmazonS3Compatible cloud connection and a contract-only CSV read through the shortcut path; `docs/reports/fabric-iceberg-table-shortcut-source-smoke.json` proves Amazon S3 Iceberg table shortcut creation under `Tables`, Fabric Iceberg-to-Delta virtualization and a contract-only `iceberg_table` read; `docs/reports/fabric-adls-iceberg-table-shortcut-source-smoke.json` proves the same `iceberg_table` contract path through an ADLS Gen2 Iceberg table shortcut; `docs/reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json` proves the same `iceberg_table` contract path through a Google Cloud Storage Iceberg table shortcut. Private-network shortcut variants, direct-catalog Iceberg variants and managed identity/OAuth object-storage access are excluded from stable-final unless separately certified. |
| Kafka-compatible stream sources | `READ_WRITE_E2E` for Confluent Cloud bounded replay, Confluent Cloud available-now catch-up and Azure Event Hubs Kafka-compatible available-now catch-up with Key Vault-backed SASL config | Generated notebooks materialize `kafka_bounded` sources through Spark's batch Kafka reader when finite offsets and a Key Vault-backed JAAS config are declared. Generated notebooks materialize `kafka_available_now` sources through Spark Structured Streaming with `trigger(availableNow=True)`, checkpointing and Delta read-back into the standard quality/write/evidence path. `docs/reports/fabric-confluent-kafka-bounded-source-smoke.json` proves Confluent Cloud bounded replay; `docs/reports/fabric-confluent-kafka-available-now-source-smoke.json` proves Confluent Cloud available-now catch-up; `docs/reports/fabric-eventhubs-kafka-available-now-source-smoke.json` proves Azure Event Hubs through its Kafka-compatible endpoint. Native `eventhubs_available_now` and Fabric Real-Time/Eventstream routing remain separate review boundaries. |
| Lineage | `READ_WRITE_E2E` | OpenLineage-compatible event rendering exists for Fabric Lakehouse runs. Generated notebooks write runtime lineage rows to `ctrl_ingestion_lineage`; the stable-surface suite probes lineage rows in live Fabric. |
| Operations metadata | `READ_WRITE_E2E` | Ownership, SLA, alert-intent and tag metadata render as JSON and Delta evidence insert SQL. Generated notebooks write declared operations metadata to `ctrl_ingestion_operations`; the stable-surface suite probes operations rows in live Fabric. Live Fabric monitoring integration is still pending. |
| Annotations | `READ_WRITE_E2E` for review evidence | Table/column description, alias, tag, PII and deprecation metadata render as review-only Fabric catalog plans and evidence SQL. Generated notebooks record validated review evidence to `ctrl_ingestion_annotations`, and the stable-surface suite probes those rows in live Fabric; apply mode is pending Fabric metadata API validation. |
| Access governance | `READ_WRITE_E2E` for review evidence; `READ_WRITE_SMOKE` for OneLake role apply/list/delete and row/column constraints; `SUPPORTED_LOCAL_TESTS` for native workspace role and sensitivity-label apply helpers | Grants, row filters and column masks render as review Fabric governance plans and access evidence SQL. Generated notebooks record validated review evidence to `ctrl_ingestion_access`, and the stable-surface suite probes those rows in live Fabric. Explicit `extensions.fabric.access_apply` entries can apply Fabric workspace role assignments, item sensitivity labels and OneLake data access roles when native Fabric IDs are supplied. `docs/reports/fabric-onelake-data-access-role-smoke.json` proves OneLake role create/list/delete for a Path/Action read policy with cleanup; `docs/reports/fabric-onelake-row-column-policy-smoke.json` proves row and column constraints against a Fabric-resolved Lakehouse table with cleanup. Arbitrary ContractForge row-filter functions are not auto-translated to OneLake SQL predicates; contracts must declare explicit Fabric-native OneLake policy payloads for apply mode. |
| CI/CD/deployment | `READ_WRITE_E2E` for deploy-only Notebook definition promotion and deployment-pipeline stage-to-stage Notebook promotion; `READ_WRITE_SMOKE` for deployment-pipeline lifecycle; `SUPPORTED_LOCAL_TESTS` for project manifests | `contractforge-fabric deploy-project` renders deterministic project deployment manifests and created the stable-surface project Notebook definitions in live Fabric without running notebooks. See `docs/reports/fabric-project-deploy-smoke.json`. `docs/reports/fabric-deployment-pipeline-read-probe.json` proves the tenant can read deployment pipelines, `docs/reports/fabric-deployment-pipeline-lifecycle-smoke.json` proves create/list/delete with cleanup, and `docs/reports/fabric-deployment-pipeline-stage-promotion-smoke.json` proves stage-to-stage Notebook content promotion with target item verification and cleanup. Git integration and Data Factory lifecycle promotion remain outside the notebook-first stable scope. |
| Stable-surface smoke | `READ_WRITE_E2E` | SQL-source stable-surface suite completed for append, overwrite, upsert, hash-diff, historical, snapshot, quality failure, strict schema failure and evidence probing across run, error, quality, schema, source metadata, lineage, explain, state, operations, annotations and access review tables. See `docs/reports/fabric-stable-surface-evidence.json`. |
| Real E2E evidence | `READ_WRITE_E2E` | Minimal SQL smoke, USGS REST/GeoJSON bronze-to-gold execution, public HTTP JSON/CSV/text source expansion, Lakehouse text file source expansion, Lakehouse ORC/Avro/XML file source expansion, internal OneLake shortcut source expansion, authenticated Basic REST source expansion, authenticated bearer/API-key REST source expansion, authenticated OAuth REST source expansion, authenticated Basic HTTP JSON source expansion, authenticated bearer/API-key HTTP JSON source expansion, authenticated Basic/bearer/API-key HTTP CSV source expansion, endpoint-enforced Basic HTTP text source expansion, endpoint-enforced bearer HTTP text source expansion, endpoint-enforced API-key HTTP text source expansion, SQL Server JDBC source expansion, PostgreSQL JDBC source expansion, public Azure Blob source expansion, direct private Azure Blob source expansion, external Azure Blob shortcut source expansion, external ADLS Gen2 shortcut source expansion, external Google Cloud Storage shortcut source expansion, external Amazon S3 shortcut source expansion, external S3-compatible shortcut source expansion, Amazon S3 Iceberg table shortcut source expansion, ADLS Gen2 Iceberg table shortcut source expansion, Google Cloud Storage Iceberg table shortcut source expansion, bounded Confluent Kafka source expansion, Confluent Kafka available-now source expansion, Event Hubs Kafka-compatible available-now source expansion and stable-surface SQL-source execution succeeded after Spark pool sizing was corrected. See `docs/reports/fabric-usgs-rest-e2e-smoke.json`, `docs/reports/fabric-http-json-source-smoke.json`, `docs/reports/fabric-http-csv-source-smoke.json`, `docs/reports/fabric-http-text-source-smoke.json`, `docs/reports/fabric-lakehouse-text-source-smoke.json`, `docs/reports/fabric-lakehouse-file-formats-source-smoke.json`, `docs/reports/fabric-onelake-shortcut-source-smoke.json`, `docs/reports/fabric-auth-rest-source-smoke.json`, `docs/reports/fabric-auth-rest-variants-source-smoke.json`, `docs/reports/fabric-auth-rest-oauth-source-smoke.json`, `docs/reports/fabric-auth-http-json-source-smoke.json`, `docs/reports/fabric-auth-http-json-variants-source-smoke.json`, `docs/reports/fabric-auth-http-csv-variants-source-smoke.json`, `docs/reports/fabric-auth-http-text-basic-source-smoke.json`, `docs/reports/fabric-auth-http-text-bearer-source-smoke.json`, `docs/reports/fabric-auth-http-text-api-key-source-smoke.json`, `docs/reports/fabric-sqlserver-jdbc-source-smoke.json`, `docs/reports/fabric-postgres-jdbc-source-smoke.json`, `docs/reports/fabric-azure-blob-source-smoke.json`, `docs/reports/fabric-private-azure-blob-source-smoke.json`, `docs/reports/fabric-external-azure-blob-shortcut-source-smoke.json`, `docs/reports/fabric-adls-shortcut-source-smoke.json`, `docs/reports/fabric-gcs-shortcut-source-smoke.json`, `docs/reports/fabric-external-s3-shortcut-source-smoke.json`, `docs/reports/fabric-s3-compatible-shortcut-source-smoke.json`, `docs/reports/fabric-iceberg-table-shortcut-source-smoke.json`, `docs/reports/fabric-adls-iceberg-table-shortcut-source-smoke.json`, `docs/reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json`, `docs/reports/fabric-confluent-kafka-bounded-source-smoke.json`, `docs/reports/fabric-confluent-kafka-available-now-source-smoke.json`, `docs/reports/fabric-eventhubs-kafka-available-now-source-smoke.json` and `docs/reports/fabric-stable-surface-evidence.json`. |

The adapter can currently validate contract intent, produce review artifacts,
deploy generated notebooks and submit smoke runs. It has live runtime evidence
for the documented notebook-first subset, but it cannot yet claim adapter-wide
source, governance-apply or deployment parity with Databricks, AWS or Snowflake.

## Parity Baseline

| Adapter | Maturity baseline | E2E status |
| --- | --- | --- |
| Databricks | Reference/stable surface | Real bronze-to-gold runs validated. |
| AWS | Stable supported surface | Real Glue/Iceberg runs validated for the documented surface. |
| Snowflake | Stable supported surface | Real SQL/Snowpark runs validated for the documented surface. |
| Fabric | Initial E2E adapter surface with stable-surface smoke evidence | Planning/rendering plus Notebook deploy/run smoke workflow; minimal SQL smoke, one public REST/GeoJSON bronze-to-gold chain and one SQL-source stable-surface suite succeeded after Spark pool sizing. Broader source/governance/deployment parity is still pending. |

Fabric should only be moved to stable status after the same contract set can
run bronze to gold in Fabric repeatedly and the remaining stable gates are
closed without workaround code.

## Contract Reuse Goal

Fabric parity means the same ContractForge contracts should remain portable.
Expected differences should be limited to native runtime bindings:

| Contract area | Reuse expectation |
| --- | --- |
| Source intent | Same `source.type`, read shape and incremental intent where the runtime can preserve semantics. |
| Target intent | Same logical layer/table intent, with Fabric environment resolving workspace, lakehouse, schema and table bindings. |
| Write mode | Same public aliases: `append`, `overwrite`, `upsert`, `hash_diff_upsert`, `historical`, `snapshot_reconcile_soft_delete`. |
| Shape and transform | Same semantic declarations; Fabric implementation may choose notebook/Spark, SQL endpoint or pipeline execution. |
| Quality | Same rule declarations and fail/quarantine intent. |
| Evidence | Same control/evidence semantics, stored in Fabric Lakehouse Delta tables. |
| Access | Same contract vocabulary, with Fabric security mappings reviewed before apply support is claimed. |
| Operations | Same ownership, SLA and run metadata, with Fabric monitor/alert integration added later. |

## Capability Matrix

| Capability | Fabric v0 declaration | Stable target |
| --- | --- | --- |
| `append` | `SUPPORTED` | Lakehouse Delta append with evidence. |
| `overwrite` | `SUPPORTED` | Deterministic target/scope replacement with evidence. |
| `upsert` | `SUPPORTED` | Lakehouse or Warehouse merge with validated key semantics. |
| `hash_diff_upsert` | `READ_WRITE_E2E` | Deterministic row hash and Delta merge rendering passed seed/no-op/change waves in the stable-surface suite. |
| `historical` | `READ_WRITE_E2E` | SCD2 validity/current-row Delta MERGE rendering passed seed/change waves in the stable-surface suite. |
| `snapshot_reconcile_soft_delete` | `READ_WRITE_E2E` | Complete-source snapshot reconciliation and soft-delete Delta MERGE rendering passed seed/delete waves in the stable-surface suite. |
| Schema evolution | `SUPPORTED_LOCAL_TESTS` | Generated notebooks enforce strict/additive/permissive policy when target schema lookup succeeds; real Fabric E2E validation is still pending. |
| Row filters | `REVIEW_REQUIRED` | Fabric security model mapped without weakening contract intent. |
| Column masks | `REVIEW_REQUIRED` | Fabric security/sensitivity model mapped without weakening contract intent. |
| Available-now streaming | `REVIEW_REQUIRED` | Bounded replay/checkpoint behavior proven with evidence. |
| Required columns quality | `SUPPORTED` | Runtime schema gate. |
| Unique key quality | `SUPPORTED` | Runtime duplicate-key gate. |
| Max null ratio quality | `SUPPORTED` | Runtime aggregate quality gate. |
| Expression quality | `SUPPORTED` | SQL/Spark expression dialect review needed before stable claim. |
| Shape | `SUPPORTED_LOCAL_TESTS` | Portable Spark shape rendering exists for parse_json, columns and flatten. Array cardinality changes and zip-array semantics remain review-only until real Fabric E2E validation. |
| Transform | `SUPPORTED_LOCAL_TESTS` | Portable Spark transform rendering exists for cast, standardize, derive, composite keys and deterministic deduplicate. Real parity tests still need capacity-stable execution. |
| Evidence store | `fabric_lakehouse_delta_tables` | Delta DDL rendering exists; generated notebooks render runtime evidence, state and opt-in lock writes. |

Because full E2E parity is not validated, declared `SUPPORTED` means
"plan/render support exists and the smoke path can generate runnable notebook
artifacts", not "runtime execution has been proven for the full contract set".

## Runtime Architecture Decision

The recommended first runtime path is notebook-first Lakehouse execution:

1. Render a Fabric notebook draft from the contracts.
2. Use OneLake `Files` paths for bounded file inputs.
3. Write bronze/silver/gold outputs as Delta tables under the Fabric Lakehouse
   `Tables` area.
4. Write evidence/control records as Delta tables in the same or a dedicated
   evidence Lakehouse.
5. Use SQL endpoint or Warehouse reads for validation and reporting, not as the
   first write engine.
6. Add Data Factory pipelines later as orchestration wrappers around generated
   notebook runs or as a separate low-code/native ingestion path.

This choice is pragmatic: the official docs show Lakehouse files-to-Delta table
workflows in Fabric notebooks, and Delta Lake is the shared Lakehouse storage
format. Data Factory remains important for orchestration and connector-heavy
sources, but it adds definition, credential, gateway and CI/CD concerns before
the core bronze-to-gold writer is proven.

## Automation Requirements

The Fabric runtime client needs these adapter-owned components before any real
E2E claim:

| Component | Requirement |
| --- | --- |
| Workspace resolver | Resolve by workspace ID first, then name only when unique. |
| Item resolver | Resolve/create Lakehouse, Notebook, Data Pipeline and optional Warehouse items. |
| REST authentication | Use Microsoft Entra authentication with explicit Fabric scopes and no embedded secrets in contracts. |
| Permission preflight | Check or clearly fail on missing contributor/read/write/execute permissions. |
| Capacity preflight | Fail clearly if the workspace cannot create required Fabric items because capacity is unsupported or missing. |
| Spark pool sizing | Detect small-capacity/default-pool mismatch and recommend or apply a single-node Small pool for smoke validation. |
| Job-instance visibility | List recent Notebook job instances and warn when active jobs can consume Spark capacity before a smoke run. |
| LRO polling | Poll operation URLs and honor `Retry-After` for 202 responses. |
| Throttling | Treat `429` as retryable with server-provided backoff. |
| Definition handling | Notebook definitions are read before update; differing existing notebooks require explicit `update_existing=True`, and unreadable current definitions block updates. |
| Artifact fingerprinting | Generated notebook definitions are fingerprinted so unchanged deploys are idempotent; pipeline fingerprinting remains future work. |
| Evidence bootstrap | Generated notebooks create evidence/state tables before the first contract run; real Fabric execution still needs capacity-stable validation. |

## Source Support Matrix

The current source catalog is produced by `list_fabric_source_support()`.

| Source family | Source types | Current status | Native Fabric mapping |
| --- | --- | --- | --- |
| Catalog/table v1 candidates | `table`, `delta_table`, `view`, `sql` | `SUPPORTED` in planning and notebook rendering | Fabric Lakehouse/Warehouse table or SQL endpoint. |
| Catalog/table review-only | `iceberg_table` | `REVIEW_REQUIRED`; ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcuts have live `READ_WRITE_E2E` evidence | Renderable when Fabric exposes the Iceberg folder as a Lakehouse table shortcut under `Tables`; direct Iceberg catalog reads still need separate proof. |
| Lakehouse file v1 candidates | `csv`, `json`, `jsonl`, `ndjson`, `parquet`, `delta`, `text`, `orc`, `avro`, `xml` | `SUPPORTED` in planning and notebook rendering; `text`, `orc`, `avro` and `xml` have live source-expansion evidence | OneLake Files path read. |
| Object storage | `s3`, `adls`, `azure_blob`, `gcs`, `blob`, `object_storage` | `REVIEW_REQUIRED`; public/direct private Azure Blob CSV, internal OneLake shortcut reads, external Azure Blob shortcut reads, external ADLS Gen2 shortcut reads, external Google Cloud Storage shortcut reads, external Amazon S3 shortcut reads, external S3-compatible shortcut reads and ADLS Gen2/Amazon S3/Google Cloud Storage Iceberg table shortcut reads have live `READ_WRITE_E2E` evidence for the Fabric runtime-binding path | OneLake shortcut, staged Lakehouse file path or Fabric Spark-readable object-store URI declared through `extensions.fabric.source_runtime_path`; direct private Azure Blob can declare `extensions.fabric.storage_account_key_secret`; external Azure Blob, ADLS Gen2, Google Cloud Storage, Amazon S3, S3-compatible and Iceberg table shortcuts for ADLS Gen2/Amazon S3/Google Cloud Storage can be created by `fabric_setup.shortcuts` with Fabric cloud connection IDs. |
| Incremental files | `incremental_files` | `REVIEW_REQUIRED` | Fabric Data Factory incremental pipeline or notebook checkpoint. |
| HTTP files | `http_file`, `http_csv`, `http_json`, `http_text` | `SUPPORTED_WITH_WARNINGS` for public/no-auth bounded contracts; `REVIEW_REQUIRED` but notebook-renderable for Key Vault placeholder auth; otherwise `REVIEW_REQUIRED` | Fabric notebook core HTTP fetch, Key Vault-backed notebook fetch or Data Factory web activity. |
| JDBC validated | `sqlserver`/SQL Server JDBC and `postgres`/PostgreSQL JDBC | `REVIEW_REQUIRED` but notebook-renderable for Basic auth with Key Vault placeholders; live `READ_WRITE_E2E` evidence exists | Fabric notebook Spark JDBC read. |
| JDBC review-only | `mysql`, `mariadb`, `oracle`, `redshift`, `db2`, `snowflake_jdbc`, `bigquery_jdbc` and generic `jdbc` without a validated URL family | `REVIEW_REQUIRED` | Fabric Data Factory pipeline or notebook JDBC read after driver/network validation. |
| Streams | `kafka_bounded`, `eventhubs_bounded`, `kafka_available_now`, `eventhubs_available_now` | `READ_WRITE_E2E` for Confluent Cloud `kafka_bounded`, Confluent Cloud `kafka_available_now` and Azure Event Hubs through Kafka-compatible `kafka_available_now` with Key Vault-backed SASL config; native `eventhubs_available_now` and Fabric Real-Time/Eventstream shapes remain `REVIEW_REQUIRED` | Fabric notebook Spark Kafka batch replay for validated bounded Kafka; Spark Structured Streaming `availableNow` for validated Kafka-compatible catch-up; Fabric Real-Time Intelligence, Eventstream or native Event Hubs connector paths for remaining stream shapes. |
| Delta Sharing | `delta_share` | `REVIEW_REQUIRED` | Delta Sharing client materialized into OneLake. |
| REST API | `rest_api` | `SUPPORTED_WITH_WARNINGS` for public/no-auth bounded contracts; `REVIEW_REQUIRED` but notebook-renderable for Key Vault placeholder auth; otherwise `REVIEW_REQUIRED` | Fabric notebook core REST fetch, Key Vault-backed notebook fetch or Data Factory REST copy. |
| Native passthrough | `native_passthrough` | `REVIEW_REQUIRED` | Fabric native connector, shortcut or Data Factory activity. |

The first E2E parity candidate should use a `parquet`, `json`, `jsonl`, `csv`
or `delta` Lakehouse file source, a simple Lakehouse table source, or a
public/no-auth bounded HTTP/REST source or the validated authenticated REST
Basic/bearer/API-key/OAuth REST, public `http_json`/`http_csv`/`http_text` and Basic/bearer/API-key `http_json` Key Vault placeholder paths. Other authenticated HTTP variants
can render review-required notebooks when credentials use
`{{ secret:scope/key }}` and the environment maps the scope to Azure Key Vault,
but live E2E evidence is still required before the full authenticated HTTP/REST
family passes F11. Lakehouse `text`, `orc`, `avro` and `xml` files, internal OneLake shortcut reads, external Azure Blob shortcut reads, external ADLS Gen2 shortcut reads, external Google Cloud Storage shortcut reads, external Amazon S3 shortcut reads, external S3-compatible shortcut reads, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads, SQL Server JDBC, PostgreSQL JDBC, bounded Confluent Kafka, Confluent Kafka available-now and Event Hubs Kafka-compatible available-now are validated through the notebook path.
Private-network shortcut variants, managed identity/OAuth
object-storage access, Delta Sharing, direct-catalog Iceberg variants and
native Event Hubs/Fabric Real-Time stream modes remain review-required until their Fabric runtime path is
explicit and tested.

For renderable v1 candidates, the adapter now emits a `.fabric.notebook.py`
draft artifact and a `.fabric.notebook.definition.json` draft. The definition
uses the public Notebook `fabricGitSource` shape with `notebook-content.py`,
`.platform` and `InlineBase64` parts. These artifacts are deterministic and
reviewable, but they are still not submitted to Fabric and are not runtime
evidence.

For every contract source, the adapter also emits `.fabric.source_review.json`
and `.fabric.source_review.md`. These artifacts include the redacted source
body, the selected Fabric runtime path, review prerequisites and the gates that
must pass before a review-only source can be treated as stable. They are
review evidence only; they do not make unvalidated JDBC, object-storage
families beyond the validated public/direct private Azure Blob paths or streams
executable. Authenticated HTTP/REST is executable only for bounded
notebook-rendered Key Vault placeholder paths; REST Basic/bearer/API-key/OAuth
and `http_json` Basic/bearer/API-key have live evidence, while remaining
OAuth for HTTP-file sources still needs source vocabulary and source-specific
evidence before it can be claimed stable.

## Stable Maturity Gates

Fabric should not be called stable until these gates pass with real Fabric
workspace evidence.

| Gate | Required outcome |
| --- | --- |
| F1 Package | Independent wheel installs with `contractforge-core` and exposes stable public API. |
| F2 Environment binding | Workspace, lakehouse, warehouse, artifact and evidence bindings resolve from environment YAML. |
| F3 Runtime architecture | Choose and document the first supported execution path: notebook-first, Data Factory-first or hybrid. |
| F4 Bronze-to-gold REST/GeoJSON E2E | Same contracts produce bronze, silver and gold outputs in Fabric with expected row-count constraints. First live pass completed June 11, 2026. |
| F5 Evidence tables | Fabric Lakehouse evidence tables capture run, quality, schema, lineage, source metadata, explain, state, operations, annotations, access review and error records. Expanded stable-surface control-table probe passed June 11, 2026. |
| F6 Quality runtime | Required columns, not-null, unique key, accepted values, row count and max-null-ratio gates execute. First stable-surface quality and failure-evidence probes passed June 11, 2026. |
| F7 Write modes | `append`, `overwrite` and `upsert` execute without workaround code. First stable-surface pass completed June 11, 2026. |
| F8 Hash diff | `hash_diff_upsert` produces the same current-state output as the validated adapters. First stable-surface seed/no-op/change pass completed June 11, 2026. |
| F9 Historical decision | `historical` is included in the notebook-first stable-surface scope and passed seed/change smoke on June 11, 2026. |
| F10 Snapshot decision | `snapshot_reconcile_soft_delete` is included in the notebook-first stable-surface scope and passed seed/delete smoke on June 11, 2026. |
| F11 Source expansion | PASS. Public/no-auth `rest_api`, public/no-auth `http_json`/`http_csv`/`http_text`, Lakehouse `text`/`orc`/`avro`/`xml`, internal OneLake shortcut reads, external Azure Blob shortcut reads, external ADLS Gen2 shortcut reads, external Google Cloud Storage shortcut reads, external Amazon S3 shortcut reads, external S3-compatible shortcut reads, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads, authenticated REST Basic/bearer/API-key/OAuth, authenticated `http_json` Basic/bearer/API-key, authenticated `http_csv` Basic/bearer/API-key, endpoint-enforced `http_text` Basic/bearer/API-key auth, SQL Server JDBC, PostgreSQL JDBC, public Azure Blob CSV, direct private Azure Blob CSV with a Key Vault-backed storage account key, bounded Confluent Kafka, Confluent Kafka available-now and Event Hubs Kafka-compatible available-now have live Fabric E2E evidence. Private-network shortcut variants, managed identity/OAuth object-storage access, native Fabric Real-Time/Eventstream providers, Delta Sharing, direct-catalog Iceberg variants, additional JDBC dialects and OAuth HTTP-file sources are excluded from the notebook-first stable-final claim through `docs/reports/fabric-source-expansion-stable-scope-decision.json`. |
| F12 Governance | PASS. Access review evidence is live-validated. Explicit Fabric workspace role assignment and sensitivity-label apply helpers are implemented and locally tested. OneLake data access role create/list/delete is live-validated through `docs/reports/fabric-onelake-data-access-role-smoke.json`, and explicit row/column constraints are live-validated through `docs/reports/fabric-onelake-row-column-policy-smoke.json`. Arbitrary ContractForge row-filter function translation remains explicit-review only, not a silent adapter behavior. |
| F13 Deployment | PASS. `deploy-project` renders deterministic project deployment manifests and can deploy generated Notebook definitions without running them. Deployment-pipeline read and create/list/delete lifecycle probes succeeded live with cleanup. Stage-to-stage Notebook content promotion succeeded live with target item verification and cleanup through `docs/reports/fabric-deployment-pipeline-stage-promotion-smoke.json`. Fabric Git integration and Data Factory promotion remain outside the notebook-first stable scope. |
| F14 Contract parity report | PASS. `docs/reports/fabric-platform-parity.json` captures the shared machine-readable parity report, and `tools.platform_parity.report` now evaluates Databricks, AWS, Snowflake and Fabric together. |
| F15 REST hardening | LRO polling, throttling, permission/capacity preflight and idempotent item updates are tested. |
| F16 CI/CD model | Document whether the adapter owns REST deployment directly, Fabric Git integration, deployment pipelines or a supported combination. |

## Recommended Implementation Order

1. Keep the current planning/review adapter surface as the contract boundary.
2. Extend the Fabric REST client module from local LRO/throttling tests and
   read-only workspace discovery to item lookup and preflight diagnostics.
3. Keep smoke execution, write-mode rendering, quality checks, lineage rendering,
   operations metadata, annotations, access governance and operational state helpers in dedicated
   `smoke`, `write_modes`, `quality`, `lineage`, `operations`, `annotations`
   `access` and `state` packages as runtime coverage expands.
4. Add a Fabric runtime module that executes the smallest supported path:
   parquet or JSON file source, bronze target, evidence write.
5. Extend to silver transform/quality and gold aggregation using the same
   contract set used for Databricks/AWS/Snowflake parity.
6. Add a real Fabric smoke command that fails if any artifact is manually
   patched outside the contracts.
7. Add Data Factory pipeline rendering/deployment after notebook-first E2E is
   stable, unless a connector-specific source requires pipeline-first runtime.
8. Only after F4-F6 pass, update public docs/site with validated status.

## Local Validation Commands

Current local checks:

```bash
uv run pytest tests/test_fabric_adapter.py tests/test_adapter_independence.py
uv run pytest tests/test_fabric_evidence_ddl.py
uv build adapters/fabric
```

Current behavior inspection:

```powershell
$env:PYTHONPATH='src;adapters/fabric/src'
uv run python -m contractforge_fabric.cli sources
uv run python -m contractforge_fabric.cli stabilization-report
uv run python -m contractforge_fabric.cli preflight --environment .tmp/fabric.env.yaml --require-lakehouse
uv run python -m contractforge_fabric.cli smoke .tmp/fabric-smoke.yaml --environment .tmp/fabric.env.yaml --no-wait
```

Expected result today:

- Fabric tests pass locally.
- Fabric wheel builds.
- Source-support catalog renders.
- `stabilization-report` returns `stable_final: true` for the documented
  notebook-first stable surface. Review-only source families, broader
  Fabric/Purview metadata behavior and Data Factory/Git promotion remain
  excluded unless separately certified.
- Runtime preflight and Notebook smoke commands print JSON evidence.
- Spark settings preflight reports FTL4/default-pool compatibility and warns on Starter Pool Medium.
- Fabric render bundles include redacted source review artifacts with
  source-specific prerequisites and graduation gates.
- Fabric Notebook deployment reads existing definitions and skips unchanged updates by fingerprint.
- Fabric Notebook deployment blocks differing or unreadable updates unless the update is explicit and the current definition can be read.
- Fabric Notebook deployment follows async get-definition operations and reads `/operations/{id}/result`.
- Fabric REST primitives can list capacities, list/create Spark pools and patch Spark settings.
- Fabric REST primitives can list/apply workspace role assignments, bulk-set item sensitivity labels, create/list/delete OneLake data access roles, list deployment pipelines and stages, connect workspace Git metadata and submit deployment-pipeline deploy requests.
- Fabric access planning can execute explicit `extensions.fabric.access_apply` workspace role assignments, item sensitivity labels and OneLake data access roles when contracts provide native Fabric IDs.
- Fabric project deployment can render a deterministic `deployment/fabric_project_deployment_manifest.json` and deploy generated Notebook definitions without running them.
- Fabric SQL smoke succeeded after the workspace default Spark pool was changed from Starter Pool Medium to a single-node Small custom pool.
- Fabric review bundles render evidence and state table Delta DDL.
- Fabric generated notebooks render idempotent evidence/state table bootstrap before lock acquisition.
- Fabric generated notebooks render run/error evidence writes.
- Fabric generated notebooks render source metadata evidence writes.
- Fabric generated notebooks render pre-write schema-policy validation and observed-schema evidence writes.
- Fabric generated notebooks render best-effort Spark explain evidence writes.
- Fabric generated notebooks render deterministic `hash_diff_upsert` row-hash merge writes.
- Fabric generated notebooks render `historical` SCD2 expire-and-insert merge writes.
- Fabric generated notebooks render `snapshot_reconcile_soft_delete` complete-source soft-delete merge writes.
- Fabric generated notebooks render append-only successful-run state updates.
- Fabric generated notebooks render opt-in Delta lock acquire/release SQL for `extensions.fabric.lock_enabled`.
- Fabric generated notebooks render portable shape blocks before transform, quality, schema policy and writes.
- Fabric generated notebooks render portable transform blocks before quality, schema policy and writes.
- Fabric generated notebooks render public/no-auth bounded HTTP/REST source reads through shared core readers.
- Fabric generated notebooks render authenticated bounded HTTP/REST source reads through shared core readers when credentials use `{{ secret:scope/key }}` and the Fabric environment maps the scope to Azure Key Vault.
- Fabric Lakehouse ORC, Avro and XML file source expansion completed live with contract-only source reads and a control-table evidence probe.
- Fabric internal OneLake shortcut source expansion completed live with Fabric REST shortcut creation, contract-only ORC read through the shortcut path and a control-table evidence probe.
- Fabric authenticated Basic REST source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric authenticated bearer/API-key REST source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric authenticated OAuth REST source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric authenticated Basic HTTP JSON source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric authenticated bearer/API-key HTTP JSON source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric authenticated Basic/bearer/API-key HTTP CSV source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric endpoint-enforced Basic HTTP text source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric endpoint-enforced bearer HTTP text source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric endpoint-enforced API-key HTTP text source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric SQL Server JDBC source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric PostgreSQL JDBC source expansion completed live with Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric Azure Blob source expansion completed live with a public object-storage CSV fixture, `extensions.fabric.source_runtime_path` and a contract-only evidence probe.
- Fabric private Azure Blob source expansion completed live with a private CSV fixture, `extensions.fabric.source_runtime_path`, `extensions.fabric.storage_account_key_secret`, Azure Key Vault runtime resolution and a contract-only evidence probe.
- Fabric external Azure Blob shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric AzureBlobs cloud connection, native shortcut creation and a contract-only evidence probe.
- Fabric ADLS Gen2 shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric AzureDataLakeStorage cloud connection, native shortcut creation and a contract-only evidence probe.
- Fabric GCS shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric GoogleCloudStorage cloud connection, native shortcut creation and a contract-only evidence probe.
- Fabric external Amazon S3 shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric AmazonS3 cloud connection, native shortcut creation and a contract-only evidence probe.
- Fabric S3-compatible shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric AmazonS3Compatible cloud connection, native shortcut creation and a contract-only evidence probe.
- Fabric Amazon S3 Iceberg table shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric AmazonS3 cloud connection, native Tables shortcut creation, Fabric Iceberg-to-Delta virtualization and a contract-only evidence probe.
- Fabric ADLS Gen2 Iceberg table shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric AzureDataLakeStorage cloud connection, native Tables shortcut creation, Fabric Iceberg-to-Delta virtualization and a contract-only evidence probe.
- Fabric GCS Iceberg table shortcut source expansion completed live with `fabric_setup.shortcuts`, a Fabric GoogleCloudStorage cloud connection, native Tables shortcut creation, Fabric Iceberg-to-Delta virtualization and a contract-only evidence probe.
- Fabric Confluent Kafka available-now source expansion completed live with Spark Structured Streaming `trigger(availableNow=True)`, checkpointing, Delta read-back, Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric Event Hubs Kafka-compatible available-now source expansion completed live with Spark Structured Streaming `trigger(availableNow=True)`, checkpointing, Delta read-back, Key Vault placeholder resolution and a contract-only evidence probe.
- Fabric notebooks render core Spark quality gates before writes.
- Fabric notebooks render per-rule quality evidence writes.
- Fabric notebooks render failed-row quarantine evidence for row-predicate quarantine rules.
- Fabric can render OpenLineage-compatible events and notebook runtime lineage evidence.
- Fabric can render operations metadata for evidence/control tables.
- Fabric generated notebooks render runtime operations metadata evidence writes.
- Fabric can render review-only annotation plans and annotation evidence SQL.
- Fabric can render access governance plans and access evidence SQL, and can apply explicit workspace role assignments, sensitivity labels and OneLake data access roles when native Fabric IDs are declared.
- Fabric generated notebooks render validated annotation/access review evidence writes; explicit Fabric-native OneLake row/column policies are live-certified, while arbitrary row-filter function translation remains review-only.
- Real Notebook execution can still be blocked by Fabric capacity throttling if Spark pool sizing or queued execution is not configured.
