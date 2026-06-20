# Development Agents

ContractForge uses focused development agents to reduce cost without weakening architecture review.

The rule is simple: cheap agents handle deterministic work; stronger agents handle decisions.

## Agent Routing

| Agent | Model | Use For | Must Not Do |
|---|---|---|---|
| `contractforge-test-runner` | `haiku` | Run tests, builds and summarize failures. | Change source or decide semantics. |
| `contractforge-docs-parity` | `haiku` | Keep docs/examples aligned with implemented APIs. | Invent capabilities or architecture decisions. |
| `contractforge-package-validator` | `haiku` | Validate wheels, metadata, imports and dependency boundaries. | Add SDK dependencies to core. |
| `contractforge-cloud-smoke-planner` | `haiku` | Prepare and summarize bounded Databricks/AWS/Snowflake/Fabric/GCP smoke tests. | Create resources outside ContractForge runtime or hide bugs. |
| `contractforge-core-boundary-reviewer` | `sonnet` | Review platform leakage, public models and evidence ownership. | Implement broad refactors. |
| `contractforge-adapter-runtime-reviewer` | `sonnet` | Review focused adapter runtime changes. | Move adapter-specific behavior into core. |
| `contractforge-security-reviewer` | `sonnet` | Review secrets, SSRF, paths, SQL rendering and credential flows. | Treat trusted-contract assumptions as permission to leak secrets. |
| `contractforge-architecture-steward` | `sonnet` | Make public API, portability and roadmap decisions. | Skip spec/test impact analysis. |

## Model Policy

`haiku` is the default for mechanical, bounded, easily verified work:

- run tests;
- inspect generated artifacts;
- update repetitive docs tables;
- validate packaging;
- summarize cloud smoke evidence.

`sonnet` is required for work where a wrong answer can damage the product architecture:

- core versus adapter boundary decisions;
- public contract API changes;
- security review;
- write-mode semantics;
- evidence/control-table schema changes;
- adapter runtime behavior with non-trivial parity risks.

`opus` is intentionally not a default agent model. Use it only for exceptional design disputes or post-incident review where the added cost is justified.

## Quality Gate

Any change produced by a low-cost agent must be reviewed by a stronger agent when it touches:

- `src/contractforge_core`;
- `adapters/*/src/*/runtime`;
- secrets or credential handling;
- evidence/control-table schemas;
- public contract fields;
- adapter extension policy.

The minimum release path is:

1. `contractforge-test-runner` runs targeted tests.
2. `contractforge-package-validator` checks independent wheels when packaging changed.
3. `contractforge-core-boundary-reviewer` reviews core or semantic changes.
4. `contractforge-security-reviewer` reviews security-sensitive changes.
5. `contractforge-architecture-steward` resolves any public API or portability decision.

This keeps token and model cost low while preserving the main ContractForge quality constraints: no platform leakage into core, no silent semantic downgrades, and no adapter behavior that bypasses the evidence model.

## CI Cost Controls

The GitHub Actions workflow uses scoped validation for pull requests and manual runs, but keeps full validation on `main`.

| Scope | When Used | Validation |
|---|---|---|
| `full` | Every push to `main`, mixed/risky PRs, manual full runs. | Entire pytest suite plus core and all stable adapter wheel builds. |
| `docs` | PRs that only touch docs, README, site, or agent docs. | Documentation map and docs/code parity tests. |
| `aws` | PRs isolated to the AWS adapter and AWS docs/tests. | AWS tests, shared adapter-source tests, extension docs, package/version checks, AWS wheel build. |
| `databricks` | PRs isolated to the Databricks adapter and Databricks docs/tests. | Databricks tests, shared adapter-source tests, extension docs, package/version checks, Databricks wheel build. |
| `snowflake` | PRs isolated to the Snowflake adapter and Snowflake docs/tests. | Snowflake adapter tests, package/version checks, Snowflake wheel build. |
| `fabric` | PRs isolated to the Fabric adapter and Fabric docs/tests. | Fabric adapter tests, source-expansion checks, package/version checks, Fabric wheel build. |
| `gcp` | PRs isolated to the GCP adapter and GCP docs/tests. | GCP adapter tests, BigQuery capability checks, package/version checks, GCP wheel build. |
| `package` | PRs isolated to packaging metadata. | Publication/version tests plus all wheel builds. |
| `smoke` | Manual dispatch or agent/config-only checks. | Boundary, security, packaging, documentation map and adapter architecture tests. |

Core changes intentionally do **not** get a narrow test tier. Any change under `src/contractforge_core` or mixed package changes falls back to `full`, because core semantics can affect every adapter.

The workflow also cancels obsolete in-progress runs for the same branch. This saves CI minutes without changing the validation result that matters: the newest commit on a branch.
