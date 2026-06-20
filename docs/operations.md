# Operations And Evidence

Operational evidence is a first-class ContractForge concept.

The Databricks adapter stores evidence in Delta control tables. ContractForge Core generalizes that as an evidence model so every adapter can persist equivalent information in the platform-native store.

## Evidence Concepts

Every production adapter should support or explicitly document gaps for:

- run ledger;
- state and watermarks;
- locks and idempotency;
- quality results;
- quarantine references;
- errors;
- schema changes;
- lineage events;
- source metadata;
- stream or bounded replay summaries;
- annotation application;
- access/governance application;
- operations metadata;
- diagnostics/explain records;
- cost signals;
- framework/source metadata.

## Databricks Mapping

The Databricks adapter maps evidence to Delta tables such as:

- `ctrl_ingestion_runs`;
- `ctrl_ingestion_state`;
- `ctrl_ingestion_quality`;
- `ctrl_ingestion_quarantine`;
- `ctrl_ingestion_errors`;
- `ctrl_ingestion_locks`;
- `ctrl_ingestion_explain`;
- `ctrl_ingestion_lineage`;
- `ctrl_ingestion_metadata`;
- `ctrl_ingestion_schema_changes`;
- `ctrl_ingestion_streams`;
- `ctrl_ingestion_annotations`;
- `ctrl_ingestion_operations`;
- `ctrl_ingestion_access`.

Other adapters should keep the semantic meaning even when table names, storage formats or native telemetry differ.

## Production Requirements

Before a plan is considered production-ready:

1. The adapter must know where evidence will be written.
2. Secrets and credentials must be redacted before persistence.
3. Failures must be recorded when possible.
4. Quality and schema changes must be queryable.
5. Governance application must leave evidence when applied.
6. Retention and cleanup must be documented by the adapter.

## Control-Table Parity

The canonical field-level parity work is tracked in [control-table parity](specs/control-table-parity.md).

Adapters should not drop fields casually. If a platform cannot provide a field, document whether it is:

- equivalent;
- adapter-computed;
- unavailable;
- review-required;
- unsupported.
