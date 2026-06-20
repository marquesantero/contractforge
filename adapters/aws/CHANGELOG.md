# Changelog

All notable changes to `contractforge-aws` are documented in this file.

The format follows Keep a Changelog, and this package follows semantic
versioning as described in `../../docs/specs/api-stability.md`.

## [0.2.0] - 2026-06-19

### Changed

- Promoted the documented `aws_glue_iceberg` surface from alpha wording to
  stable-supported release governance.
- Added AWS stable-surface criteria and waiver registry documentation.
- Added a versioned AWS stable-surface evidence manifest under `docs/reports`.
- Updated `contractforge-aws stabilization-report` to return
  `STABLE_SUPPORTED_SURFACE` and `stable_final=true` for the documented
  Glue/Iceberg scope.
- Aligned the adapter dependency range with `contractforge-core` 0.2.x.
- Documented prerequisites and execution expectations for stable
  `hash_diff_upsert`, `historical` and `snapshot_reconcile_soft_delete`
  writes instead of hiding platform setup behind the adapter.

### Added

- Added release metadata for the current AWS adapter baseline covering Glue
  Spark, Iceberg, S3 artifacts, Athena evidence, REST/HTTP sources, MSK/Kafka
  validation, governance review/apply helpers and production run evidence.

## [0.1.0] - 2026-06-08

### Added

- Initial public alpha release of the AWS adapter.
- AWS Glue/Iceberg planning, artifact rendering, quality, evidence, lineage,
  RDS IAM, REST/HTTP source handling, orchestration and Athena-facing runtime
  helpers.
