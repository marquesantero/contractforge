# ADR-004: Source Portability and Connector Scope

## Status

Accepted

## Context

ContractForge keeps connector support focused on portable primitives. That is useful for a multiplatform core because adapter-specific connectors can evolve without expanding the core boundary.

The core should maintain only connector intent that is portable, stable, and low-maintenance. Platform-native and SaaS-specific ingestion should be represented as native passthrough or adapter-specific extension behavior.

## Decision

ContractForge Core will classify source types into:

- portable built-in
- native passthrough
- bounded stream
- unsupported

The core will use a generic `incremental_files` source type instead of the Databricks-specific `autoloader` name. Platform-specific aliases remain outside runtime contracts and may be handled only by explicit conversion tooling.

Kafka and Event Hubs are supported only as bounded catch-up/replay intent in the core through `kafka_bounded` and `eventhubs_bounded`. Continuous streaming is not part of the core execution model.

OData, SAP OData, SaaS connectors, drives, and legacy protocols move to `native_passthrough` unless an adapter explicitly implements them.

Oracle remains in the JDBC family, but adapters must require the user to provide the Oracle JDBC driver.

## Consequences

The connector surface becomes smaller and more maintainable.

Adapters can still use native platform strengths:

- Databricks Auto Loader for `incremental_files`
- Lakeflow Connect for SaaS passthrough
- AWS AppFlow/DMS/Glue for passthrough
- Fabric Dataflow Gen2 for passthrough

Unsupported or non-portable sources are reported explicitly instead of failing late at runtime.

## Non-Goals

- Continuous streaming semantics in the core.
- Maintaining custom SaaS connectors for every proprietary API.
- Redistributing restricted JDBC drivers such as Oracle `ojdbc`.
