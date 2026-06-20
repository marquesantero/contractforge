# Changelog

All notable changes to `contractforge-snowflake` are documented in this file.

The format follows Keep a Changelog, and this package follows semantic
versioning as described in `../../docs/specs/api-stability.md`.

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
