# Deployment Versioning

ContractForge records deployments as first-class evidence. A deploy is not only
a set of files copied to a platform; it is a versioned control-plane event with
stable hashes for the contract payload, resolved environment, adapter manifest
and deployment row.

The goal is repeatability. A team should be able to answer which contract was
deployed, which runtime package rendered it, which platform artifact was
created, and whether a later deploy changed semantics or only regenerated the
same intent.

## Ownership Boundary

The core owns the ledger contract:

- `ctrl_deployment_versions` schema;
- deterministic hashing rules;
- deployment row shape;
- stable identity fields shared across adapters.

Adapters own platform persistence:

- table creation in the target platform;
- inserts and updates during deploy;
- platform-native artifact references;
- adapter runtime package metadata.

The ledger never changes ingestion semantics. It records the result of a deploy
command.

## Ledger Columns

Each deployment creates one `deployment_id`. Each deployed contract step or
native artifact creates one row with:

| Column | Meaning |
| --- | --- |
| `deployment_id` | Unique id for one deploy command. |
| `deployment_step_id` | Deterministic id for the step inside the deploy. |
| `deployment_hash` | Stable hash of the deployment row, excluding mutable result metadata. |
| `contract_hash` | Stable hash of the contract payload used by that step. |
| `environment_hash` | Stable hash of the resolved environment payload. |
| `manifest_hash` | Stable hash of the adapter deployment manifest payload. |
| `adapter` | Adapter that rendered or deployed the artifact. |
| `runtime_package_versions` | Core and adapter package versions used by the deploy path. |
| `artifact_uri` | Platform-native artifact reference when available. |
| `status` | Planned, deployed, failed or adapter-specific terminal status. |

Adapters may add native metadata, but portable columns remain stable.

## Native Storage

| Adapter | Ledger storage |
| --- | --- |
| Databricks | Delta table in the configured evidence catalog/schema. |
| AWS | Iceberg table registered in Glue Catalog. |
| Snowflake | SQL table in the configured evidence database/schema. |
| Fabric | Lakehouse Delta table in the configured evidence schema. |
| GCP | BigQuery table in the configured evidence dataset. |

## Hash Semantics

Hashes are deterministic and content-based:

- `contract_hash` changes when the effective contract payload changes.
- `environment_hash` changes when the resolved deployment environment changes.
- `manifest_hash` changes when adapter-owned deployment instructions change.
- `deployment_hash` changes when the stable deploy row changes.

Mutable runtime fields such as timestamps, terminal status details and platform
job ids are not part of the stable deployment hash.

## Operational Use

Use the ledger to compare deploys:

- same contract hash, different environment hash: same intent deployed to a
  different target binding;
- same contract and environment hash, different manifest hash: platform
  artifact or adapter deployment behavior changed;
- changed contract hash: ingestion semantics changed and should receive normal
  contract review;
- failed status with recorded hashes: failed deploy is still auditable.

## Public Release Position

Deployment versioning is part of the current public technical preview. The
schema and hashing rules are core-owned, while adapter storage remains
platform-native and may gain additional adapter-specific metadata before a
future `1.0` API freeze.
