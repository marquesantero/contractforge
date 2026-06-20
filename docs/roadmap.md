# Roadmap

This roadmap documents adapter maturity and release criteria. It is intentionally conservative: ContractForge should prove portability with capabilities and evidence, not with marketing claims.

## Product Positioning

ContractForge is a multi-runtime contract-first ingestion platform.

Tagline:

```text
Define ingestion intent once. Run it natively anywhere, or know exactly why you can't.
```

The "why you can't" is part of the product. A `REVIEW_REQUIRED` or `UNSUPPORTED` plan is a correct outcome when the target platform cannot safely preserve the declared contract.

## Current Status

| Component | Status | Scope |
| --- | --- | --- |
| `contractforge-core` | Active | Platform-neutral contracts, semantic models, capability matching, abstract planning, source taxonomy, schema policy, quality/evidence models and adapter protocol. |
| `contractforge-databricks` | Reference adapter | Databricks-native rendering and runtime helpers for Delta, Unity Catalog, Auto Loader, Lakeflow planning, Asset Bundles, governance, quality, evidence/control tables, lineage, cost and dashboards. |
| `contractforge-aws` | Stable supported surface | AWS Glue Spark/Iceberg planning, rendering, deployment, runtime execution, evidence audit, quality/quarantine, source support, cost reconciliation, annotations, operations, Lake Formation review/apply helpers, consumer-engine validation, reference hash-diff benchmarking and orchestration are validated for the documented `aws_glue_iceberg` surface. historical and snapshot soft delete are excluded from stable-final; generic streaming-provider claims and contract-specific governance/SLA claims remain explicit review/final-certification boundaries. |
| `contractforge-fabric` | Stable supported surface | Fabric REST preflight, generated Notebook deployment/run, deploy-only project manifests, deployment pipeline stage-to-stage Notebook promotion, Lakehouse Delta writes, Lakehouse text/ORC/Avro/XML files, internal OneLake shortcut reads, public/no-auth REST, public/no-auth HTTP JSON/CSV/text, authenticated REST Basic/bearer/API-key/OAuth, authenticated HTTP JSON Basic/bearer/API-key, authenticated HTTP CSV Basic/bearer/API-key, endpoint-enforced HTTP text Basic/bearer/API-key, SQL Server JDBC, PostgreSQL JDBC, public and direct private Azure Blob CSV object storage, external Azure Blob, ADLS Gen2, Google Cloud Storage, Amazon S3 and S3-compatible shortcut reads, ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads, bounded Confluent Kafka replay, Confluent Kafka available-now catch-up, Event Hubs Kafka-compatible available-now catch-up, core write modes, quality, schema, lineage, state, control-table evidence, explicit Fabric workspace role assignment, sensitivity-label and OneLake data access role apply helpers including row/column policy apply are validated for the documented `fabric_lakehouse` surface. Private-network shortcuts, managed identity/OAuth object-storage access, Delta Sharing, direct-catalog Iceberg, native Fabric Real-Time/Eventstream and Data Factory/Git promotion are excluded from stable-final unless separately certified. |
| `contractforge-snowflake` | Stable supported surface | SQL warehouse runtime, hosted Snowpark procedure library runner with staged ZIP imports, live task graph execution, table/SQL/bounded REST/staged-file sources, write modes, reference hash-diff benchmarking, quality, schema policy, governance, evidence/control tables, lineage and cost reconciliation are validated for the documented `snowflake_sql_warehouse` surface. historical/snapshot soft delete are excluded from stable-final; continuous ingestion and account-feature-dependent access policy validation remain explicit review/final-certification boundaries. |
| `contractforge-gcp` | Stable supported surface | BigQuery table/view/SQL sources, GCS CSV/NDJSON/Parquet/Avro/ORC load jobs, public/no-auth bounded REST/HTTP JSON/CSV materialization and declared `http_file` Avro/ORC/Parquet materialization through core readers plus BigQuery local load jobs, authenticated REST/HTTP Secret Manager review/runtime resolution for `{{ secret:scope/key }}` placeholders, registered BigLake Iceberg table reads, raw Iceberg BigLake registration command/readback, append/overwrite/explicit-column upsert, advanced write-mode review artifacts with accepted cross-adapter `hash_diff_upsert` production parity, SQL quality checks, run/quality/schema/annotation/governance/failed-run evidence DDL, bronze-to-gold execution, row access policies, direct column data masking, policy-tag column access, BigQuery descriptions, schema-policy planning artifacts plus validated table/SQL/GCS-source runtime enforcement, Dataplex data-quality create and execution/readback planning artifacts, explicit Dataplex lineage/aspect execution/readback command surface, governance ledger/reconciliation planning artifacts, non-mutating governance reconciliation readback, governance evidence write/readback for declared governance intent and a certified Google Workflows deployment runner are validated for the documented `gcp_bigquery` surface. Workflows evidence covers deploy/execute, command-path readback, runner-side evidence, quality failed-row semantics, execution-scoped evidence ids, schema-evidence persistence, workflow cleanup, write-failure evidence, target/evidence cleanup/reset and repeated full-project rerun execution/readback. Streaming, historical/snapshot advanced write modes, automatic BigQuery type widening/mutation, non-Workflows deployment runners, automatic native Dataplex lineage/aspect emission during every contract run, direct raw Iceberg path execution without registration, JDBC/Delta Sharing, inline authenticated REST/HTTP credentials, governance auto-repair/delete and overwrite-retention certification are excluded from stable-final unless separately certified. |

