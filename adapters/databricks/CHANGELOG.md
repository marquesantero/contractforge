# Changelog

All notable changes to `contractforge-databricks` are documented in this file.

The format follows Keep a Changelog, and this package follows semantic
versioning as described in `../../docs/specs/api-stability.md`.

## [Unreleased]

### Changed

- Aligned project contract loading so simple YAML contracts under a
  `project.yaml` tree use the core `project.yaml.defaults` resolver before
  Databricks planning, rendering or deployment.
- Updated governance preview/apply-plan commands to use the core bundle loader
  for split contracts, preserving project defaults and bundle validation.

## [0.2.0] - 2026-06-19

### Added

- Added `contractforge-databricks stabilization-report` with
  `STABLE_SUPPORTED_SURFACE` and `stable_final=true` for the documented
  serverless Delta surface.
- Added a Databricks stable-surface evidence manifest under `docs/reports`.
- Added release metadata for the current stable Databricks adapter baseline.

### Changed

- Aligned the adapter dependency range with `contractforge-core` 0.2.x.
- Documented the validated contract-only execution model for Databricks-native
  jobs and serverless-oriented runtime guidance.

## [0.1.0] - 2026-06-08

### Added

- Initial public alpha release of the Databricks adapter.
- Databricks contract planning, SQL/artifact rendering, Asset Bundle support,
  runtime helpers, governance, quality, evidence, lineage and operational
  cost surfaces.
