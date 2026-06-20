# Adapter CLI Reference

ContractForge adapters expose a shared command vocabulary so users do not need
to learn a different tool shape for each platform. Adapter-specific flags are
allowed, but the main command names and meanings should stay consistent.

Use the adapter package for the target runtime:

| Platform | CLI |
| --- | --- |
| Databricks | `contractforge-databricks` |
| AWS | `contractforge-aws` |
| Snowflake | `contractforge-snowflake` |
| Fabric | `contractforge-fabric` |
| GCP | `contractforge-gcp` |

## Standard Commands

| Command | Purpose |
| --- | --- |
| `plan` | Load contracts, validate semantics and return adapter capability status. |
| `render` | Generate native SQL, scripts, manifests or review artifacts without executing them. |
| `deploy` | Publish or register native runtime artifacts for a single contract when the adapter supports it. |
| `deploy-project` | Render and optionally deploy an ordered project from `project.yaml`. |
| `run` | Execute an already deployed or directly runnable contract path when supported. |
| `smoke` | Run a bounded adapter-owned validation scenario. |
| `cost-report` | Render or read platform cost evidence where available. |
| `cleanup-plan` | Produce a reviewed cleanup plan without deleting resources by default. |
| `stabilization-report` | Report stable-surface gates, review boundaries and remaining promotion gates. |

Some adapters expose extra commands when the feature is genuinely native to
that platform, such as `sources`, `performance-report`, `source-promotion` or
governance apply/readback helpers. Those commands must not replace the standard
planning, rendering, deployment and evidence vocabulary.

## Common Flags

| Flag | Meaning |
| --- | --- |
| `--environment` | Environment contract that owns runtime, evidence, artifact and credential binding. |
| `--output-dir` | Directory for generated artifacts and review files. |
| `--dry-run` | Validate/render without performing remote mutation. |
| `--run` | Execute after deploy/render when the adapter command supports it. |
| `--wait` | Wait for remote execution to reach a terminal state. |
| `--readback` | Query native evidence or metadata after execution. |
| `--strict-final` | Fail when a stable-final gate is not closed. |

## Adapter Entry Points

```bash
contractforge-databricks stabilization-report --strict-final
contractforge-aws stabilization-report --strict-final
contractforge-snowflake stabilization-report --strict-final
contractforge-fabric stabilization-report --strict-final
contractforge-gcp stabilization-report --strict-final
```

## Standard Workflow

Plan one contract:

```bash
contractforge-<adapter> plan path/to/contract.ingestion.yaml --environment path/to/environment.yaml
```

Render native artifacts:

```bash
contractforge-<adapter> render path/to/contract.ingestion.yaml --environment path/to/environment.yaml --output-dir .contractforge/out
```

Deploy or run an ordered project through the adapter-owned command path:

```bash
contractforge-aws deploy-project examples/real-world/usgs-earthquake-rest-medallion/project.yaml --run --wait
contractforge-gcp deploy-project examples/real-world/usgs-earthquake-rest-medallion/project.yaml --deploy-orchestration --run-orchestration --wait-orchestration --readback-orchestration
```

Project execution should use the project contract and adapter CLI, not
hand-written runtime workarounds.

## Rules

- Keep source, target, write mode, quality and governance semantics in contracts.
- Keep credentials, artifact locations, warehouses, pools and native IDs in environment files.
- Do not silently downgrade unsupported semantics.
- Prefer `SUPPORTED_WITH_WARNINGS` or `REVIEW_REQUIRED` over hiding platform differences.
- Persist or read back evidence for real execution whenever the adapter claims runtime maturity.