## Adapter Maturity Levels

| Level | Meaning |
| --- | --- |
| `planned` | Architecture and expected native mappings are documented, but no public package exists. |
| `alpha` | Adapter package exists and can plan/render a narrow set of contracts. Not production-ready. |
| `beta` | Adapter supports core contract sections, evidence mapping and representative runtime tests. |
| `reference` | Adapter proves the architecture and has broad parity with an existing production framework or real platform behavior. |
| `production` | Adapter has documented compatibility, release discipline, runtime validation and operational evidence coverage. |

## Second Adapter Criteria

The next public adapter should be small but honest. It should not be a stub that always returns `REVIEW_REQUIRED`.

Minimum useful scope:

1. Package builds its own wheel.
2. Imports `contractforge-core`; core does not import it.
3. Declares conservative `PlatformCapabilities`.
4. Supports planning and rendering for:
   - `append`;
   - `overwrite`;
   - `upsert` or explicit `REVIEW_REQUIRED`;
   - core evidence DDL/layout or documented audit artifacts.
5. Supports at least these contract sections:
   - ingestion;
   - operations;
   - environment.
6. Documents source support and unsupported semantics.
7. Has tests proving no silent write-mode downgrade.

## Release Signals

Before calling the architecture `1.0`:

- at least one non-Databricks adapter should have a stable supported surface with repeated runtime validation; AWS satisfies this for `aws_glue_iceberg`, Snowflake satisfies this for `snowflake_sql_warehouse`, Fabric satisfies this for the documented notebook-first `fabric_lakehouse` surface, and GCP satisfies this for the documented BigQuery batch `gcp_bigquery` surface;
- AWS and Snowflake final-certification work should follow the [AWS and Snowflake production maturity plan](specs/aws-snowflake-production-maturity-plan.md);
- public API stability rules should be documented;
- package versions should have an explicit compatibility policy;
- docs should include an end-to-end multi-platform case study and keep the USGS GeoJSON medallion example current across stable adapters;
- CI should build the core wheel and every adapter wheel.

## Near-Term Documentation Work

- Expand the USGS GeoJSON medallion case study with screenshots or query outputs from Databricks, AWS, Snowflake, Fabric and GCP evidence tables.
- Expand Fabric beyond the stable notebook-first surface only when there is separate evidence for private-network shortcuts, managed identity/OAuth object-storage access, Delta Sharing, direct-catalog Iceberg variants or native Fabric Real-Time/Eventstream paths without weakening contract semantics.
- Add adapter-specific capability matrices as adapters mature.

