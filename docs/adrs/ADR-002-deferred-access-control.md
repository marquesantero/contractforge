# ADR-002: Deferred Access Control

**Status:** Accepted
**Date:** 2026-05-13

## Context

Applying grants, row filters and column masks in Unity Catalog usually requires different permissions from the permissions needed to write data. If normal ingestion applied access directly, the data job would need elevated security privileges and an access-governance failure could obscure the result of the data load.

There is also operational risk in grant reconciliation. Revoking an undeclared permission can remove manual access created for emergency, investigation or transition purposes.

## Decision

`ingest_plan()` applies `operations` and `annotations` after the write, but leaves `access` as `DEFERRED`. Access application is handled by dedicated commands:

- `contractforge validate-access`
- `contractforge governance-check`
- `contractforge drift-check`
- `contractforge apply-access`

Revoking undeclared grants requires `revoke_unmanaged=true` in the contract and `apply-access --force-revoke` during execution.

## Consequences

- The ingestion job does not need elevated security privileges.
- The security pipeline can run with its own credentials, approvers and audit trail.
- Access failures do not stop data loads by default; they appear as governance status/report entries.
- Rollout has two steps when access must be applied: ingestion and governance.
- The harness must test access separately from the main table ingestion.
