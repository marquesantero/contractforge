# ADR-005: Adapter Parameter Policy

## Status

Accepted

## Context

ContractForge started as a Databricks adapter framework. Some concepts in the mature implementation are true ContractForge semantics, while others are Databricks-native implementation details.

The multiplatform core needs a clear rule for deciding which parameters belong to the core and which belong to adapters.

## Decision

ContractForge Core owns canonical semantic parameter names.

Adapters translate those parameters into native platform artifacts. Adapter-specific parameters must live under `environment.parameters.<adapter>`.

We will use canonical core names when a parameter name is tied to one platform. Platform-specific aliases must live in adapters or external conversion tooling, not in the core.

Initial canonical naming decisions:

- `source.type: incremental_files` is canonical; `source.type: autoloader` is not a core contract type.
- `progress_location` is canonical; `checkpoint_location` is not a core field.
- `schema_tracking_location` is canonical; `schema_location` is not a core field.
- `native_passthrough` is canonical; native connector names belong to adapter extensions or rendered artifacts.

## Consequences

Adapters may need more parameters than the core semantic contract provides. In that case they must use safe defaults, adapter extension blocks, `REVIEW_REQUIRED`, or `UNSUPPORTED`. They must not silently weaken the ContractForge intent.

Contract examples must use canonical names. Compatibility conversion belongs in adapters or external conversion tooling, not in `contractforge_core`.

Every new parameter must update the platform parity matrix and adapter parameter policy.
