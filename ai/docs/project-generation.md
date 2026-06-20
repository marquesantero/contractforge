# Project Generation Core

ContractForge AI uses a normalized project plan model before writing any generated files. This keeps project generation reviewable, testable and safe.

The project generation core provides a shared artifact model and writer that target-specific generators can reuse.

If the scenario is still written as plain language, start with `plan-project` before generating files:

```bash
contractforge-ai plan-project \
  --intent "Create a silver ingestion from s3a://landing/orders into main.silver.orders using hash_diff_upsert." \
  --schema schemas/orders.json \
  --format markdown
```

`plan-project` recommends one or more `generate-project` commands and reports missing decisions. See [Natural-Language Project Planning](project-planning.md).

Supported generation targets:

| Target | Purpose |
| --- | --- |
| `contractforge-yaml` | Canonical split ContractForge contracts plus project metadata. |
| `contractforge-python` | Thin Python wrapper around ContractForge validation and adapter planning/execution boundaries. |
| `databricks-dab` | Databricks Asset Bundle scaffold that runs the generated contracts through `contractforge-databricks`. |
| `aws-glue-iceberg` | AWS Glue Spark + Iceberg scaffold that deploys the generated contracts through `contractforge-aws`. |
| `dbt` | Downstream dbt source/model/test starter over ContractForge-managed tables. |
| `classic-pyspark` | Migration comparison scaffold, not the preferred governed production path. |

When the user wants one command that plans and scaffolds, use `guided-project`:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders." \
  --schema schemas/orders.json \
  --target contractforge-yaml \
  --output-dir ./generated/orders
```

`guided-project` refuses to write files while required decisions remain unresolved unless `--allow-review-required` is passed. That makes it suitable for guided onboarding while preserving the same review boundary as the lower-level planner and generator commands.

## AI-First Guided Generation

`guided-project --with-ai` uses the provider before artifact generation. This is different from post-generation advisory enrichment: the provider can improve a structured project specification, and validated updates can affect the generated files.

The flow is:

1. Build deterministic intent and context evidence.
2. Convert the planner result into an `EnrichedProjectSpec`.
3. Ask the provider for structured `field_updates` through `project.spec.enrichment.v1`.
4. Validate the provider response locally.
5. Apply only allowlisted field updates that preserve deterministic/user-provided intent.
6. Generate artifacts from the enriched specification.
7. Render the rich HTML review with the original intent, enriched fields, generated artifacts, validation and unresolved decisions.

Example:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/events into main.bronze.b_events. The endpoint returns nested JSON payloads." \
  --schema schemas/events.json \
  --target contractforge-yaml \
  --with-ai \
  --provider openai \
  --language pt-BR \
  --allow-review-required \
  --output-dir ./generated/events
```

`--language` is intentionally provider-backed and applies after the English review is rendered. The provider translates narrative prose in `AI_REVIEW.html` while labels, statuses, identifiers, file paths, commands and code remain in English. This keeps reports useful for local readers without changing the technical vocabulary used in contracts, CI and support tickets.

Provider suggestions can be applied to generated artifacts when they stay inside the supported project-spec surface:

| Field | How it can affect generated artifacts |
| --- | --- |
| `source_format` | Sets `source.format` in generated ingestion contracts. |
| `transform` | Writes the full ContractForge `transform` block. This is the canonical path for any supported transformation, including `shape.parse_json`, `shape.flatten`, `shape.explode` and `shape.columns`. |
| `shape` | Backward-compatible shortcut for shape-only suggestions. Prefer `transform` for new provider outputs. |
| `quality_rules` | Merges provider-suggested draft quality rules into `quality_rules`. |
| `annotations` | Merges draft table/column descriptions, tags and metadata into `.annotations.yaml`. |
| `operations` | Merges operational ownership, criticality and runbook draft metadata into `.operations.yaml`. |
| `selected_target`, `connector`, `source_path`, `target_*`, `layer`, `mode` | Can fill unresolved planner placeholders only. Provider-filled identity fields stay review-required. Provider attempts to change deterministic or user-provided values are rejected and audited. |

