# Architecture Decision Records

This directory records architecture decisions that explain ContractForge product and engineering choices.

Format:

- **Status:** proposed, accepted, superseded or removed.
- **Context:** the problem that motivated the decision.
- **Decision:** the adopted choice.
- **Consequences:** positive effects, costs and constraints.

## ADRs

| ADR | Status | Decision |
| --- | --- | --- |
| [ADR-001](ADR-001-split-contracts-by-responsibility.md) | Accepted | Split contracts by responsibility: ingestion, annotations, operations and access. |
| [ADR-002](ADR-002-deferred-access-control.md) | Accepted | Do not apply access governance inside normal ingestion. |
| [ADR-003](ADR-003-snapshot-soft-delete-sql-merge.md) | Accepted | Implement `snapshot_soft_delete` with SQL `MERGE` and reject partial sources. |
