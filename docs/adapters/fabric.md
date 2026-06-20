# Fabric Adapter

`contractforge-fabric` is the Microsoft Fabric Lakehouse adapter for
ContractForge.

The current adapter is a stable supported notebook-first Fabric Lakehouse
surface. It can render, deploy and run generated Fabric
notebooks for the documented Lakehouse subset, and it writes ContractForge
control-table evidence into Fabric Lakehouse Delta tables.

## Validated Scope

- Package: independent `contractforge-fabric` wheel.
- Subtarget: `fabric_lakehouse`.
- Runtime path: Fabric REST preflight, generated Notebook deployment, Notebook
  run submission and terminal job classification.
- Sources:
  - table, view, SQL and Lakehouse file sources for notebook rendering;
  - Lakehouse `text`, `orc`, `avro` and `xml` file sources with live Fabric
    source-expansion evidence;
  - internal OneLake shortcut reads with live Fabric shortcut creation and
    source-expansion evidence;
  - public/no-auth bounded `rest_api` with live USGS REST/GeoJSON
    bronze-to-gold evidence;
  - public/no-auth `http_json`, `http_csv` and `http_text` with live Fabric
    source-expansion evidence;
  - authenticated bounded REST with Basic auth, bearer token, API-key and
    OAuth client-credentials placeholders, plus authenticated `http_json` and
    `http_csv` with Basic auth, bearer token and API-key placeholders,
    `{{ secret:scope/key }}` secret placeholders and Azure Key Vault runtime
    resolution, with live Fabric source-expansion evidence.
  - endpoint-enforced Basic, bearer and API-key auth on `http_text`, with live
    Fabric source-expansion evidence.
  - SQL Server/Azure SQL JDBC and PostgreSQL JDBC with Basic auth, `{{ secret:scope/key }}`
    password placeholders and Azure Key Vault runtime resolution, with live
    Fabric source-expansion evidence.
  - Azure Blob CSV object storage through a Fabric Spark-readable
    `extensions.fabric.source_runtime_path` binding. Public Blob and direct
    private Blob with a Key Vault-backed storage account key both have live
    Fabric source-expansion evidence.
  - External Azure Blob shortcut reads through native Fabric shortcut creation
    and a Fabric AzureBlobs cloud connection with Key credentials, with live
    Fabric source-expansion evidence.
  - External ADLS Gen2 shortcut reads through native Fabric shortcut creation
    and a Fabric AzureDataLakeStorage cloud connection with Key credentials,
    with live Fabric source-expansion evidence.
  - External Google Cloud Storage shortcut reads through native Fabric shortcut
    creation and a Fabric GoogleCloudStorage cloud connection with Basic HMAC
    credentials, with live Fabric source-expansion evidence.
  - External Amazon S3 shortcut reads through native Fabric shortcut creation
    and a Fabric AmazonS3 cloud connection with Basic IAM user credentials,
    with live Fabric source-expansion evidence.
  - External S3-compatible shortcut reads through native Fabric shortcut
    creation and a Fabric AmazonS3Compatible cloud connection with Basic IAM
    user credentials, with live Fabric source-expansion evidence.
  - ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg table shortcut reads
    through native Fabric shortcut creation under `Tables`, Fabric
    Iceberg-to-Delta virtualization and `source.type: iceberg_table`, with
    live Fabric source-expansion evidence.
  - Confluent Cloud Kafka bounded replay and checkpointed available-now
    catch-up with Key Vault-backed SASL configuration, with live Fabric
    source-expansion evidence.
  - Azure Event Hubs through its Kafka-compatible endpoint with checkpointed
    available-now catch-up and Key Vault-backed SASL configuration, with live
    Fabric source-expansion evidence.
- Write modes: `append`, `overwrite`, `upsert`, `hash_diff_upsert`,
  `historical` and `snapshot_reconcile_soft_delete`.
- Quality: required columns, not-null, unique keys, accepted values, minimum
  rows, max-null-ratio and expression gates.
- Shape and transforms: JSON parsing, array explode/explode_outer, column
  projection, flatten, cast, standardize, derive, composite keys and
  deterministic deduplication.