Provider suggestions that can change generated contract behavior are deliberately stricter than simple low-risk hints. ContractForge AI may preserve provider-suggested `transform`, `shape`, `quality_rules`, `annotations`, `operations` or `dab_compute` fields in generated draft artifacts so reviewers can inspect the concrete contract syntax, but it always records those fields as `requires_review`. A provider cannot mark those fields as production-ready because they can change schema, values, row cardinality, governance metadata, quality enforcement, operational ownership or runtime behavior.

Critical business decisions remain explicit review items. The provider may suggest them, but ContractForge AI keeps them review-required:

- `merge_keys`
- `hash_columns`
- owner or stewardship accountability
- SLA and escalation policy
- delete semantics
- legal PII policy
- production credentials or secret values

If provider output is invalid, unavailable, outside the allowlist or conflicts with deterministic identity, generation falls back to the deterministic specification and records the enrichment status instead of silently using the model output. Unsupported transformation enrichment fields, such as runtime secrets or platform deployment settings, are rejected and recorded in the provider proposal audit; they are not written into generated contracts.

## AI_REVIEW.html as the Main Review Surface

Guided generation consolidates review material into
`AI_REVIEW.html`. The report is designed for approval, handoff and screenshots:
it shows the interpreted request, selected target, generated artifacts,
required decisions, context evidence, traceability, deterministic validation,
critique and provider guidance in one structured page.

Markdown and JSON remain useful for automation, but the HTML report should be
the default artifact for reviewing generated projects. This avoids a
project directory full of disconnected review notes and makes it clearer which
decisions must be resolved before generated files are used.

The generated report has the same visual system across:

- intent-first `generate` outputs;
- `guided-project` outputs;
- direct `project-plan` and `generate-project` review outputs;
- `validate-project-structure --format html` project validation reports;
- operational analysis reports.

`validate-project-structure --format html` renders long findings and adapter
evidence as cards. This matters for real projects because adapter warning
codes, contract paths and planner payloads are too long for fixed-width tables.
The HTML report keeps `READY_WITH_WARNINGS` visible without making warning-only
projects look invalid.

When an explicit schema/profile file is not available yet, guided generation can build a deterministic context package from local samples:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from /landing/orders into main.bronze.b_orders." \
  --context-dir samples/orders \
  --runtime databricks-serverless \
  --target contractforge-yaml \
  --allow-review-required \
  --output-dir ./generated/orders
```

The context package currently inspects JSON, JSONL/NDJSON and CSV samples. If it can infer a schema profile from a supported sample, the generated project includes:

- `CONTEXT.md`: readable context summary and review notes.
- `context/context-package.json`: machine-readable evidence package.
- `context/inferred-schema-profile.yaml`: inferred schema profile used for generation when `schema_path` was not provided.

This inference is deliberately conservative. A sample file can suggest columns and basic types, but it cannot prove optional fields, source completeness, business keys or governance ownership.

## Patch Existing Projects Safely

When a project already exists, ContractForge AI should not blindly regenerate
everything. Patch planning represents file changes before they are written, so
the user can review what would be created, skipped or considered a conflict.

Use this pattern when the user asks to complete a project from a known final
table, add missing sibling contracts, or generate only the missing bronze,
silver or gold layers.

Patch planning keeps these boundaries:

| Boundary | Behavior |
| --- | --- |
| Existing files | Preserved by default. |
| Review artifacts | Protected from unsafe overwrite. |
| Missing siblings | Can be generated selectively. |
| Ambiguous changes | Kept as review-required decisions. |
| File paths | Must stay relative to the output directory. |

This is the preferred path for "complete what is missing" workflows. It keeps
the existing repository as evidence instead of treating every prompt as a new
greenfield project.

For repeatable guided workflows, store the guided inputs in a requirements file and keep it under review with the generated project:

```yaml
intent: Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders.
schema_path: schemas/orders.json
# Or use context_dir when schema_path is not available yet.
# context_dir: samples/orders
runtime: databricks-serverless
default_catalog: main
default_schema: bronze
default_layer: bronze
preferred_target: contractforge-yaml
allow_review_required: false
```

Generate from that file:

```bash
contractforge-ai guided-project \
  --requirements requirements/orders-project.yaml \
  --output-dir ./generated/orders
