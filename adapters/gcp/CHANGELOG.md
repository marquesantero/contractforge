# Changelog

All notable changes to `contractforge-gcp` are documented in this file.

## [0.2.0] - 2026-06-19

### Added

- Added the Google Cloud BigQuery adapter with planning, rendering, smoke execution and evidence DDL.
- Validated the documented stable BigQuery batch surface with live GCS file-format, explicit-column upsert, bronze-to-gold, governance, annotation, failed-run evidence and BigLake Iceberg smokes.
- Validated compact opt-in BigQuery advanced write-mode replay smokes for `hash_diff_upsert`, `historical` and `snapshot_reconcile_soft_delete`, while keeping these modes review-required outside the stable surface.
- Added advanced write-mode source-key preflight SQL and validated `hash_diff_upsert` changed-row replay plus null/duplicate merge-key failure smokes.
- Added a production-sized GCP BigQuery `hash_diff_upsert` benchmark with initial load, no-change replay, changed-row wave, null/duplicate key failures, overlap serialization and DML cost metrics.
- Accepted `hash_diff_upsert` cross-adapter production parity for GCP using the GCP, AWS, Snowflake and Fabric evidence reports.
- Added a production-sized GCP BigQuery advanced-write benchmark for `historical` and `snapshot_reconcile_soft_delete`, covering SCD2 replay/change/delete/late-arriving rejection and snapshot tombstone/reactivation cases.
- Added historical delete-expression expiration and late-arriving reject failure smokes for opt-in BigQuery review-required execution.
- Added snapshot complete-source blocking, same-hash reactivation, tombstone and replay smokes for opt-in BigQuery review-required execution.
- Added deterministic single-contract BigQuery deployment manifests and `render --output-dir` artifact materialization.
- Added BigQuery schema-policy planning artifacts and schema evidence table DDL.
- Added an opt-in BigQuery schema-policy runtime hook for table-source inspection, additive nullable column application and schema evidence writes.
- Validated additive nullable BigQuery schema-policy enforcement with live schema and evidence readback.
- Validated strict BigQuery schema-policy drift blocking with failed schema evidence readback.
- Validated permissive nullable BigQuery schema-policy enforcement with live schema and evidence readback.
- Validated destructive BigQuery schema-policy type-change blocking with failed schema evidence readback.
- Added SQL-source schema-policy inspection through a temporary zero-row evidence-dataset probe and validated live schema/evidence readback.
- Added declared-schema GCS load-source schema-policy inspection through a temporary evidence-dataset load probe and validated live schema/evidence readback.
- Added a GCP schema-policy type-mutation decision that keeps automatic BigQuery type widening/mutation review-required outside the stable runtime path.
- Added dry-run GCP project deployment planning with per-contract bundle materialization and a project deployment manifest.
- Added Google Workflows project-runner source planning artifacts to GCP project deployment dry-runs.
- Added sequential GCP project smoke execution through the existing contract-only BigQuery runtime.
- Added neutral OpenLineage control-table evidence for executed BigQuery load/write smoke operations.
- Added query-only operational cost reporting over BigQuery run evidence with operator-supplied rate inputs.
- Added deterministic Dataplex DataScan data-quality planning artifacts plus the `dataplex-quality` command, and validated native DataScan execution/export readback against a 10,000-row BigQuery target.
- Added consolidated governance ledger planning artifacts and governance evidence DDL.
- Added redacted source-review JSON and Markdown artifacts with runtime paths, review prerequisites and graduation gates.
- Added structured non-JDBC source-family promotion paths to GCP source-review artifacts.
- Added source-family promotion-plan JSON artifacts for review-required non-JDBC GCP sources.
- Added the `source-promotion` command and validated raw Iceberg BigLake registration/readback from a declared `gs://` prefix with explicit schema.
- Added authenticated REST/HTTP Secret Manager review artifacts and runtime resolution for `{{ secret:scope/key }}` credential placeholders, validated by live authenticated REST, REST API-key, HTTP JSON bearer-token and HTTP JSON API-key smokes.
- Added declared-format GCP `http_file` Avro, ORC and Parquet materialization through shared HTTP fetch plus BigQuery local load jobs, validated by a live BigQuery project smoke.
- Added deployment manifest execution-readiness signaling so review-required and blocked contracts do not publish executable apply steps.
- Added the public `is_gcp_source_renderable` helper to keep source renderability checks aligned with the GCP classifier.
- Added `stabilization-report --strict-final` for the scoped stable-supported GCP surface.

### Changed

- Aligned the adapter dependency range with `contractforge-core` 0.2.x.
- Promoted the documented `gcp_bigquery` surface to the current stable
  supported release boundary.

## [0.1.0] - 2026-06-08

### Added

- Added the initial Google Cloud BigQuery adapter package.