- Evidence: live control-table probes validate runs, errors, quality, schema,
  source metadata, lineage, explain, state, operations, annotations and access
  review evidence. Project deployment renders the shared
  `ctrl_deployment_versions` ledger DDL and insert statements for Fabric
  Lakehouse Delta storage.

## Evidence

The main evidence manifests are:

- [Fabric USGS REST E2E smoke](../reports/fabric-usgs-rest-e2e-smoke.json)
- [Fabric stable-surface evidence](../reports/fabric-stable-surface-evidence.json)
- [Fabric platform parity report](../reports/fabric-platform-parity.json)
- [Fabric source-expansion stable-scope decision](../reports/fabric-source-expansion-stable-scope-decision.json)
- [Fabric project deploy-only smoke](../reports/fabric-project-deploy-smoke.json)
- [Fabric OneLake data access role smoke](../reports/fabric-onelake-data-access-role-smoke.json)
- [Fabric OneLake row/column policy smoke](../reports/fabric-onelake-row-column-policy-smoke.json)
- [Fabric deployment pipeline read probe](../reports/fabric-deployment-pipeline-read-probe.json)
- [Fabric deployment pipeline lifecycle smoke](../reports/fabric-deployment-pipeline-lifecycle-smoke.json)
- [Fabric deployment pipeline stage promotion smoke](../reports/fabric-deployment-pipeline-stage-promotion-smoke.json)
- [Fabric HTTP JSON source smoke](../reports/fabric-http-json-source-smoke.json)
- [Fabric HTTP CSV source smoke](../reports/fabric-http-csv-source-smoke.json)
- [Fabric HTTP text source smoke](../reports/fabric-http-text-source-smoke.json)
- [Fabric Lakehouse text source smoke](../reports/fabric-lakehouse-text-source-smoke.json)
- [Fabric Lakehouse file formats source smoke](../reports/fabric-lakehouse-file-formats-source-smoke.json)
- [Fabric OneLake shortcut source smoke](../reports/fabric-onelake-shortcut-source-smoke.json)
- [Fabric authenticated REST source smoke](../reports/fabric-auth-rest-source-smoke.json)
- [Fabric authenticated REST variants source smoke](../reports/fabric-auth-rest-variants-source-smoke.json)
- [Fabric authenticated REST OAuth source smoke](../reports/fabric-auth-rest-oauth-source-smoke.json)
- [Fabric authenticated HTTP JSON source smoke](../reports/fabric-auth-http-json-source-smoke.json)
- [Fabric authenticated HTTP JSON variants source smoke](../reports/fabric-auth-http-json-variants-source-smoke.json)
- [Fabric authenticated HTTP CSV variants source smoke](../reports/fabric-auth-http-csv-variants-source-smoke.json)
- [Fabric authenticated HTTP text Basic source smoke](../reports/fabric-auth-http-text-basic-source-smoke.json)
- [Fabric authenticated HTTP text bearer source smoke](../reports/fabric-auth-http-text-bearer-source-smoke.json)
- [Fabric authenticated HTTP text API-key source smoke](../reports/fabric-auth-http-text-api-key-source-smoke.json)
- [Fabric SQL Server JDBC source smoke](../reports/fabric-sqlserver-jdbc-source-smoke.json)
- [Fabric PostgreSQL JDBC source smoke](../reports/fabric-postgres-jdbc-source-smoke.json)
- [Fabric Azure Blob source smoke](../reports/fabric-azure-blob-source-smoke.json)
- [Fabric private Azure Blob source smoke](../reports/fabric-private-azure-blob-source-smoke.json)
- [Fabric external Azure Blob shortcut source smoke](../reports/fabric-external-azure-blob-shortcut-source-smoke.json)
- [Fabric ADLS Gen2 shortcut source smoke](../reports/fabric-adls-shortcut-source-smoke.json)
- [Fabric GCS shortcut source smoke](../reports/fabric-gcs-shortcut-source-smoke.json)
- [Fabric external Amazon S3 shortcut source smoke](../reports/fabric-external-s3-shortcut-source-smoke.json)
- [Fabric S3-compatible shortcut source smoke](../reports/fabric-s3-compatible-shortcut-source-smoke.json)
- [Fabric Iceberg table shortcut source smoke](../reports/fabric-iceberg-table-shortcut-source-smoke.json)
- [Fabric ADLS Iceberg table shortcut source smoke](../reports/fabric-adls-iceberg-table-shortcut-source-smoke.json)
- [Fabric GCS Iceberg table shortcut source smoke](../reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json)
- [Fabric Confluent Kafka bounded source smoke](../reports/fabric-confluent-kafka-bounded-source-smoke.json)
- [Fabric Confluent Kafka available-now source smoke](../reports/fabric-confluent-kafka-available-now-source-smoke.json)
- [Fabric Event Hubs Kafka available-now source smoke](../reports/fabric-eventhubs-kafka-available-now-source-smoke.json)