```

Supported requirements fields:

- `intent`: natural-language ingestion scenario.
- `schema_path`: schema/profile path used by the generated contract and metadata drafts.
- `context_dir`: directory with local sample files used to build a context package when `schema_path` is not provided.
- `runtime`: target runtime hint such as `databricks-serverless`, `databricks-classic` or `local`.
- `default_catalog`: target catalog fallback when the intent does not state one.
- `default_schema`: target schema fallback when the intent does not state one.
- `default_layer`: ContractForge layer fallback when the intent does not state one.
- `preferred_target`: one of `contractforge-yaml`, `contractforge-python`, `databricks-dab`, `aws-glue-iceberg`, `dbt` or `classic-pyspark`.
- `allow_review_required`: whether to generate a review scaffold when planner decisions remain open.
- `naming`: optional ContractForge naming overrides used for generated artifact names.

CLI flags override the requirements file. For example, this keeps the same reviewed intent but generates a Databricks Asset Bundle preview:

```bash
contractforge-ai guided-project \
  --requirements requirements/orders-project.yaml \
  --target databricks-dab \
  --output-dir ./generated/orders-dab \
  --dry-run
```

## ContractForge YAML Projects

`contractforge-ai generate-project --target contractforge-yaml` generates a reviewable ContractForge YAML scaffold from schema/profile metadata and explicit source/target options.

Generated artifact names are derived with the core ContractForge naming policy. The default policy is `caf_default`; physical target identifiers are preserved.

Example:

```bash
contractforge-ai generate-project \
  --target contractforge-yaml \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders
```

Generated files:

```text
contracts/<layer>/<target_table>.ingestion.yaml
contracts/<layer>/<target_table>.annotations.yaml
contracts/<layer>/<target_table>.operations.yaml
DECISIONS.md
RUNBOOK.md
VALIDATION.md
README.md
```

Use `--naming-file` when generated artifact names need explicit overrides:

```yaml
policy: caf_default
logical_name: orders_platform
contract_basename: orders_contract
bundle_name: orders-bundle
job_name: Orders Ingestion
task_key: orders_ingestion_task
```

```bash
contractforge-ai generate-project \
  --target contractforge-yaml \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --naming-file naming.yaml \
  --output-dir ./generated/orders
```

When a naming file is provided, the generated ingestion contract includes the same `naming` block so review and regeneration can preserve the artifact decisions.

The generated ingestion contract keeps ingestion behavior separate from governance/operations metadata. The annotations and operations files are generated as separate draft files so teams can review them independently.

Use bundle-aware review for generated ContractForge YAML projects:

```bash
contractforge-ai review contracts/bronze/b_orders.ingestion.yaml --bundle
```

## AWS Glue Iceberg Projects

`contractforge-ai generate-project --target aws-glue-iceberg` creates a
contract-first AWS scaffold. It does not generate per-contract ingestion logic.
The generated project keeps ingestion behavior in split contracts and lets the
AWS adapter deploy those contracts through its stable Glue runtime runner.

Example:

```bash
contractforge-ai generate-project \
  --target aws-glue-iceberg \
  --schema schema-profile.json \
  --project-name orders_aws \
  --connector s3 \
  --source-path s3://landing/orders \
  --target-catalog analytics \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders-aws
```

Generated files:

```text
project.yaml
environments/aws.environment.yaml
connections/source.yaml
contracts/aws/<layer>/<contract>/<contract>.ingestion.yaml
contracts/aws/<layer>/<contract>/<contract>.annotations.yaml
contracts/aws/<layer>/<contract>/<contract>.operations.yaml
DECISIONS.md
RUNBOOK.md
VALIDATION.md
README.md
```

The AWS environment uses syntactically valid review placeholders for fields
that the AWS planner validates, for example
`s3://review-required-contractforge-artifacts/project/`. Replace these before
deployment:

- `artifacts.uri`: S3 prefix where ContractForge publishes contract/runtime artifacts.
- `parameters.aws.iceberg.warehouse`: Iceberg warehouse S3 prefix.
- `parameters.aws.glue_job.role_arn`: Glue execution role ARN.
- `parameters.aws.dependencies.extra_py_files`: S3 wheel locations for ContractForge packages.

Review flow:

```bash
contractforge-ai validate-project-structure ./generated/orders-aws --adapter aws
contractforge-aws plan ./generated/orders-aws/contracts/aws/bronze/b_orders/b_orders.ingestion.yaml \
  --environment ./generated/orders-aws/environments/aws.environment.yaml
contractforge-aws deploy ./generated/orders-aws/contracts/aws/bronze/b_orders/b_orders.ingestion.yaml \
  --environment ./generated/orders-aws/environments/aws.environment.yaml \
  --dry-run
```

