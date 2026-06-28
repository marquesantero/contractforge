# Adapter Authoring Guide

## Purpose

This document defines the public ContractForge Core API and behavioral contract required to build a fully functional platform adapter.

The target reader is an engineer building adapters such as:

- `contractforge-aws`
- `contractforge-fabric`
- `contractforge-snowflake`
- `contractforge-gcp`
- future private/client-specific adapters

An adapter is not a fork of ContractForge Core. It is a platform implementation that consumes core contracts, declares platform capabilities, translates abstract plans into native artifacts, optionally executes them, and persists evidence.

## Adapter Responsibilities

An adapter must provide these surfaces:

| Surface | Required | Purpose |
| --- | --- | --- |
| Capability declaration | Yes | Tell the core planner which ContractForge semantics the platform can preserve. |
| Planning bridge | Yes | Run core planning against adapter capabilities and add adapter-specific warnings/blockers when needed. |
| Artifact rendering | Yes | Produce native SQL, job definitions, scripts, pipeline JSON, Terraform, review Markdown, or equivalent. |
| Evidence mapping | Yes | Persist or render evidence/control-table structures for runs, state, quality, errors, lineage, access and operations. |
| Runtime execution | Optional but expected for production adapters | Execute the rendered/translated plan using injected platform clients or runtime handles. |
| Source translation | Expected | Translate core source contracts into native reads, jobs, copy operations, queries or review artifacts. |
| Source support catalog | Expected | Publish adapter-owned support metadata for each source family, including native mapping, status and review notes. |
| Governance translation | Expected for governed platforms | Translate annotations, operations and access contracts to native metadata/security controls. |
| CLI integration | Required for packaged adapters | Expose the canonical adapter command vocabulary from `docs/cli.md`; keep platform-specific options under those commands. Generic validation/schema/init remain core concerns. |

Adapters must not require the core to import platform SDKs.

## Public Core APIs To Use

Adapter authors should treat the following modules as the stable public surface.

| API | Import | Use |
| --- | --- | --- |
| Adapter protocol | `contractforge_core.adapters` | Implement `PlatformAdapter` and return `RenderedArtifacts`. |
| Capability model | `contractforge_core.capabilities` | Declare `PlatformCapabilities`. |
| Planner | `contractforge_core.planner` | Call `plan_contract(contract, capabilities)`. |
| Planning result models | `contractforge_core.planner` | Return `PlanningResult`, `PlanningBlocker`, `PlanningWarning`, `ExecutionPlan`. |
| Semantic model | `contractforge_core.semantic` | Consume immutable `SemanticContract` and intents. |
| Contract parsing/validation | `contractforge_core.contracts` | Validate YAML/Python mappings and normalize via `semantic_contract_from_mapping`. |
| Bundle composition | `contractforge_core.contracts` | Use `load_contract_bundle` and `compose_contract_sections`. |
| Source metadata | `contractforge_core.connectors` | Use source taxonomy, redacted metadata and portability diagnostics. |
| Schema diff | `contractforge_core.schema` | Compare schemas and validate `strict`, `additive_only`, `permissive`. |
| Quality results | `contractforge_core.quality` | Return normalized `QualityRuleResult` and aggregate status. |
| Runtime neutral models | `contractforge_core.runtime` | Use `PreparedInput`, `QuarantineReference`, `QueryOne` when useful. |
| Evidence records | `contractforge_core.evidence` | Use neutral record shapes when rendering adapter evidence. |
| Execution outcome | `contractforge_core.execution` | Return `ExecutionOutcome` from runtime write helpers. |
| Security/redaction | `contractforge_core.security` | Redact source/auth/runtime metadata before evidence. |
| Naming/watermark helpers | `contractforge_core.naming`, `contractforge_core.watermark` | Use portable naming and typed watermark helpers. |

Do not import adapter packages from core. Adapter packages may import core.

## Minimal Adapter Protocol

The core adapter protocol is intentionally small:

```python
from contractforge_core.adapters import PlatformAdapter, RenderedArtifacts
from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import PlanningResult, plan_contract
from contractforge_core.semantic import SemanticContract


class MyPlatformAdapter:
    name = "my-platform"

    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            platform=self.name,
            supports_append=True,
            supports_overwrite=True,
            supports_merge=True,
            evidence_stores=("audit_tables",),
        )

    def plan(self, contract: SemanticContract) -> PlanningResult:
        return plan_contract(contract, self.capabilities())

    def render_contract(self, contract: SemanticContract) -> RenderedArtifacts:
        return RenderedArtifacts(
            artifacts={
                "review.md": "...",
                "job.sql": "...",
            }
        )
```

