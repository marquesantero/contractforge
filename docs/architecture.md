# Architecture

This document is for contributors and maintainers. It describes how ContractForge Core is structured and how adapters should extend it without leaking platform code into the core.

## Product Boundary

ContractForge Core provides:

- public contract models for ingestion, annotations, operations, access and environment;
- semantic normalization into immutable intent models;
- platform capability declarations;
- capability matching and abstract execution plans;
- portability diagnostics;
- platform-neutral evidence models;
- adapter protocols and generic test adapters.

ContractForge Core does not provide:

- a scheduler;
- Spark or Delta execution;
- Databricks, AWS, Azure, Fabric, GCP or Snowflake SDK clients;
- a GUI;
- a guarantee that every platform can run every contract.

## Layered Flow

```text
YAML / Python / generated contracts
        |
contract validation
        |
semantic model
        |
capability matcher
        |
abstract execution plan
        |
platform adapter
        |
native runtime artifacts + evidence
```

The core describes intent. The adapter translates intent into native behavior.

## Package Boundaries

```text
src/contractforge_core/
  contracts/       Public Pydantic contract models and bundle composition.
  semantic/        Immutable semantic objects.
  capabilities/   Platform capability declarations and native capability metadata.
  planner/        Capability matching and abstract plan construction.
  connectors/     Portable source taxonomy and redacted source metadata.
  evidence/       Neutral evidence record shapes.
  execution/      Write-mode names, strategy and execution result models.
  quality/        Neutral quality rule/result concepts.
  schema/         Portable schema diff and policy helpers.
  runtime/        Runtime-neutral helper models.
  security/       Redaction helpers.
  adapters/       Adapter protocol and generic in-memory adapters.
```

Adapter packages live outside the core package:

```text
adapters/databricks/src/contractforge_databricks/
```

Future adapters should follow the same pattern.

## Adapter Contract

An adapter must:

1. declare conservative capabilities;
2. call or respect core planning;
3. render review artifacts for all planning statuses;
4. implement native execution only inside the adapter package;
5. persist or render evidence according to the core evidence model;
6. document unsupported and review-required semantics.

The adapter may add platform warnings and blockers, but it must not silently downgrade semantics.

## No Platform Branching In Core

The core should not contain logic like:

```python
if platform == "databricks":
    ...
```

Instead, adapters declare capabilities:

```python
PlatformCapabilities(
    platform="databricks",
    supports_merge=True,
    supports_scd2=True,
    supports_row_filters=True,
)
```

The planner matches required semantics against declared capabilities.

## Control Tables And Evidence

The Databricks adapter uses Delta control tables. In the core, this is represented as a neutral evidence model.

The core defines evidence concepts:

- runs;
- state;
- locks/idempotency;
- quality results;
- quarantine references;
- errors;
- schema changes;
- lineage;
- source metadata;
- operations;
- access/governance;
- diagnostics;
- cost signals.

Adapters decide persistence: Delta tables, Iceberg tables, object-store JSON, Snowflake audit tables, Fabric Lakehouse tables or native telemetry.

## Maintainability Guardrails

- Keep modules focused by domain.
- Do not create god files for planner, contracts or adapters.
- Prefer immutable semantic dataclasses for internal intent.
- Use Pydantic at public contract boundaries.
- Keep adapter runtime imports lazy.
- Add tests for every new semantic concept.
- Update docs and specs with user-visible behavior changes.
