# ContractForge Documentation

This directory contains the versioned documentation for ContractForge and its adapter architecture.

ContractForge is a multi-runtime contract-first ingestion platform. The core package defines the semantic layer, and adapters implement platform-native rendering, execution and evidence persistence.

## Start Here

- [Quick start](quickstart.md): validate the core installation, plan a contract and render Databricks artifacts.
- [Usage guide](usage-guide.md): practical workflow for split contracts, planning, rendering and adapter execution.
- [Contracts](contracts.md): ingestion, annotations, operations, access and environment contract sections.
- [Project YAML](project-yaml.md): repository-level environments, reusable connections, schedules, execution order and adapter deployment blocks.
- [Connection YAML](connection-yaml.md): reusable connector defaults and ingestion override behavior.
- [Adapter CLI](cli.md): standardized adapter command vocabulary and common flags.
- [Adapters](adapters.md): how platform adapters depend on the core and where adapter-specific behavior belongs.
- [Databricks adapter](databricks.md): Databricks reference adapter, capabilities and runtime boundary.
- [AWS adapter](adapters/aws.md): AWS Glue Iceberg adapter thesis, phases and capability boundary.
- [Fabric adapter](adapters/fabric.md): Microsoft Fabric Lakehouse notebook-first adapter, validated subset and review boundaries.
- [Snowflake adapter](adapters/snowflake.md): Snowflake SQL warehouse adapter guide, stable supported surface and review boundaries.
- [GCP adapter](adapters/gcp.md): GCP BigQuery adapter guide, stable supported surface and review boundaries.
- [Test contracts across adapters](adapters/test-contracts-across-adapters.md): side-by-side Databricks, AWS, Snowflake, Fabric and GCP guidance for proving the same ingestion with minimal contract diffs.
- [Platform parity tests](platform-parity-tests.md): shared Databricks/AWS/Snowflake/Fabric/GCP scenarios that validate contract portability boundaries.
- [USGS GeoJSON medallion example](../examples/real-world/usgs-earthquake-rest-medallion/README.md): real Databricks, AWS, Snowflake, Fabric and GCP adapter parity project using the shared GeoJSON medallion intent.
- [S3 file medallion example](../examples/real-world/s3-file-medallion/README.md): AWS Glue/Iceberg file ingestion project using S3 CSV files, Glue bookmarks and control-table evidence.
- [AWS failure-path example](../examples/real-world/aws-failure-paths/README.md): contract-only negative tests for failed run evidence, error evidence and redaction.
- [Roadmap](roadmap.md): adapter maturity, second-adapter criteria and release signals.

## Technical Reference

- [Architecture](architecture.md): contributor-oriented architecture, package boundaries and planning flow.
- [Connectors](connectors.md): portable sources, bounded sources, native passthrough and adapter-specific sources.
- [Operations and evidence](operations.md): evidence model, control-table parity and adapter persistence requirements.
- [Security](security.md): secrets, redaction, governance evidence and platform credential boundaries.
- [Development agents](development-agents.md): cost-aware agent routing and CI validation tiers for tests, docs, packaging, security and architecture review.
- [GeoJSON E2E presentation runbook](reports/geojson-test-presentation.md): step-by-step commands for presenting the Databricks, AWS, Snowflake, Fabric and GCP GeoJSON adapter parity proof.
- [Naming](naming.md): target identifiers, generated artifact names and adapter-safe naming.
- [Project template](project-template.md): recommended repository layout for teams using ContractForge Core.
- [Anti-patterns](anti-patterns.md): configurations and architecture choices to avoid.

## Architecture Contracts

The files under [specs](specs/) are not casual notes. They define architecture contracts that code and adapters should preserve.

Important specs:

