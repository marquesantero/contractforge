# API Stability And Versioning

## Purpose

ContractForge publishes the core, adapters and AI companion as separate Python
distributions. This document defines what each package promises as public API,
what remains preview, and how package versions move independently.

## Versioning Policy

ContractForge packages use independent semantic versioning. Package versions do
not move in lockstep.

The current public release line is:

| Distribution | Current version | Stability |
| --- | ---: | --- |
| `contractforge-core` | `0.2.0` | Beta public API boundary. |
| `contractforge-databricks` | `0.2.0` | Stable supported surface for the documented Databricks Delta/serverless-oriented boundary. |
| `contractforge-aws` | `0.2.0` | Stable supported surface for `aws_glue_iceberg`; advanced boundaries remain explicit planner decisions. |
| `contractforge-snowflake` | `0.2.0` | Stable supported surface for `snowflake_sql_warehouse`; account-feature-dependent boundaries remain explicit planner decisions. |
| `contractforge-fabric` | `0.2.0` | Stable supported surface for `fabric_lakehouse`; capacity availability remains an operational platform concern. |
| `contractforge-gcp` | `0.2.0` | Stable supported surface for `gcp_bigquery`; Workflows orchestration and BigQuery execution are adapter-owned. |
| `contractforge-ai` | `0.3.0` | Alpha AI companion surface. |

Compatibility is declared through each package's `dependencies` field. There is
no promise that two packages with the same version number are related releases.

## Public API

For `contractforge-core`, public API includes importable modules under
`contractforge_core` whose module path segments do not start with `_`, plus the
documented `contractforge` CLI commands.

The core public API includes:

- semantic contract models
- project parsing and schedule helpers
- capability models and matching
- connector catalog metadata
- planning result types
- evidence and security redaction models
- documented CLI behavior

Core modules or names prefixed with `_` are internal. Future `_internal`
packages are also internal.

## Preview API

Adapter packages expose stable supported surfaces only when explicitly
promoted. Anything outside the documented surface remains preview or
review-required and may change in minor versions. Adapters must still preserve
the core-adapter dependency direction and must declare their compatible
`contractforge-core` range.

`contractforge-aws` is promoted for the documented `aws_glue_iceberg` stable
supported surface. Its remaining production-certification boundaries, including
generic streaming providers, workload-specific governance/SLA claims and
excluded historical/snapshot soft-delete semantics, remain preview or review-required
until their criteria are met.

`contractforge-snowflake` is promoted for the documented
`snowflake_sql_warehouse` stable supported surface. Its remaining
production-certification boundaries, including continuous ingestion,
account-feature-dependent access policy validation and excluded historical/snapshot
soft-delete semantics, remain preview or review-required until their criteria
are met.

`contractforge-ai` is alpha. Generated project structure, provider routing
reports, prompt templates and enrichment payloads may change in minor versions.
The deterministic validation boundary remains authoritative: generated outputs
must pass core validation before they are treated as usable ContractForge
projects.

## Internal API

The following are internal and may change without deprecation:

- modules, packages, functions, classes or attributes prefixed with `_`
- generated runtime code that is not documented as a public helper
- test fixtures and `.tmp` artifacts
- provider prompt internals unless documented in the AI package docs
- adapter implementation details not exported from package `__init__.py`

## Breaking Changes

Before `1.0.0`, minor versions may include breaking changes in preview
surfaces. Patch versions should remain bug-fix only.

After `1.0.0`, breaking changes to stable public API require a major version
increase. Alpha adapters and AI may remain below `1.0.0` while core reaches
`1.0.0`.

## Databricks GA Policy

When the Databricks adapter reaches GA, `contractforge-databricks` may move to
`1.0.0`. The core moves to `1.0.0` with it only if the GA boundary depends on a
stable core public API contract. AWS, Snowflake and AI continue on their own
version tracks.

`STABLE_SUPPORTED_SURFACE` is a narrower release-readiness classification for
the documented adapter surface. It can be `stable_final=true` while the
Databricks 1.0.0 GA gate, full provider matrices and API-freeze decisions remain
separate.