The important portability property is that `aws-glue-iceberg` changes the
project/environment/deployment boundary, not the ingestion semantics. If the
same contract intent also targets Databricks, the differences should remain in
environment files, project deployment metadata and last-resort
`extensions.<adapter>` blocks.

`RUNBOOK.md` contains operational entry points, pre-run checks, validation commands and incident notes.
`VALIDATION.md` contains deterministic generated-artifact validation and ContractForge plan-building validation through the required core package.

Preview the plan without writing files:

```bash
contractforge-ai generate-project \
  --target contractforge-yaml \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --format markdown
```

Dry-run filesystem writes:

```bash
contractforge-ai generate-project \
  --target contractforge-yaml \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders \
  --dry-run
```

Overwrite existing generated files only when explicitly requested:

```bash
contractforge-ai generate-project \
  --target contractforge-yaml \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders \
  --force
```

## Databricks Asset Bundle Projects

`contractforge-ai generate-project --target databricks-dab` generates a Databricks Asset Bundle starter project around a ContractForge ingestion contract.

Use this target when the expected output is not only YAML contracts, but a deployable Databricks project structure with bundle configuration, job resources and a notebook task.

Example:

```bash
contractforge-ai generate-project \
  --target databricks-dab \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders-dab
```

Generated files:

```text
databricks.yml
resources/jobs.yml
notebooks/run_<layer>_<target_table>.py
contracts/<layer>/<target_table>.ingestion.yaml
contracts/<layer>/<target_table>.annotations.yaml
contracts/<layer>/<target_table>.operations.yaml
DECISIONS.md
RUNBOOK.md
VALIDATION.md
README.md
```

When the prompt explicitly asks for serverless, existing-cluster or job-cluster compute, the generated DAB uses that compute style directly. If the prompt does not state a compute preference, the bundle uses an `existing_cluster_id` variable with `REVIEW_REQUIRED` so the reviewer can choose the right workspace-specific execution target.

Examples:

```text
Create a DAB project for main.bronze.b_orders using serverless.
Create a DAB project for main.bronze.b_orders with existing_cluster_id 1234-567890-abcd.
Create a DAB project for main.bronze.b_orders with a job cluster.
```

Typical review flow:

```bash
cd ./generated/orders-dab

# Review DECISIONS.md and replace REVIEW_REQUIRED values first.
databricks bundle validate
databricks bundle deploy -t dev
databricks bundle run <job-name> -t dev
```

The generated notebook loads the ingestion contract from the bundle workspace and calls ContractForge directly. ContractForge and any required connector dependencies must be available in the selected Databricks runtime.

Preview without writing files:

```bash
contractforge-ai generate-project \
  --target databricks-dab \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --format markdown
```

## ContractForge Python Projects

`contractforge-ai generate-project --target contractforge-python` generates a Python-first project that calls ContractForge through explicit `ingest()` wrappers while keeping ingestion behavior in separate YAML contracts.

Use this target when a team wants a normal Python package, notebook runner or orchestrator entry point, but still wants contracts to remain reviewable files.

Example:

```bash
contractforge-ai generate-project \
  --target contractforge-python \
  --schema schema-profile.json \
  --project-name orders_ingestion \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders-python
```

Generated files:

```text
pyproject.toml
src/<project_name>/__init__.py
src/<project_name>/config.py
src/<project_name>/run_ingestion.py
notebooks/run_<layer>_<target_table>.py
contracts/<layer>/<target_table>.ingestion.yaml
contracts/<layer>/<target_table>.annotations.yaml
contracts/<layer>/<target_table>.operations.yaml
DECISIONS.md
RUNBOOK.md
VALIDATION.md
README.md
```

The generated Python wrapper stays intentionally thin:

```python
from contractforge_core.contracts import load_contract_bundle, semantic_contract_from_mapping

bundle = load_contract_bundle(contract_path)
semantic = semantic_contract_from_mapping(bundle.contract)
```

Execution is adapter-owned. The generated Python CLI defaults to contract validation and exposes explicit adapter actions:

| Action | Meaning |
| --- | --- |
| `validate` | Load the split bundle through `contractforge-core` and normalize semantics without platform execution. |
| `plan-databricks` | Call the Databricks adapter public planner and return planning status, warnings and blockers. |
| `run-databricks` | Execute through `contractforge_databricks.ingest_databricks_bundle(...)` in a Databricks runtime. |
| `plan-aws` | Call the AWS adapter public planner and return planning status, warnings and blockers. |

AWS execution remains deployment-owned by the AWS adapter after planning, artifact publication and Glue job registration. The Python scaffold does not fake local AWS execution.

The generated Python project is useful for:

- Databricks jobs that execute a Python file or notebook;
- local smoke tests around generated contracts;
- existing orchestrators that expect Python entry points;
- teams migrating from notebook-first ingestion to contract-first ingestion.

Typical review flow:

```bash
cd ./generated/orders-python

# Review DECISIONS.md and contracts first.
pip install -e .
orders_ingestion-ingest --contract contracts/bronze/b_orders.ingestion.yaml
orders_ingestion-ingest --action plan-databricks --contract contracts/bronze/b_orders.ingestion.yaml
orders_ingestion-ingest --action run-databricks --contract contracts/bronze/b_orders.ingestion.yaml
orders_ingestion-ingest --action plan-aws --contract contracts/bronze/b_orders.ingestion.yaml
```

The scaffold does not write credentials or resolved secrets. Confirm runtime dependency installation for `contractforge-core`, the selected adapter and any connector-specific packages before execution.

## Classic PySpark Projects

`contractforge-ai generate-project --target classic-pyspark` generates a classic PySpark comparison project beside the recommended ContractForge contract.

Use this target for migration analysis when a team needs to compare an existing notebook/script style with the contract-first execution path. It is intentionally not a full replacement for ContractForge runtime behavior.

Example:

```bash
contractforge-ai generate-project \
  --target classic-pyspark \
  --schema schema-profile.json \
  --project-name orders_migration \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders-classic
```

Generated files:

```text
classic_pyspark/run_<layer>_<target_table>.py
notebooks/classic_run_<layer>_<target_table>.py
contracts/<layer>/<target_table>.ingestion.yaml
contracts/<layer>/<target_table>.annotations.yaml
contracts/<layer>/<target_table>.operations.yaml
MIGRATION.md
DECISIONS.md
RUNBOOK.md
VALIDATION.md
README.md
```

The generated PySpark files include explicit review placeholders:

```python
df = spark.read.format("REVIEW_REQUIRED").load(source_path)
```

For simple `append` and `overwrite` cases, the comparison script can show a plain Delta write. For merge-based or governance-heavy modes, it raises a clear `NotImplementedError` instead of pretending that manual PySpark is equivalent to ContractForge.

Use this target when:

- migrating notebook-first ingestion into ContractForge;
- explaining the difference between a manual Spark script and governed ingestion;
- reviewing source/target behavior with engineers who are not yet familiar with ContractForge.

Do not use this target as the default production pattern. ContractForge execution owns quality gates, quarantine, schema evolution, lineage, control tables, idempotency and operational evidence.

## dbt Projects

`contractforge-ai generate-project --target dbt` generates a dbt starter project for teams that use dbt downstream of ContractForge ingestion.

The generated dbt project treats the ContractForge-managed target table as a dbt `source()`. This keeps responsibilities separate:

- ContractForge owns ingestion, connector behavior, write modes, governance metadata and operational evidence.
- dbt owns downstream SQL transformations, dbt tests and analytics engineering workflows.

Example:

```bash
contractforge-ai generate-project \
  --target dbt \
  --schema schema-profile.json \
  --project-name orders_analytics \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --output-dir ./generated/orders-dbt
```

Generated files:

```text
dbt_project.yml
models/sources.yml
models/staging/stg_<target_table>.sql
models/staging/stg_<target_table>.yml
DECISIONS.md
RUNBOOK.md
VALIDATION.md
README.md
```

The generated `models/sources.yml` points to the ContractForge target table. The staging model reads from that source:

```sql
with source as (
    select * from {{ source('bronze_bronze', 'b_orders') }}
)

select
    order_id,
    status,
    amount
from source
```

ContractForge quality suggestions are mapped to dbt generic tests when the mapping is direct:

- `quality_rules.not_null` -> `not_null`
- `quality_rules.unique_key` -> `unique`
- `quality_rules.accepted_values` -> `accepted_values`

