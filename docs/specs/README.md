# ContractForge Specifications Index

This folder holds architecture contracts — not casual notes. The files define
behavior that the core and adapters must preserve, plus internal planning that
tracks release maturity.

It is a large folder, so this index groups the specs by **who needs them and
when**. To make most contributions you only need tiers 1 and 2. Treat tier 3 as
lookup material and tier 4 as maintainer-owned planning.

If you are new, read [`../architecture.md`](../architecture.md) first, then the
"Start here" specs below.

## 1. Start here — core contracts

Platform-neutral foundations every contributor should understand before
changing behavior.

- [Semantic contract](semantic-contract.md) — the immutable intent model.
- [Contract sections](contract-sections.md) — ingestion, annotations, operations, access, environment.
- [Portability boundaries](portability-boundaries.md) — what stays portable and what is platform-owned.
- [Platform capabilities](platform-capabilities.md) — how platforms declare what they support.
- [Execution plan](execution-plan.md) — the abstract plan the planner produces.
- [Evidence model](evidence-model.md) — neutral evidence record shapes.
- [Environment contract](environment-contract.md) — environment resolution rules.
- [API stability and versioning](api-stability.md) — public surface and compatibility rules.

## 2. Authoring & extending

Read these when adding or changing an adapter, source, parameter or write mode.

- [Adapter authoring](adapter-authoring.md) — the primary how-to for a new or changed adapter.
- [Source portability](source-portability.md) — adding sources without breaking the portable taxonomy.
- [Write engines](write-engines.md) — write-mode semantics and strategy.
- [Parameter defaults](parameter-defaults.md) — default resolution rules.
- [Adapter parameter policy](adapter-parameter-policy.md) — when and how adapter parameters are allowed.
- [Databricks extensions](extensions-databricks.md) — extension surface for Databricks-only behavior.
- [AWS extensions](extensions-aws.md) — extension surface for AWS-only behavior.
- [Publication packaging](publication-packaging.md) — package boundaries, exports and wheels.
- [Adapter technical review checklist](adapter-technical-review-checklist.md) — run through this before opening an adapter PR.

## 3. Reference — capability parity & mappings

Consult these when working on a specific platform. Not required reading to
start.

- [Platform contract parity](platform-contract-parity.md)
- [Control-table parity](control-table-parity.md)
- [Evidence mapping matrix](evidence-mapping-matrix.md)
- [AWS adapter](aws-adapter.md) · [AWS capability parity](aws-capability-parity.md)
- [Databricks adapter](databricks-adapter.md) · [Databricks contract parity](databricks-contractforge-parity.md)
- [GCP capability parity](gcp-capability-parity.md)
- [Snowflake capability parity](snowflake-capability-parity.md)

## 4. Internal — release planning & maturity

Maintainer-owned. These track GA criteria, waivers, stabilization and
production maturity. You do **not** need them to contribute.

- Databricks: [GA criteria](databricks-ga-criteria.md) · [GA waivers](databricks-ga-waivers.md)
- AWS: [GA criteria](aws-ga-criteria.md) · [GA waivers](aws-ga-waivers.md) · [hardening checklist](aws-adapter-hardening-checklist.md) · [stabilization matrix](aws-stabilization-matrix.md)
- Snowflake: [GA criteria](snowflake-ga-criteria.md) · [GA waivers](snowflake-ga-waivers.md) · [stabilization matrix](snowflake-stabilization-matrix.md) · [implementation plan](snowflake-adapter-implementation-plan.md) · [parity execution plan](snowflake-adapter-parity-execution-plan.md)
- Cross-adapter: [AWS and Snowflake production maturity plan](aws-snowflake-production-maturity-plan.md) · [hash-diff production benchmark runbook](hash-diff-production-benchmark-runbook.md)

---

When you add a user-visible semantic concept, update the relevant spec here
alongside the user guide, adapter docs and the tests that enforce the boundary.
See the documentation rule in [`../README.md`](../README.md).
