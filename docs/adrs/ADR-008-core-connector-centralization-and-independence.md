# ADR-008: Core Connector Centralization and Independence

## Status

Accepted

## Context

Connector logic (request building, pagination, auth, fetch, option mapping) is platform-neutral: it has no genuine per-platform difference. Historically some of it lived inside an adapter (e.g. the bounded REST client in the Databricks adapter) and was at risk of being re-implemented in every new adapter, weakening security and performance guarantees and creating drift.

Separately, the core `connectors` package was a flat set of modules. As connector logic grows and is shared by multiple adapters, a structure is needed that keeps each connector independently maintainable: changing one connector must never force a change that interferes with another.

## Decision

**Centralize platform-neutral connector logic in the core.** If a piece of connector logic has no real per-platform difference, it lives once in `contractforge_core.connectors` and adapters consume it. Adapters keep only platform-specific concerns: native artifact rendering/execution, secret resolution against the platform secret store, and materialization into the platform DataFrame. The portable algorithm is not duplicated across adapters.

**Each core connector is fully independent and self-contained.** Nothing is shared between connectors. If two connectors need similar infrastructure (HTTP retry, SSRF validation, no-redirect fetch), each carries its own copy inside its own folder. There are no cross-connector imports. This isolation is deliberate and overrides DRY: a change to one connector can never ripple into another.

**Folder structure:** `connectors/<family>/<connector>/`.

- Family folders group related connectors; connector folders hold one connector each.
- A connector that grows large is split into multiple files inside its folder to avoid god-files.
- `__init__.py` is a facade only — it re-exports and never contains logic.
- Cross-cutting, non-connector concerns (the connector registry/catalog metadata, source metadata) live at the `connectors` top level, not inside a connector.
- Granularity: JDBC is split per dialect (each dialect independent); Kafka and Event Hubs are single connectors that each cover their bounded and available-now modes.

The top-level `connectors` facade re-exports the public API so callers are shielded from internal structure.

## Consequences

- One hardened, tested implementation per portable connector concern — better security and performance, no adapter drift.
- Maintenance isolation: a connector can be changed without risk to others.
- Accepted cost: small infrastructure (retry/SSRF) is duplicated between connectors rather than shared. This is the intended price of independence.
- Adapters become thinner; the portable logic has a single home.

## Non-Goals

- DRY across connectors, or a shared utility/HTTP module inside `connectors`.
- Putting any logic in an `__init__.py`.
- Re-implementing portable connector logic inside an adapter when the core can own it.