The generated files remain drafts. Review dbt profile configuration, adapter-specific database/schema naming and generated tests before using them in CI.

Typical review flow:

```bash
cd ./generated/orders-dbt

# Review DECISIONS.md and replace profile placeholders first.
dbt parse
dbt build --select staging
```

Preview without writing files:

```bash
contractforge-ai generate-project \
  --target dbt \
  --schema schema-profile.json \
  --project-name orders_analytics \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --format markdown
```

## ProjectPlan

A `ProjectPlan` describes a complete multi-file output without touching the filesystem.

Fields:

- `name`: logical project name.
- `target`: generation target, such as `contractforge-yaml`, `databricks-dab`, `aws-glue-iceberg`, `dbt` or `classic-pyspark`.
- `artifacts`: list of files to generate.
- `report`: review context for humans.
- `traceability`: evidence, confidence and review boundary.

Example:

```yaml
name: orders
target: contractforge-yaml
artifacts:
  - path: contracts/bronze/orders.ingestion.yaml
    kind: contract
    description: Bronze ingestion contract.
    content: |
      mode: append
  - path: README.md
    kind: markdown
    content: |
      # Orders
report:
  title: Orders project
  summary: Generated project scaffold.
  decisions_required:
    - question: Confirm target catalog
      reason: Catalog naming is environment-specific.
      path: target.catalog
traceability:
  confidence: 0.8
  review_required: true
```

## ProjectArtifact

Each artifact represents a relative file path and content.

Path safety rules:

- paths must be relative;
- absolute paths are rejected;
- `..` traversal is rejected;
- duplicate paths in the same plan are rejected;
- files are not overwritten unless explicitly requested.

Artifact kinds include:

- `contract`
- `annotation`
- `operation`
- `access`
- `notebook`
- `python`
- `sql`
- `yaml`
- `json`
- `markdown`
- `config`
- `resource`
- `other`

## Generated Documentation

Project generators should produce three review documentation artifacts when applicable:

- `README.md`: project overview, generated structure and basic usage.
- `DECISIONS.md`: assumptions, required decisions and review boundary.
- `RUNBOOK.md`: operational checklist, entry points, validation commands and troubleshooting notes.
- `VALIDATION.md`: deterministic validation summary and ContractForge validation result.

Targets may add additional files when useful. For example, `classic-pyspark` also generates `MIGRATION.md` because its main purpose is migration comparison.

## ContractForge Validation Adapter

Generated contracts are always checked with ContractForge AI deterministic validation rules. ContractForge AI also validates generated ingestion contracts with `contractforge_core.contracts.semantic_contract_from_mapping` from `contractforge-core`.

This adapter:

- if ContractForge Core accepts the contract, `VALIDATION.md` records a `PASS`;
- if ContractForge Core rejects the contract, `VALIDATION.md` records a `FAIL` and includes the rejection message;
- if ContractForge Core or one of its required dependencies cannot be imported, `VALIDATION.md` records a `FAIL` explaining the installation issue.

The adapter does not require Spark and does not execute ingestion. It validates the contract shape and plan-building boundary before the scaffold is treated as usable.

## DecisionReport

The report captures the review boundary for a generated project.

It contains:

- summary;
- assumptions;
- decisions required;
- warnings.

This report is separate from artifact contents so future generators can create both machine-readable plans and readable review files.

## CLI

Inspect a project plan:

```bash
contractforge-ai project-plan --input plan.yaml
```

Return the full plan as JSON, including file contents:

```bash
contractforge-ai project-plan --input plan.yaml --format json
```

Return markdown:

```bash
contractforge-ai project-plan --input plan.yaml --format markdown
```

Preview writes without touching the filesystem:

```bash
contractforge-ai project-plan --input plan.yaml --output-dir ./generated --dry-run
```

Write artifacts:

```bash
contractforge-ai project-plan --input plan.yaml --output-dir ./generated
```

Overwrite existing files only when explicitly requested:

```bash
contractforge-ai project-plan --input plan.yaml --output-dir ./generated --force
```

## Design Boundary

The project writer does not decide what should be generated. It only writes an already-constructed `ProjectPlan` safely.

Future generators should:

- produce a `ProjectPlan`;
- attach traceability;
- include a review report;
- avoid writing files unless the user passes an output directory;
- never write credentials or resolved secrets.
