# ADR-001: Split Contracts by Responsibility

**Status:** Accepted
**Date:** 2026-05-13

## Context

A table contract covers different responsibilities: data engineering, catalog governance, operations/SRE and security. In larger organizations, those areas have different review cycles, approvers and risks. Keeping everything in a single YAML file increases merge conflicts, makes reviews harder and couples changes that could be applied independently.

## Decision

The framework supports split contracts loaded as a bundle:

- `*.ingestion.yaml`: source, target, write mode, schema policy, quality, watermark, partitioning and execution parameters.
- `*.annotations.yaml`: comments, aliases, tags, PII, deprecation and table/column metadata.
- `*.operations.yaml`: ownership, criticality, SLA, groups, runbook and operational dashboard parameters.
- `*.access.yaml`: grants, row filters, column masks and drift/reconcile policy.

`load_contract_bundle()` and `ingest_bundle()` combine those files when ingestion needs the full context. Dedicated commands validate or apply specific parts without rerunning expensive ingestion.

## Consequences

- Different teams can review different files without blocking the whole contract.
- Metadata, operations and access can evolve without changing ingestion logic.
- Drift detection becomes easier by dimension: ingestion, annotation, operation or access.
- Contract discovery becomes slightly more complex: documentation and CLI must be clear about which files belong to a bundle.
- Multi-file contracts require strong naming and versioning conventions.