- [Semantic contract](specs/semantic-contract.md)
- [Contract sections](specs/contract-sections.md)
- [Platform capabilities](specs/platform-capabilities.md)
- [Execution plan](specs/execution-plan.md)
- [Parameter defaults](specs/parameter-defaults.md)
- [Evidence model](specs/evidence-model.md)
- [Control-table parity](specs/control-table-parity.md)
- [Evidence mapping matrix](specs/evidence-mapping-matrix.md)
- [Source portability](specs/source-portability.md)
- [Databricks extensions](specs/extensions-databricks.md)
- [Databricks GA criteria](specs/databricks-ga-criteria.md)
- [Databricks GA waiver registry](specs/databricks-ga-waivers.md)
- [Databricks stable-surface evidence](reports/databricks-stable-surface-evidence.json)
- [AWS extensions](specs/extensions-aws.md)
- [AWS adapter](specs/aws-adapter.md)
- [AWS capability parity](specs/aws-capability-parity.md)
- [AWS stable-surface criteria](specs/aws-ga-criteria.md)
- [AWS stable-surface waiver registry](specs/aws-ga-waivers.md)
- [GCP capability parity](specs/gcp-capability-parity.md)
- [GCP stable-surface evidence](reports/gcp-stable-surface-evidence.json)
- [GCP BigQuery file formats smoke](reports/gcp-bigquery-file-formats-smoke.json)
- [GCP BigQuery upsert smoke](reports/gcp-bigquery-upsert-smoke.json)
- [GCP BigQuery bronze-to-gold smoke](reports/gcp-bigquery-bronze-to-gold-smoke.json)
- [GCP BigQuery row access policy smoke](reports/gcp-bigquery-row-access-policy-smoke.json)
- [GCP BigQuery data masking smoke](reports/gcp-bigquery-data-masking-smoke.json)
- [GCP BigQuery error evidence smoke](reports/gcp-bigquery-error-evidence-smoke.json)
- [GCP BigQuery data masking blocker](reports/gcp-bigquery-data-masking-blocker.json)
- [Fabric adapter guide](adapters/fabric.md)
- [Fabric USGS REST E2E smoke](reports/fabric-usgs-rest-e2e-smoke.json)
- [Fabric stable-surface evidence](reports/fabric-stable-surface-evidence.json)
- [Fabric platform parity report](reports/fabric-platform-parity.json)
- [Fabric source-expansion stable-scope decision](reports/fabric-source-expansion-stable-scope-decision.json)
- [Fabric project deploy-only smoke](reports/fabric-project-deploy-smoke.json)
- [Fabric OneLake data access role smoke](reports/fabric-onelake-data-access-role-smoke.json)
- [Fabric OneLake row/column policy smoke](reports/fabric-onelake-row-column-policy-smoke.json)
- [Fabric deployment pipeline read probe](reports/fabric-deployment-pipeline-read-probe.json)
- [Fabric deployment pipeline lifecycle smoke](reports/fabric-deployment-pipeline-lifecycle-smoke.json)
- [Fabric deployment pipeline stage promotion smoke](reports/fabric-deployment-pipeline-stage-promotion-smoke.json)
- [Fabric HTTP JSON source smoke](reports/fabric-http-json-source-smoke.json)
- [Fabric HTTP CSV source smoke](reports/fabric-http-csv-source-smoke.json)
- [Fabric HTTP text source smoke](reports/fabric-http-text-source-smoke.json)
- [Fabric Lakehouse text source smoke](reports/fabric-lakehouse-text-source-smoke.json)
- [Fabric Lakehouse file formats source smoke](reports/fabric-lakehouse-file-formats-source-smoke.json)
- [Fabric OneLake shortcut source smoke](reports/fabric-onelake-shortcut-source-smoke.json)
- [Fabric authenticated REST source smoke](reports/fabric-auth-rest-source-smoke.json)
- [Fabric authenticated REST variants source smoke](reports/fabric-auth-rest-variants-source-smoke.json)
- [Fabric authenticated REST OAuth source smoke](reports/fabric-auth-rest-oauth-source-smoke.json)
- [Fabric authenticated HTTP JSON source smoke](reports/fabric-auth-http-json-source-smoke.json)
- [Fabric authenticated HTTP JSON variants source smoke](reports/fabric-auth-http-json-variants-source-smoke.json)
- [Fabric authenticated HTTP CSV variants source smoke](reports/fabric-auth-http-csv-variants-source-smoke.json)
- [Fabric authenticated HTTP text Basic source smoke](reports/fabric-auth-http-text-basic-source-smoke.json)
- [Fabric authenticated HTTP text bearer source smoke](reports/fabric-auth-http-text-bearer-source-smoke.json)
- [Fabric authenticated HTTP text API-key source smoke](reports/fabric-auth-http-text-api-key-source-smoke.json)
- [Fabric SQL Server JDBC source smoke](reports/fabric-sqlserver-jdbc-source-smoke.json)
- [Fabric PostgreSQL JDBC source smoke](reports/fabric-postgres-jdbc-source-smoke.json)
- [Fabric Azure Blob source smoke](reports/fabric-azure-blob-source-smoke.json)
- [Fabric private Azure Blob source smoke](reports/fabric-private-azure-blob-source-smoke.json)
- [Fabric external Azure Blob shortcut source smoke](reports/fabric-external-azure-blob-shortcut-source-smoke.json)
- [Fabric ADLS Gen2 shortcut source smoke](reports/fabric-adls-shortcut-source-smoke.json)
- [Fabric GCS shortcut source smoke](reports/fabric-gcs-shortcut-source-smoke.json)
- [Fabric external Amazon S3 shortcut source smoke](reports/fabric-external-s3-shortcut-source-smoke.json)
- [Fabric S3-compatible shortcut source smoke](reports/fabric-s3-compatible-shortcut-source-smoke.json)
- [Fabric Iceberg table shortcut source smoke](reports/fabric-iceberg-table-shortcut-source-smoke.json)
- [Fabric ADLS Iceberg table shortcut source smoke](reports/fabric-adls-iceberg-table-shortcut-source-smoke.json)
- [Fabric GCS Iceberg table shortcut source smoke](reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json)
- [Fabric Confluent Kafka bounded source smoke](reports/fabric-confluent-kafka-bounded-source-smoke.json)
- [Fabric Confluent Kafka available-now source smoke](reports/fabric-confluent-kafka-available-now-source-smoke.json)
- [Fabric Event Hubs Kafka available-now source smoke](reports/fabric-eventhubs-kafka-available-now-source-smoke.json)
- [GCP authenticated REST Secret Manager smoke](reports/gcp-authenticated-rest-secret-manager-smoke.json)
- [GCP authenticated REST/HTTP Secret Manager variants smoke](reports/gcp-auth-rest-http-secret-manager-variants-smoke.json)
- [GCP authenticated REST/HTTP Secret Manager variants historical blocker](reports/gcp-auth-rest-http-secret-manager-variants-blocker.json)
- [GCP HTTP text materialization local smoke](reports/gcp-http-text-materialization-local-smoke.json)
- [GCP HTTP sources BigQuery smoke](reports/gcp-http-sources-bigquery-smoke.json)
- [GCP HTTP file binary BigQuery smoke](reports/gcp-http-file-binary-bigquery-smoke.json)
- [GCP HTTP text BigQuery historical blocker](reports/gcp-http-text-bigquery-smoke-blocker.json)
- [GCP HTTP file materialization local smoke](reports/gcp-http-file-materialization-local-smoke.json)
- [GCP hash-diff cross-adapter production parity](reports/gcp-hashdiff-cross-adapter-production-parity.json)
- [Snowflake capability and evidence parity](specs/snowflake-capability-parity.md)
- [Snowflake adapter implementation plan](specs/snowflake-adapter-implementation-plan.md)
- [Snowflake adapter parity execution plan](specs/snowflake-adapter-parity-execution-plan.md)
- [Snowflake adapter operations guide](adapters/snowflake.md)
- [Snowflake stabilization matrix](specs/snowflake-stabilization-matrix.md)
- [Snowflake stable-surface criteria](specs/snowflake-ga-criteria.md)
- [Snowflake stable-surface waiver registry](specs/snowflake-ga-waivers.md)
- [AWS and Snowflake production maturity plan](specs/aws-snowflake-production-maturity-plan.md)
- [Hash-diff production benchmark runbook](specs/hash-diff-production-benchmark-runbook.md)
- [AWS adapter hardening checklist](specs/aws-adapter-hardening-checklist.md)
- [AWS stabilization matrix](specs/aws-stabilization-matrix.md)
- [Write engines](specs/write-engines.md)
- [Adapter authoring](specs/adapter-authoring.md)
- [Publication packaging](specs/publication-packaging.md)
- [API stability and versioning](specs/api-stability.md)

## Architecture Decisions

Formal decisions live in [adrs](adrs/).

- ADR-001: core-adapter architecture
- ADR-002: Databricks reference adapter
- ADR-003: portable versus platform-specific semantics
- ADR-004: source portability and connector scope
- ADR-005: adapter parameter policy
- ADR-006: environment contract
- ADR-007: AWS Glue Iceberg adapter strategy
- ADR-008: core connector centralization and independence

## Documentation Rule

When adding a user-visible semantic concept, update:

1. the relevant user guide in this directory;
2. the relevant spec under `docs/specs`;
3. adapter documentation when platform behavior changes;
4. tests that enforce the architecture boundary.
