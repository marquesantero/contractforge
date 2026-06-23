# Changelog

All notable changes to `contractforge-core` are documented in this file.

The format follows Keep a Changelog, and this package follows semantic
versioning as described in `docs/specs/api-stability.md`.

## [Unreleased]

### Added

- Added core contract default resolution for split bundles using
  `project.yaml.defaults`, including an auditable decision ledger and the
  `contractforge resolve-bundle` inspection command.
- Added safe inference from `merge_keys` to `quality_rules.unique_key` and
  missing `not_null` checks for identity-based write modes.
- Added adapter-specific project defaults for cross-platform contract trees and
  layer-aware defaults such as `schema_policy`.
- Documented the complete parameter-defaults reference, including
  `project.yaml.defaults`, adapter overrides and deterministic
  quality/custom-transform inferences.

### Changed

- Aligned adapter project loaders so project-scoped simple YAML contracts can
  use `project.yaml.defaults` consistently across AWS, Databricks, Snowflake,
  Fabric and GCP.

## [0.2.0] - 2026-06-19

### Added

- Promoted the public package set for the current ContractForge maturity
  baseline across core, Databricks, AWS, Snowflake, Fabric, GCP and AI.
- Added the core-owned `ctrl_deployment_versions` deployment ledger schema,
  stable deployment hashes and adapter-native ledger DDL/insert renderers for
  Databricks, AWS, Snowflake, Fabric and GCP.
- Added project and connection semantics used by the cross-platform test
  projects, including reusable source defaults and environment-specific
  bindings.
- Added stable writer aliases for contract authoring: `append`, `overwrite`,
  `upsert`, `hash_diff_upsert`, `historical` and
  `snapshot_reconcile_soft_delete`.

### Changed

- Updated packaging and release metadata for the independent PyPI
  distributions.
- Kept adapter-specific behavior outside the core package while aligning the
  core validation boundary with the current adapter surfaces.

## [0.1.0] - 2026-06-08

### Added

- Initial public preview release of the platform-neutral ContractForge core.
- Semantic contract models, project parsing, capability matching, planning,
  source connector catalog, evidence models and the `contractforge` CLI.
