# ADR-006: Environment Contract

## Status

Accepted

## Context

The core contracts describe ingestion intent, annotations, operations and access. Platform adapters also need execution context: runtime, deployment, evidence location, secrets strategy, capability requirements and adapter parameters.

Putting these values into ingestion, annotations, operations or access would mix semantic intent with environment-specific execution.

## Decision

Add a separate `environment.yaml` contract.

The environment contract contains:

- `name`
- `adapter`
- `runtime`
- `deployment`
- `evidence`
- `secrets`
- `defaults`
- `capabilities`
- `parameters.<adapter>`

It must not contain semantic fields such as `source`, `target`, `mode`, `annotations`, `operations`, `access`, `quality_rules` or `transform`.

## Consequences

The same ingestion/access/annotations/operations contracts can be planned against multiple environments.

The core validates the generic shape and rejects semantic leakage. Adapters interpret the platform-specific maps.

Adapter-specific parameter compatibility belongs in adapters or conversion tooling, not in `contractforge_core`.
