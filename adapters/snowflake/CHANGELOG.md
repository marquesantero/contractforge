# Changelog

All notable changes to `contractforge-snowflake` are documented in this file.

The format follows Keep a Changelog, and this package follows semantic
versioning as described in `../../docs/specs/api-stability.md`.

## [Unreleased]

No unreleased changes.

## [0.2.1] - 2026-06-24

### Added

- Documented Snowflake REST secret binding through
  `parameters.snowflake.secrets` and `{{ secret:snowflake/<alias> }}`
  placeholders for hosted procedure execution.
- Documented the validated TMDB task-graph execution path for authenticated
  bounded REST ingestion.

### Changed

- Aligned project contract loading so simple YAML contracts under a
  `project.yaml` tree use the core `project.yaml.defaults` resolver before
  Snowflake planning, publishing or project task deployment.
- Updated Snowflake task-graph deployment guidance to reflect the live
  `CREATE OR REPLACE TASK` lifecycle with existing task suspension and
  `run-project --wait` task-history polling.

### Fixed

- Fixed Snowflake quality-rule documentation for unquoted SQL aliases returned
  by Snowflake metadata in uppercase; contract aliases are matched
  case-insensitively during runtime quality checks.
- Clarified that undeclared Snowflake secret placeholders are rejected or fail
  closed instead of falling back to accidental objects such as `PUBLIC.NONE`.

## [0.2.0] - 2026-06-19

### Added

- Added release metadata for the current Snowflake adapter baseline covering
  SQL warehouse execution, hosted procedure library runs, staged files,
  bounded REST/API sources, secrets/external access integration, quality,
  schema policy, evidence, lineage and cost surfaces.

### Changed

- Aligned the adapter dependency range with `contractforge-core` 0.2.x.
- Promoted the documented `snowflake_sql_warehouse` surface as the stable
  supported release boundary while keeping account-feature-dependent behavior
  explicit in the docs and planner decisions.

## [0.1.0] - 2026-06-08

### Added

- Initial public alpha release of the Snowflake adapter.
- Snowflake SQL warehouse planning, Snowpark library-runner support, staged
  source bindings, deployment artifacts, quality, evidence, lineage, cost and
  project task graph surfaces.
- Promoted the documented `snowflake_sql_warehouse` surface to
  stable-supported release governance.
- Added Snowflake stable-surface criteria, waiver registry and evidence
  manifest documentation.
- Added `contractforge-snowflake stabilization-report` with strict-final
  boundary signaling.
