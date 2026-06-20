# ADR-003: Portable vs Platform-Specific Semantics

## Status

Accepted

## Context

Some ingestion concepts are portable across platforms, while others only look similar but differ in behavior.

Silent fallback would make ContractForge Core unsafe for consulting and governed delivery.

## Decision

Every semantic concept must be classified as portable, platform-specific, supported with warnings, review required, or unsupported.

The planner must return explicit planning results with warnings and blockers.

## Consequences

The project will favor accurate planning over optimistic portability claims.

New semantic concepts require:

- a spec update
- tests
- capability mapping
- adapter behavior or blocker

