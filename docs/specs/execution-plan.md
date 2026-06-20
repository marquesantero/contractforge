# Execution Plan Specification

## Purpose

An execution plan is an abstract plan produced by the semantic core. It is not a Databricks job, Glue script, Fabric pipeline, or SQL file.

The plan exists so adapters can render native artifacts while preserving declared contract semantics.

## Plan Contents

An execution plan may contain:

- source read step
- shape step, when shape intent is declared
- transform step, when transform intent is declared
- quality validation step
- write step
- governance application step
- evidence recording step

## Rendering

Adapters render execution plans into platform-native artifacts, for example:

- YAML
- SQL
- Python
- Databricks Asset Bundles
- Glue job scripts
- Fabric pipeline JSON
- Terraform snippets
- Markdown review reports

Execution is optional and adapter-owned. The core does not execute platform runtime code.

## Execution Outcomes

The core owns a small execution outcome vocabulary for adapter runtimes:

- `SUCCESS`
- `FAILED`
- `SKIPPED`

An adapter may include native metrics and the statement or artifact that executed, but the outcome status and basic fields remain portable so evidence, retries and dashboards can use the same vocabulary across platforms.

## Prepared Inputs

The core defines a small prepared-input model for adapter runtimes:

- source view or staged relation name
- source columns
- rows read
- rows quarantined
- source name
- source metadata

Adapters may prepare this input with Spark, SQL, native pipelines or external landing steps. The core only defines the handoff shape and common fallback rules such as deriving rows written from execution metrics or prepared row counts.

## Execution Windows

The core owns execution window planning for partitioned or backfill-style runs:

- time-window generation from start/end/every
- child run idempotency key composition
- child runtime parameters
- aggregate window result summaries

Adapters render platform-specific filters and runtime artifacts for each window. For example, Databricks renders SQL timestamp predicates with Databricks identifier quoting, while other adapters may render Snowflake SQL, Spark expressions, Dataflow filters or native job parameters.

## Parity Catalogs

The core defines platform-neutral parity catalog models for comparing native platform engines with ContractForge semantics:

- scenario id and title
- requested write mode
- candidate native engine
- expectation: `must_match`, `intentional_difference` or `unsupported`
- required capabilities and contract fields
- expected semantics
- metric expectations
- blockers or review notes

Adapters own the actual scenario catalog for their native engines. Databricks, for example, can publish parity scenarios for SQL MERGE and Lakeflow AUTO CDC without making those engines part of the core.

## Write Strategy Records

The core defines a small write-strategy record for adapter decisions:

- strategy kind
- selected engine
- reason
- blockers
- warnings

Adapters own the decision logic and engine names. For example, Databricks may choose Delta append, SQL MERGE, Lakeflow AUTO CDC or a ContractForge Delta algorithm; another adapter may choose a different native engine while preserving the same strategy record shape.

## Safety Rules

The planner must not:

- silently downgrade write modes
- erase governance requirements
- replace historical with append
- assume streaming equivalence across engines
- generate runtime-specific code from the core package