Kafka bounded and available-now paths, including the Event Hubs Kafka-compatible
available-now path, have live Fabric source-expansion evidence.

The stable-surface suite is contract-only and uses SQL sources to isolate
runtime/write/evidence semantics from external connector availability. The USGS
project validates the public REST source path from bronze to silver to gold.

## Runtime Prerequisites

- Microsoft Fabric workspace on supported Fabric capacity.
- Workspace contributor/read/write/execute permissions for Notebook items.
- A Lakehouse item configured in the environment.
- A default Spark pool that fits the capacity. In the validated FTL4 workspace,
  a single-node Small custom pool was required to avoid
  `TooManyRequestsForCapacity`.
- Azure CLI authentication for the tenant used by the workspace.
- For authenticated HTTP/REST drafts, Azure Key Vault access from the Fabric
  notebook runtime through `notebookutils.credentials.getSecret`, with
  `environment.secrets.vault_url` or `environment.secrets.scopes.<scope>`
  configured.
- For object-storage drafts, a Fabric-readable source path declared through
  `extensions.fabric.source_runtime_path`, such as a reviewed Lakehouse
  shortcut, staged Lakehouse file path or direct Spark object-store URI. Direct
  private Azure Blob CSV can also declare
  `extensions.fabric.storage_account_key_secret` with a
  `{{ secret:scope/key }}` Key Vault placeholder; generated notebooks resolve
  the key and set Spark's `fs.azure.account.key.<account>.blob.core.windows.net`
  configuration before reading.
- For external Azure Blob shortcut drafts, a Fabric cloud connection ID is
  required. Validated project smokes declare this through
  `fabric_setup.shortcuts` and environment parameters such as
  `parameters.fabric.connections.azure_blob_shortcut_connection_id`.
- For external ADLS Gen2 shortcut drafts, a Fabric AzureDataLakeStorage cloud
  connection ID is required. The validated smoke uses Key credentials stored in
  the Fabric connection, and resolves
  `parameters.fabric.connections.adls_shortcut_connection_id` into
  `fabric_setup.shortcuts`.
- For external Google Cloud Storage shortcut drafts, a Fabric
  GoogleCloudStorage cloud connection ID is required. The validated smoke uses
  Basic HMAC credentials stored in the Fabric connection, and resolves
  `parameters.fabric.connections.gcs_shortcut_connection_id` into
  `fabric_setup.shortcuts`.
- For external Amazon S3 shortcut drafts, a Fabric AmazonS3 cloud connection ID
  is required. The validated smoke uses Basic IAM user credentials stored in the
  Fabric connection, and the project resolves
  `parameters.fabric.connections.amazon_s3_shortcut_connection_id` into
  `fabric_setup.shortcuts`.
- For external S3-compatible shortcut drafts, a Fabric AmazonS3Compatible cloud
  connection ID is required. The validated smoke uses Basic IAM user
  credentials stored in the Fabric connection, and the project resolves
  `parameters.fabric.connections.s3_compatible_shortcut_connection_id` into
  `fabric_setup.shortcuts`.
- For Iceberg table shortcut drafts, the shortcut must be created directly
  under `Tables` and point at an Iceberg table folder containing `metadata/`
  and `data/`. The validated smokes use `source.type: iceberg_table` after
  Fabric virtualizes ADLS Gen2, Amazon S3 and Google Cloud Storage Iceberg
  folders as Lakehouse tables.
