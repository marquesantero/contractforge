# Platform Capabilities Specification

Parameter-level parity is defined in [platform-contract-parity.md](platform-contract-parity.md). Capabilities are the runtime/planning mechanism adapters use to turn that matrix into `SUPPORTED`, `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or `UNSUPPORTED` planning results.

## Purpose

Platform capabilities describe what an adapter can preserve safely for a target runtime.

The core planner matches semantic requirements against declared capabilities instead of branching on platform names.

## Capability Declaration

An adapter declares capabilities such as:

- append support
- overwrite support
- merge support
- hash-diff change detection support
- historical support
- snapshot soft delete support
- schema evolution support
- row filter support
- column mask support
- bounded available-now streaming support
- required-column quality support
- unique-key quality support
- max-null-ratio quality support
- expression quality support
- shape support
- transform support
- evidence stores
- review-required semantics

## Capability Matching

The matcher must produce one of:

- `SUPPORTED`
- `SUPPORTED_WITH_WARNINGS`
- `REVIEW_REQUIRED`
- `UNSUPPORTED`

The result must explain blockers and warnings.

## Examples

`upsert` requires merge capability.

`hash_diff_upsert` requires merge capability and hash-diff change detection support.

`historical` requires merge capability and historical historical support.

`snapshot_reconcile_soft_delete` requires adapter-declared snapshot reconciliation support, or a review marker when the platform has a partial but not automatically equivalent implementation.

Row filters require governance capability, or a review marker when the platform has a partial or non-equivalent feature.

Expression quality rules require adapter-declared expression support, or a review marker when SQL dialect equivalence must be checked.

Shape intent requires adapter-declared shape support because structural operations can depend on nested schema, array semantics and cardinality behavior.

Transform intent without adapter-declared support returns `SUPPORTED_WITH_WARNINGS` for simple contracts because some platforms may still apply equivalent transformations in deployment tooling, but runtime execution needs explicit adapter behavior.

Production plans require at least one evidence store.