A production adapter will usually add methods around this protocol, such as `ingest_bundle()`, `apply_access_contract()` or `execute_plan()`. Those methods are adapter-owned and must not be required by the core.

## Capability Declaration Contract

Capabilities are the adapter's promise to the core. They must be conservative.

```python
PlatformCapabilities(
    platform="snowflake",
    supports_append=True,
    supports_overwrite=True,
    supports_merge=True,
    supports_hash_diff=True,
    supports_scd2=False,
    supports_snapshot_reconcile_soft_delete=False,
    supports_schema_evolution=True,
    supports_row_filters=True,
    supports_column_masks=True,
    supports_available_now_streaming=False,
    supports_expression_quality=True,
    supports_shape=False,
    supports_transform=True,
    evidence_stores=("audit_tables",),
    review_required_semantics=("historical", "snapshot_reconcile_soft_delete"),
)
```

Rules:

1. Declare `supports_* = True` only when the adapter can preserve the ContractForge semantics.
2. Use `review_required_semantics` when the platform may support the concept but equivalence depends on design.
3. Use `supported_custom_write_modes` only for explicit adapter-registered `custom:<name>` handlers.
4. Production adapters must provide at least one `evidence_stores` value.
5. Never set a capability to true only because the platform has a similar feature with different behavior.

## Planning Result Semantics

Adapters must preserve the four planning statuses:

| Status | Meaning | Adapter behavior |
| --- | --- | --- |
| `SUPPORTED` | Contract can be mapped with equivalent behavior. | Render/execute normally. |
| `SUPPORTED_WITH_WARNINGS` | Contract can run, but non-breaking caveats exist. | Render warnings into review artifacts and evidence. |
| `REVIEW_REQUIRED` | Safe execution requires a human/platform design decision. | Render review artifacts; do not execute automatically unless user explicitly allows it. |
| `UNSUPPORTED` | Required semantics cannot be preserved. | Do not render executable artifacts as if supported. |

Adapters may add platform-specific blockers/warnings after core planning, but they must not downgrade silently.

## Contract Sections Adapters Must Understand

The core owns the complete ContractForge contract vocabulary. Adapters conform to it.

| Section | Adapter obligation |
| --- | --- |
| `ingestion` | Translate source, target, write mode, schema policy, quality, shape and transform. |
| `annotations` | Map table/column descriptions, tags, aliases, PII and lifecycle metadata where supported. |
| `operations` | Persist or render owner, SLA, criticality, runbook and operational metadata. |
| `access` | Map grants, row filters, column masks and drift policy, or return review/unsupported. |
| `environment` | Read adapter, evidence location and adapter parameters. Never mix ingestion semantics into environment. |

Adapters must reject or warn on contracts whose `environment.adapter` targets another platform.

## Source Translation Requirements

The core source taxonomy is the starting point:

| Source family | Core examples | Adapter obligation |
| --- | --- | --- |
| Catalog/lakehouse | `table`, `delta_table`, `iceberg_table`, `view`, `sql` | Map to native table/query reads or review if unsupported. Resolve core logical refs (`source.ref`, `source.table_ref`, `{{ table_ref:layer.table }}`) to platform-native qualified names inside the adapter. |
| Files | `csv`, `json`, `parquet`, `delta`, `orc`, `text`, `avro`, `xml` | Map formats to native readers, preserving schema and options. |
| Object storage | `s3`, `adls`, `azure_blob`, `gcs`, `object_storage` | Map paths and credentials without leaking SDK details into core. |
| Incremental files | `incremental_files` | Map to platform file-tracking mechanism, e.g. Auto Loader, Glue bookmarks, Dataflow pattern, or review. |
| HTTP file | `http_file`, `http_csv`, `http_json`, `http_text` | Support bounded fetch or render review/native task. |
| JDBC batch | `jdbc`, `postgres`, `mysql`, `sqlserver`, `oracle`, `redshift`, `db2`, etc. | Map URL/table/query/partitioning/auth; document driver responsibilities. |
| Bounded streams | `kafka_bounded`, `eventhubs_bounded` | Implement catch-up replay only unless adapter has explicit streaming design. |
| Native passthrough | `native_passthrough` | Render native connector/service artifacts and review evidence. |

Platform-specific names, such as `autoloader`, must not become core input. Conversion tooling may rewrite them before validation.