- For Kafka drafts, SASL configuration through a `{{ secret:scope/key }}`
  Key Vault placeholder. The validated bounded Confluent Kafka path uses
  Spark's batch reader with `starting_offsets: earliest` and
  `ending_offsets: latest`; the validated available-now path uses Spark
  Structured Streaming with `trigger(availableNow=True)` and a declared
  `checkpoint_location`. The validated Azure Event Hubs path uses the same
  Kafka-compatible Spark reader shape against the Event Hubs Kafka endpoint and
  a Key Vault-backed JAAS configuration.
- For Fabric-native governance apply drafts, contracts must declare explicit
  Fabric IDs under `extensions.fabric.access_apply`. The adapter can plan and
  execute workspace role assignments through the Fabric
  `workspaces/{workspaceId}/roleAssignments` API and item sensitivity labels
  through the Fabric admin `items/bulkSetLabels` API. It can also apply
  explicit OneLake data access roles through the Fabric
  `items/{itemId}/dataAccessRoles` preview API when the contract provides the
  native Lakehouse item ID, role members and decision rules. Live evidence
  validates role create/list/delete for a basic Path/Action read policy and
  row/column constraints against a Fabric-resolved Lakehouse table, with
  cleanup. Generic ContractForge row-filter functions are not auto-translated
  into OneLake SQL predicates; contracts must declare explicit Fabric-native
  OneLake policy payloads for apply mode.
- For deploy-only project promotion, `contractforge-fabric deploy-project`
  renders a deterministic project deployment manifest and can create/update
  generated Notebook item definitions without executing the notebooks. Each
  deploy creates a unique `deployment_id`; each project step records
  `deployment_hash`, `contract_hash`, `environment_hash` and `manifest_hash`
  rows in the generated Fabric deployment ledger SQL artifact.
  Deployment pipeline and Git settings can be recorded in `project.deployment.fabric`
  for promotion review. Tenant-level deployment-pipeline read,
  create/list/delete lifecycle and stage-to-stage Notebook content promotion
  probes succeeded with cleanup. The stage promotion smoke promoted one
  generated stable-surface Notebook from the `Manager` workspace to a temporary
  target workspace, verified the target-stage item, deleted the promoted item,
  unassigned both stages, deleted the pipeline and deleted the temporary target
  workspace. Git integration and Data Factory lifecycle promotion remain
  outside the current notebook-first stable scope.

## Stable-Final Exclusions

The following are intentionally not claimed as stable behavior:

- OAuth for HTTP-file source types. OAuth is not currently part of the
  HTTP-file source vocabulary;
- Private-network shortcut variants, managed identity/OAuth object-storage
  access, Delta Sharing, direct-catalog Iceberg variants
  and native Event Hubs/Fabric Real-Time/Eventstream modes beyond the validated
  Kafka-compatible bounded and available-now paths;
- Fabric/Purview table grants, row filters, column masks and broader metadata
  apply mode beyond explicit workspace role assignment, sensitivity-label and
  OneLake data access role APIs with explicit Fabric-native decision rules;
- concurrent lock semantics beyond generated Delta lock SQL;
- live Data Factory pipeline deployment and Git integration certification;
- adapter-wide parity beyond the documented notebook-first subset.

The shared parity report now includes Fabric in the same machine-readable
scenario set used for Databricks, AWS, Snowflake, Fabric and GCP. That closes
the parity reporting gap, but it does not widen the stable claim beyond the
validated notebook-first subset.

## CLI

Fabric follows the standardized adapter command vocabulary in
[Adapter CLI](../cli.md). Fabric-specific flags such as `--max-attempts`,
`--retry-after-seconds` and preflight checks remain platform options under the
canonical command names.

`stabilization-report --strict-final` returns zero for the documented
notebook-first stable-final claim. The exclusions above remain review-required
unless separate evidence is attached.

## Related Docs

- [Fabric parity review](../../adapters/fabric/PARITY.md)
- [Fabric adapter README](../../adapters/fabric/README.md)
- [USGS GeoJSON medallion example](../../examples/real-world/usgs-earthquake-rest-medallion/README.md)