Adapters should expose a small source-support catalog so users and tooling can
inspect what a platform can do without reading renderer internals. The catalog
is adapter-owned and must not be imported by the core.

Recommended public shape:

```python
def <adapter>_source_support(source: dict | str) -> dict:
    return {
        "adapter": "<adapter>",
        "source_type": "incremental_files",
        "status": "SUPPORTED",  # or REVIEW_REQUIRED / UNSUPPORTED
        "native_mapping": "Auto Loader cloudFiles",
        "note": "Uses core incremental_files/file_stream intent.",
    }


def list_<adapter>_source_support() -> tuple[dict, ...]:
    ...
```

`contractforge_databricks.sources.list_databricks_source_support()` and
`contractforge_aws.sources.list_aws_source_support()` are the reference
implementations. They classify the same core source vocabulary differently:
Databricks maps `incremental_files` to Auto Loader, while AWS maps eligible
`incremental_files` contracts to Glue job bookmarks and returns
`REVIEW_REQUIRED` when bookmark semantics cannot be preserved.

Adapter extension keys must be allowlisted by the adapter. Unknown keys must
emit a planning warning and must not be honored silently. The reference warning
codes are `DATABRICKS_UNKNOWN_EXTENSION` and `AWS_UNKNOWN_EXTENSION`.

## Write Mode Requirements

Adapters must explicitly classify each write mode.

| Write mode | Adapter requirement |
| --- | --- |
| `append` | Append rows without reconciling target. |
| `overwrite` | Replace target or declared target scope atomically enough for the platform. |
| `upsert` | Update current state by stable keys; requires merge/upsert semantics. |
| `hash_diff_upsert` | Preserve ContractForge row-hash semantics and latest-target comparison. |
| `historical` | Preserve history rows, current-row marker, validity windows and late-arriving policy. |
| `snapshot_reconcile_soft_delete` | Reconcile complete snapshot and mark missing keys inactive/deleted. |
| `custom:<name>` | Execute only through adapter-registered explicit handlers. |

Adapters must never fall back from `historical` to append, from merge to append, or from snapshot reconciliation to overwrite without a blocker/review result.

## Schema, Shape And Transform

Adapters should use core schema helpers for neutral diffing:

- `compare_schema(source_schema, target_schema, allow_type_widening=...)`
- `validate_schema_diff(diff, policy)`

The adapter owns physical inspection and DDL/API application.

Shape and transform are semantic ContractForge intent:

- parse JSON
- flatten
- array handling
- zip arrays
- cast
- derive
- standardize
- deduplicate
- composite keys

If the platform cannot execute a shape/transform step natively or through its runtime, the adapter must return `REVIEW_REQUIRED` or render a materialization artifact.

## Quality Requirements

Core quality intents include:

- required columns
- not null
- unique key
- accepted values
- row count minimum
- max null ratio
- expression
- custom opaque rules

Adapters must:

1. Evaluate supported quality rules or render native SQL/review artifacts.
2. Return `QualityRuleResult` with normalized status/severity/counts.
3. Respect contract-level `on_quality_fail`.
4. Persist quality evidence.
5. Preserve quarantine behavior when severity is `quarantine`, or return a blocker/review result.

Custom quality rule registries are adapter-owned because they may depend on SQL dialects, DataFrames or platform APIs.

## Governance Requirements

Adapters should support these contracts when the platform has equivalent controls:

| ContractForge concept | Adapter mapping examples |
| --- | --- |
| Table/column descriptions | Catalog comments, metadata API, data catalog descriptions. |
| Tags and aliases | Native tags, labels, policy tags, classification metadata. |
| PII/sensitivity | Tags, policy taxonomy, masking-policy review or security catalog. |
| Grants | Native GRANT/IAM/Lake Formation/Fabric permissions. |
| Row filters | Row access policies, data filters, security policies. |
| Column masks | Masking policies, policy tags, column-level security. |
| Drift/revoke unmanaged | Compare declared/current state and require explicit destructive confirmation. |

If security inheritance or policy semantics differ, return `REVIEW_REQUIRED`.

## Evidence And Control Tables

Every production adapter must document its persistence strategy for the evidence model.

The canonical evidence concepts are:

- run
- state
- lock/idempotency guard
- quality result
- quarantine reference
- error
- schema change
- stream/bounded replay summary
- lineage event
- annotation application
- access/governance application
- operations metadata
- diagnostics/explain
- cost signal
- framework/source metadata

The Databricks adapter uses Delta control tables with `ctrl_ingestion_*` names. Other adapters may use Iceberg, BigQuery, Snowflake audit tables, Fabric Lakehouse tables, object-store artifacts or native state stores. The semantic fields remain the same.

At minimum, production adapters must provide:

| Evidence surface | Minimum requirement |
| --- | --- |
| Run ledger | Queryable run records with status, source, target, mode, metrics, timestamps and error summary. |
| State | Last successful watermark/state by target. |
| Errors | Redacted error message and diagnostic detail. |
| Quality | Rule-level results. |
| Schema changes | Detected/applied drift evidence. |
| Source metadata | Redacted source details and connector capability metadata. |
| Governance evidence | Required when adapter applies annotations/access/operations. |

Adapters must redact secrets before persistence.

## Environment Contract

The environment contract selects execution context and adapter parameters.

```yaml
environment:
  name: prod
  adapter: snowflake
  evidence:
    database: AUDIT
    schema: CONTRACTFORGE
  runtime:
    kind: warehouse
  parameters:
    snowflake:
      warehouse: INGEST_WH
      query_tag_prefix: contractforge
```

Rules:

1. `environment.adapter` must match the adapter package.
2. `environment.evidence` tells the adapter where to store evidence.
3. `environment.parameters.<adapter>` is the adapter-owned native parameter map.
4. Environment must not contain source, target, mode, quality, annotations, operations or access semantics.
5. Adapters must ignore parameter blocks for other adapters.

## Rendering Artifacts

Adapters should render both executable and review artifacts.

Recommended artifact categories:

| Artifact | Examples |
| --- | --- |
| Review report | Markdown explaining plan status, warnings, blockers and portability boundaries. |
| Capability evidence | JSON capability declaration and runtime evidence. |
| Source artifacts | SQL/read scripts, connector configs, copy job definitions. |
| Write artifacts | SQL MERGE, COPY, pipeline steps, job scripts. |
| Evidence DDL | Audit/control table DDL or storage layout. |
| Governance artifacts | Grants, tags, policies, row filters, masks. |
| Deployment artifacts | Databricks Asset Bundle, Glue job script, Fabric pipeline JSON, Terraform. |

Rendering must not imply execution when planning status is `REVIEW_REQUIRED` or `UNSUPPORTED`.

## Runtime Execution Pattern

Runtime execution should be adapter-owned and dependency-injected.

Recommended pattern:

```python
def ingest_platform_contract(
    contract: dict | SemanticContract,
    *,
    runner: PlatformRunner,
    options: PlatformIngestOptions | None = None,
    query_one: QueryOne | None = None,
) -> dict:
    ...
```

Rules:

- Accept `SemanticContract` or validated mapping.
- Normalize mappings with `semantic_contract_from_mapping`.
- Plan before execution.
- Require explicit override before executing `REVIEW_REQUIRED` plans.
- Use injected runners/clients instead of importing global sessions at package import time.
- Persist run/error evidence even on failure when possible.
- Return a structured result compatible with core failure handling.

## Suggested Package Layout

Adapters should stay modular and avoid god files.

```text
contractforge_<platform>/
  __init__.py
  adapter.py
  api.py
  environment.py
  capabilities/
    models.py
    evaluate.py
    mapping.py
  sources/
    artifacts.py
    runtime.py
  execution/
    append.py
    overwrite.py
    merge.py
    scd2.py
    snapshot.py
    results.py
  schema/
    diff.py
    sync.py
  quality/
    evaluation.py
    sql.py
    registry.py
  governance/
    annotations.py
    access.py
    drift.py
  evidence/
    schemas.py
    ddl.py
    writer.py
  runtime/
    orchestrator.py
    options.py
    finalization.py
  rendering/
    markdown.py
    bundle.py
  tests/
```

Adapter modules should be separated by domain: source, execution, governance, evidence, runtime, rendering, capabilities and CLI.

## Packaging And Publication

Each adapter is published as its own Python distribution. The adapter wheel depends on `contractforge-core`; the core wheel never depends on or packages adapters.

For example, `contractforge-databricks` owns `contractforge_databricks` and the `contractforge-databricks` console script. It must not be bundled into the `contractforge-core` wheel.

Adapter packaging rules are defined in [publication-packaging.md](publication-packaging.md).

## Testing Requirements For A Functional Adapter

A minimally credible adapter needs pure tests for planning and rendering, plus runtime tests with fake runners.

Required test groups:

| Test group | Required cases |
| --- | --- |
| Core boundary | Adapter imports core; core never imports adapter. |
| Capability planning | append, overwrite, merge, historical/review, governance support and evidence requirement. |
| Contract parsing | ingestion, annotations, operations, access and environment. |
| Source rendering | catalog, files/object storage, JDBC, HTTP/native passthrough where supported. |
| Write rendering/execution | all declared write modes and no silent fallback. |
| Schema policy | strict, additive, type widening and blocker paths. |
| Quality | pass/fail/warn/quarantine evidence. |
| Governance | annotations, grants, row filters/masks or review-required. |
| Evidence DDL | every canonical evidence concept is represented or explicitly documented as review/unsupported. |
| Redaction | secrets and sensitive URLs are not persisted in evidence. |
| Failure handling | errors create evidence and return/raise consistently. |

## Documentation Requirements

Each adapter must ship documentation for:

1. Supported ContractForge semantics.
2. Platform capability matrix.
3. Contract parameter mapping.
4. Evidence/control-table mapping.
5. Source connector support.
6. Write mode behavior and limitations.
7. Governance/access behavior.
8. Runtime prerequisites and credentials.
9. Known review-required semantics.
10. Unsupported semantics.

For enterprise use, do not rely only on examples. Include explicit tables showing how every canonical ContractForge concept maps to the platform.

## Adapter Acceptance Checklist

An adapter is considered functional when:

- It implements `PlatformAdapter`.
- It declares conservative `PlatformCapabilities`.
- It can plan a canonical `SemanticContract`.
- It renders review artifacts for every planning result.
- It renders or creates evidence storage.
- It maps all supported write modes without silent downgrade.
- It can persist a run ledger, errors, quality results and schema changes.
- It documents unsupported/review-required semantics.
- It has tests proving core remains platform-free.
- It exposes public APIs without requiring platform runtime imports at package import time.

## Adapter Maturity Levels

Functional and stable are different claims. Use these maturity levels when
documenting an adapter:

| Level | Meaning | Required evidence |
| --- | --- | --- |
| Render-only | Produces review/native artifacts but does not execute platform jobs. | Planning/rendering tests and review artifacts. |
| Runnable | Executes simple contracts with adapter-owned runtime code. | Fake-runner tests and at least one real runtime smoke test. |
| Validated | Runs representative sources, writes, quality checks and evidence paths end to end. | Repeatable end-to-end evidence using contracts and documented environment bindings. |
| Stable | Has an explicit supported surface, repeated successful evidence, failure handling, redaction and documented review boundaries. | Public capability matrix, real evidence records and no silent semantic downgrade. |
| Production-certified | Adds operational runbooks, cost attribution, security review, support policy and upgrade guarantees. | Operational evidence, security sign-off and support/rollback process. |

Stable does not mean every platform feature is implemented. It means the
documented supported surface is explicit, tested, repeatable and honest about
unsupported or review-required behavior.

## Platform-Specific Starting Points

| Platform | Likely native artifacts | High-risk semantics |
| --- | --- | --- |
| AWS | Glue jobs, EMR Serverless scripts, Iceberg tables, Lake Formation grants, S3 audit artifacts, Terraform. | historical equivalence, locks/state, row filters, schema evolution, streaming semantics. |
| Fabric | Data Pipelines, Lakehouse tables, Dataflow Gen2, OneLake paths, Purview/Fabric metadata. | Merge/SCD behavior, masks/filters, pipeline idempotency, streaming and cost attribution. |
| Snowflake | SQL scripts, tasks, streams, warehouses, masking policies, row access policies, audit tables. | Snapshot soft delete semantics, historical late-arriving policy, source connectors, cost attribution by query/task. |
| GCP | BigQuery SQL/jobs, GCS load jobs, BigLake Iceberg tables, raw Iceberg BigLake registration command/readback, BigQuery evidence tables, schema-policy planning and live bounded enforcement, advanced write-mode review artifacts, row access policies, data policies, policy tags, governance ledger/reconciliation planning, non-mutating governance reconciliation readback, evidence write/readback, Dataplex data-quality create plus execution/readback planning, explicit Dataplex lineage/aspect command execution/readback and a certified Google Workflows deployment runner. | Streaming, advanced write modes, automatic type widening/mutation, automatic Dataplex lineage/aspect emission during every contract run, non-Workflows deployment runners, direct raw Iceberg path execution without registration, governance auto-repair/delete and overwrite-retention certification remain outside the scoped stable surface until separately certified. |

The correct adapter behavior is not "make it work somehow". It is to preserve semantics, warn, require review or reject clearly.
