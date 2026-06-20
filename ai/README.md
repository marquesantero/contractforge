# ContractForge AI

ContractForge AI is the AI-assisted companion package for [ContractForge](https://github.com/marquesantero/contractforge). It provides contract review, diagnostics, annotation suggestions and project-generation guidance without coupling deterministic ingestion to a specific model provider.

The ingestion engine remains deterministic. ContractForge AI reads contracts, control-table evidence and selected samples, then produces structured recommendations for humans and CI workflows.

ContractForge AI is distributed as its own wheel in the ContractForge monorepo. It requires `contractforge-core` for contract validation, naming policy and semantic normalization. Runtime adapters such as `contractforge-databricks`, `contractforge-aws`, `contractforge-snowflake`, `contractforge-fabric` and `contractforge-gcp` remain optional and are used only when an AI workflow needs platform-specific execution or deployment guidance.

## Initial Capabilities

- Deterministic contract review with risk findings before invoking any model.
- Deterministic failure explanation from ContractForge run/error evidence.
- Deterministic annotation and quality-rule suggestions from schema/profile metadata.
- Project scaffold generation for ContractForge YAML, thin Python wrappers, Databricks Asset Bundles, dbt and classic PySpark migration projects.
- Integration profiles and redacted environment discovery for local, CI, Databricks and agent onboarding.
- Repository instruction asset generation for coding assistants and IDE agents.
- Local knowledge indexing for contract repositories, documentation, sample context and reviewed examples.
- Shared evidence, confidence, assumptions and review-required output model.
- Provider abstraction for future LLM integrations.
- OpenAI and Azure OpenAI provider configuration with optional SDK dependency.
- Provider capability registry for structured-output strategy, transport and Databricks runtime dependency decisions.
- Secret redaction utilities for safe context assembly.
- CLI entry point for local and CI usage.

## Installation

```bash
pip install contractforge-ai
```

This installs `contractforge-core` as the deterministic validation dependency. Install provider and adapter extras only when a workflow needs live model enrichment or platform-specific project execution.

Adapter-aware examples:

```bash
pip install "contractforge-ai[databricks]"
pip install "contractforge-ai[aws-adapter]"
pip install "contractforge-ai[snowflake-adapter]"
pip install "contractforge-ai[fabric-adapter]"
pip install "contractforge-ai[gcp-adapter]"
```

For local development:

```bash
pip install -e ".[dev]"
```

## Usage

The package can run useful checks without configuring a model provider.

Inspect the local setup:

```bash
contractforge-ai environment-report
```

The report separates package availability into `contractforge` (`contractforge_core`, `contractforge_ai`), optional `adapters` (`contractforge_databricks`, `contractforge_aws`), parser dependencies, provider clients and platform SDKs. Missing adapters are informational unless the workflow asks for adapter-aware validation or platform execution guidance.

ContractForge AI does not import adapter packages or platform SDKs at package import time. Adapter planning is reached through the optional adapter public APIs, and provider/runtime SDKs are imported only inside the specific workflow that needs them. This keeps local deterministic review usable without Databricks, AWS, Spark or Glue dependencies installed.

List supported integration profiles:

```bash
contractforge-ai profiles
```

Validate a Databricks job-oriented setup:

```bash
contractforge-ai profile databricks-job --config databricks-profile.json --format json
```

Generate non-secret onboarding files:

```bash
contractforge-ai init --profile local-cli --output-dir ./contractforge-ai-setup
```

Generate repository instructions for coding assistants:

```bash
contractforge-ai agent-instructions --target all --project-name "Orders Platform" --output-dir .
```

Build a local knowledge index from reviewed documentation, contracts and examples:

```bash
contractforge-ai knowledge-index build docs contracts examples --output .contractforge-ai/knowledge.json
```

Query the index with citations before attaching model-backed enrichment:

```bash
contractforge-ai knowledge-index query \
  --index .contractforge-ai/knowledge.json \
  --query "How should serverless object storage access be configured?"
```

The knowledge index is deterministic and local. It redacts common secret patterns, stores source paths and line ranges, and is intended to provide grounded context to future AI planning, critique and project-generation workflows.

Route a user intent to the appropriate ContractForge AI workflow:

```bash
contractforge-ai route-task \
  --intent "Generate a shape for nested JSON with arrays" \
  --knowledge-index .contractforge-ai/knowledge.json \
  --format markdown
```

Task routing selects the high-level workflow, prompt template, provider-routing task and relevant local context. It is designed to run before model calls so provider-backed enrichment receives focused, cited context instead of a large unstructured prompt.

For low-risk advisory tasks, such as metadata commentary or review enrichment, task routing can prefer HTTP-only providers to avoid extra SDK dependencies in constrained runtimes:

```bash
contractforge-ai route-task \
  --intent "Review this contract and summarize low-risk metadata improvements" \
  --knowledge-index .contractforge-ai/knowledge.json \
  --prefer-http-only \
  --format markdown
```

`--prefer-http-only` is a routing preference, not a quality override. Workflows that generate project plans, contracts or deployable artifacts still require strict structured-output support even when HTTP-only routing is preferred.

Generate a complete intent-first ContractForge project from a natural-language request:

```bash
contractforge-ai generate \
  --prompt "Use table main.raw.orders_sample and create a bronze to gold project. Silver must use hash_diff_upsert. Gold final columns: order_id, customer_id, amount, order_date, status." \
  --schema schemas/orders.json \
  --output-dir ./generated/orders-medallion
```

`generate` is the most direct project-creation path. It interprets the user intent, builds a bronze/silver/gold ContractForge structure when the prompt asks for a medallion flow, chains layer outputs as layer inputs, writes split ingestion/annotations/operations contracts and consolidates review guidance into `AI_REVIEW.html`.

When the prompt explicitly names a supported adapter such as AWS Glue or Databricks, generated `project.yaml` includes the matching environment entry and each project step points that adapter to the same canonical ingestion contract. ContractForge AI does not fork contract semantics by platform. The generated adapter environment is a deployment scaffold with review-required runtime values; it is not allowed to change source, target, write mode, quality, access or transform intent.

AWS-oriented intent:

```bash
contractforge-ai generate \
  --prompt "Create an AWS Glue bronze project from s3://landing/orders into analytics.bronze.b_orders using append." \
  --schema schemas/orders.json \
  --output-dir ./generated/orders-aws
```

Databricks-oriented intent:

```bash
contractforge-ai generate \
  --prompt "Create a Databricks Asset Bundle bronze project from /Volumes/raw/orders into main.bronze.b_orders using append." \
  --schema schemas/orders.json \
  --output-dir ./generated/orders-databricks
```

Both forms keep the generated ingestion contract portable. The project metadata differs only by environment binding, for example `environments/aws.environment.yaml` or `environments/databricks.environment.yaml`, until an adapter deploy command materializes platform-native artifacts.

Provider-backed guided generation can add allowlisted draft fields such as `source_format`, `transform`, `shape`, `quality_rules`, `annotations` and `operations`. It cannot silently overwrite deterministic identity fields such as connector, source path, target, layer or write mode. Conflicting provider proposals are rejected and recorded in the provider proposal audit; provider-filled missing identity values remain review-required. Provider-suggested fields that can change contract behavior or deployment behavior, such as `transform`, `shape`, `quality_rules`, `annotations`, `operations` and `dab_compute`, are always review-required even when the provider claims high confidence. Unsupported runtime fields, secrets or deployment settings are rejected and audited instead of being written into generated contracts.

When no schema file is available, provide an inspectable Databricks table as schema evidence:

```bash
contractforge-ai generate \
  --prompt "Create a bronze to gold orders pipeline from the example table and keep only order_id, customer_id, amount and status in gold." \
  --sample-table main.raw.orders_sample \
  --default-catalog main \
  --output-dir ./generated/orders-medallion
```

Use `--with-ai --provider <provider>` when configured model guidance should enrich the review report. ContractForge AI still validates the generated artifacts locally and keeps unresolved business decisions explicit, especially keys, SCD behavior, quality gates, PII handling and ownership.

When a human-facing report should be delivered in another language, pass `--language <language>` together with `--with-ai`. ContractForge AI first renders the canonical English report, then asks the selected provider to translate narrative prose. Technical labels, statuses, paths, commands, JSON/YAML and code remain in English.

```bash
contractforge-ai generate \
  --prompt "Create a bronze to gold orders pipeline from main.raw.orders_sample." \
  --sample-table main.raw.orders_sample \
  --with-ai \
  --provider openai \
  --language pt-BR \
  --output-dir ./generated/orders-medallion
```

Validate generated or AI-reviewed artifacts before treating them as ready:

```bash
contractforge-ai validate-artifact \
  --contract contracts/bronze/orders.ingestion.yaml \
  --format markdown
```

The deterministic validation gate normalizes results to `READY`, `NEEDS_DECISIONS`, `INVALID` or `UNSAFE`. It can validate generated ContractForge contracts, generated project plans and provider structured outputs. Provider text never overrides these deterministic statuses.

Validate a real ContractForge project folder, including `project.yaml`, environment YAMLs, reusable connection YAMLs and split contract bundles:

```bash
contractforge-ai validate-project-structure ./examples/real-world/supabase-jdbc-medallion --format markdown
```

This gate reuses ContractForge Core for environment validation, connection resolution, bundle composition and semantic normalization. ContractForge AI adds CI-friendly findings for project-level mistakes such as legacy flat contract fields, missing connection files, wrapped split sections and inline secrets. Ingestion-level source settings override the reusable connection YAML after the connection is loaded by the core.

When adapter packages are installed, add explicit adapter planning gates:

```bash
contractforge-ai validate-project-structure ./examples/real-world/supabase-jdbc-medallion \
  --adapter databricks \
  --adapter aws \
  --format markdown
```

Adapter-aware validation calls the public adapter planners only. It does not execute jobs or create infrastructure. `SUPPORTED` remains ready, `SUPPORTED_WITH_WARNINGS` and `REVIEW_REQUIRED` require decisions, and `UNSUPPORTED` fails the gate.

Provider-backed explanations can be layered over adapter validation through the `adapter.validation.enrichment.v1` prompt, but the deterministic adapter status remains authoritative.

Run second-pass critique over generated or model-enriched output:

```bash
contractforge-ai critique-output \
  --input enriched-project-plan.json \
  --validation validation-report.json \
  --context retrieved-context.json \
  --format markdown
```

Critique scoring checks evidence coverage, unresolved decisions, readiness claims, validation failures and contract-boundary mistakes such as metadata being placed inside transformation logic.

Review a contract:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml
```

Review a separated ContractForge contract bundle by loading sibling annotations and operations files:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --bundle
```

Optionally attach provider-backed advisory enrichment while keeping deterministic findings authoritative:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --with-ai --format json
```

Return JSON for CI or automation:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --format json
```

Render a pull-request friendly Markdown report:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --format markdown
```

Fail CI when high-risk findings are present:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --fail-on high
```

Fail CI for a specific deterministic finding:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --fail-on-code write.keys.nullable
```

Explain a failed run from JSON evidence:

```bash
contractforge-ai explain-run --input failed-run.json
```

Optionally enrich the deterministic explanation:

```bash
contractforge-ai explain-run --input failed-run.json --with-ai --format json
```

Explain a Databricks run by collecting ContractForge control-table evidence:

```bash
contractforge-ai explain-run \
  --run-id 264f171c-83e9-43f5-baea-c0391838145a \
  --catalog main \
  --ctrl-schema ops \
  --format json
```

Return JSON for automation:

```bash
contractforge-ai explain-run --input failed-run.json --format json
```

Analyze aggregate ContractForge control-table evidence:

```bash
contractforge-ai analyze-control-tables \
  --input control-table-evidence.json \
  --format markdown
```

Attach provider-backed operational guidance while keeping deterministic metrics and findings authoritative:

```bash
contractforge-ai analyze-control-tables \
  --input control-table-evidence.json \
  --with-ai \
  --provider openai \
  --language pt-BR \
  --format html
```

The control-table analyzer accepts redacted JSON evidence with keys such as `runs`, `errors`, `quality`, `streams`, `schema_changes`, `operations` and `collection_errors`. It produces status/risk, aggregate metrics, deterministic findings, recommendations and follow-up SQL queries.

The analyzer also detects recurring failure clusters by target/runtime/connector, repeated authentication/network/dependency error categories, schema drift, quality degradation, stream metric inconsistencies, duration outliers and freshness SLA breaches when operations evidence includes SLA lag fields.

Example failure evidence:

```json
{
  "run": {
    "run_id": "264f171c-83e9-43f5-baea-c0391838145a",
    "status": "FAILED",
    "target_table": "workspace.cf_examples_bronze.b_cdc_covid",
    "source_connector": "http_file",
    "runtime_type": "serverless",
    "error_message": "urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>"
  },
  "errors": [
    {
      "stack_trace": "Full stack trace or ctrl_ingestion_errors payload"
    }
  ]
}
```

Initial deterministic categories include authentication/authorization, network/egress, storage access, schema/SQL, quality gates, missing dependency/driver, runtime limitation and API rate/quota failures.

Suggest annotations and quality rules from schema/profile metadata:

```bash
contractforge-ai suggest-metadata --schema schema-profile.json --format yaml
```

Suggestions include evidence and confidence in JSON/text output. Treat them as reviewable drafts, not automatic contract changes.

Suggest shape configuration from nested JSON samples:

```bash
contractforge-ai suggest-shape --sample sample.json --format yaml
```

Array explosions are marked for review because they can multiply row counts.

Generate a draft ingestion contract:

```bash
contractforge-ai generate-contract \
  --schema schema-profile.json \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders
```

Generated contracts are marked as drafts and include review-required metadata.

Generate a reviewable project scaffold:

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

Project targets currently include `contractforge-yaml`, `contractforge-python`, `databricks-dab`, `aws-glue-iceberg`, `snowflake-sql-warehouse`, `fabric-lakehouse`, `gcp-bigquery`, `dbt` and `classic-pyspark`. The `contractforge-yaml` target emits canonical split contracts. Adapter targets keep ingestion behavior in the same split contracts and add only platform deployment scaffolding. The `contractforge-python` target validates through `contractforge-core` by default and exposes explicit adapter actions such as `plan-databricks`, `run-databricks` and `plan-aws`. Generated scaffolds include reviewable docs such as `README.md`, `DECISIONS.md`, `RUNBOOK.md` and `VALIDATION.md`.

Planner platform hints come from explicit platform or platform-service wording, not storage locations alone. `s3://...` selects the `s3` connector but does not force AWS; `iceberg` can describe table format without forcing the AWS adapter. If no platform is named and multiple adapters support the connector, planning can recommend multiple adapter targets for the same contract intent.

Generate an AWS Glue/Iceberg project scaffold:

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

Adapter targets write contracts under `contracts/<adapter>/...`, generate `environments/<adapter>.environment.yaml`, and use syntactically valid review placeholders such as `REVIEW_REQUIRED`, `s3://review-required-...` or `gs://review-required-...` so deterministic project validation can run the adapter planner before real cloud, warehouse, IAM or governance values are filled.

Generated artifact names follow the core ContractForge naming policy. Use a naming override file when a scaffold needs explicit contract, bundle, job or task names:

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
  --target databricks-dab \
  --schema schema-profile.json \
  --project-name orders \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders \
  --naming-file naming.yaml
```

Plan a project from natural language before generating files:

```bash
contractforge-ai plan-project \
  --intent "Create a silver ingestion from s3a://landing/orders into main.silver.orders using hash_diff_upsert." \
  --schema schemas/orders.json \
  --format markdown
```

Planner output is review-only. It lists missing decisions and recommended `generate-project` commands; it does not write files or deploy resources.

Optional provider-backed enrichment can be attached with `--with-ai`, but the deterministic planner result remains authoritative:

```bash
contractforge-ai plan-project \
  --intent "Create a silver ingestion from s3a://landing/orders into main.silver.orders using hash_diff_upsert." \
  --schema schemas/orders.json \
  --with-ai \
  --format json
```

Generate directly from the reviewed planning path when the scenario is ready enough to scaffold:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders." \
  --schema schemas/orders.json \
  --target databricks-dab \
  --output-dir ./generated/orders-dab
```

Use `--with-ai` when a configured provider should help refine the project specification before files are generated:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/events into main.bronze.b_events. The source returns nested JSON payloads." \
  --schema schemas/events.json \
  --target contractforge-yaml \
  --with-ai \
  --provider openai \
  --allow-review-required \
  --output-dir ./generated/events
```

In this path the model does not only write a side report. ContractForge AI first builds an `EnrichedProjectSpec`, asks the provider for structured field updates, validates the response locally, then generates artifacts from the enriched spec. Evidence-backed technical suggestions can be applied to generated draft files, for example `source.format`, full `transform` blocks, `quality_rules`, `annotations` and `operations`. Full transform blocks remain review-required until a human approves the schema/value/cardinality impact.

Prompt-explicit values are also carried deterministically when they are clear enough to be materialized. For example, a prompt can provide owners, criticality, freshness SLA, required columns, unique keys, accepted values, expression checks and DAB compute preference such as serverless, existing cluster or job cluster.

Business-critical fields stay review-required even when the provider suggests them. Examples include merge keys, hash-diff columns, ownership, SLA, delete semantics, legal PII policy and credentials.

Generate from a context directory when no explicit schema file exists yet:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from /landing/orders into main.bronze.b_orders." \
  --context-dir samples/orders \
  --runtime databricks-serverless \
  --target contractforge-yaml \
  --allow-review-required \
  --output-dir ./generated/orders
```

Context-aware generation inspects supported local samples such as JSON, JSONL and CSV, creates a reviewable inferred schema profile when possible, and writes `CONTEXT.md` plus `context/context-package.json` into the generated project. Deterministic validation still remains authoritative; context evidence is not treated as proof that a sample covers the whole source.

`guided-project` refuses to write files when required decisions remain open. Pass `--allow-review-required` only when the goal is to create a review scaffold with explicit placeholders, unresolved decisions and a rich HTML review.

When a guided project is materialized, the result includes deterministic validation and second-pass critique sections. These gates classify the scaffold as `READY`, `NEEDS_DECISIONS`, `INVALID` or `UNSAFE`; generated project files are still review artifacts until those gates and the decision report are clean. The generated rich HTML review consolidates the requested intent, inferred specification, generated artifacts, validation status and unresolved decisions.

For repeatable guided generation, use a reviewed requirements file:

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

```bash
contractforge-ai guided-project \
  --requirements requirements/orders-project.yaml \
  --output-dir ./generated/orders
```

Evaluate enrichment quality against a deterministic baseline:

```bash
contractforge-ai eval-enrichment \
  --deterministic deterministic.json \
  --enrichment enriched.json \
  --kind project_plan \
  --format markdown
```

The test suite includes deterministic workflow fixtures for project planning, task routing, provider-output validation and control-table incidents. These fixtures are intended to catch regressions in status, decisions, evidence and validation behavior before provider-backed tests are enabled.

Provider quality evaluation also rejects readiness claims that contradict deterministic status. If the baseline is `NEEDS_DECISIONS`, `INVALID`, `UNSAFE`, `UNSUPPORTED` or `FAIL`, provider summaries and recommendations must not claim the project is ready to deploy, publish, run or proceed.

## Provider Configuration

ContractForge AI can run deterministic checks without any model provider. Configure a provider only when model-enriched explanations or generation features are enabled.

Install provider dependencies:

```bash
pip install "contractforge-ai[openai]"
```

OpenAI:

```bash
export CONTRACTFORGE_AI_PROVIDER=openai
export CONTRACTFORGE_AI_MODEL=gpt-4.1
export OPENAI_API_KEY=...
```

Azure OpenAI:

```bash
export CONTRACTFORGE_AI_PROVIDER=azure_openai
export CONTRACTFORGE_AI_MODEL=<deployment-name>
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
export AZURE_OPENAI_API_VERSION=<api-version>
```

Databricks Model Serving:

```bash
export CONTRACTFORGE_AI_PROVIDER=databricks
export CONTRACTFORGE_AI_MODEL=<serving-endpoint-name>
export DATABRICKS_HOST=https://<workspace-host>
export DATABRICKS_TOKEN=...
```

DeepSeek:

```bash
export CONTRACTFORGE_AI_PROVIDER=deepseek
export CONTRACTFORGE_AI_MODEL=deepseek-chat
export DEEPSEEK_API_KEY=...
```

Anthropic:

```bash
export CONTRACTFORGE_AI_PROVIDER=anthropic
export CONTRACTFORGE_AI_MODEL=claude-sonnet-4-5
export ANTHROPIC_API_KEY=...
```

Google Gemini API:

```bash
export CONTRACTFORGE_AI_PROVIDER=gemini
export CONTRACTFORGE_AI_MODEL=gemini-2.5-flash
export GEMINI_API_KEY=...
```

AWS Bedrock:

```bash
pip install "contractforge-ai[aws]"
export CONTRACTFORGE_AI_PROVIDER=bedrock
export CONTRACTFORGE_AI_MODEL=anthropic.claude-3-5-sonnet-20240620-v1:0
export AWS_REGION=us-east-1
```

Provider settings are redacted before being returned in diagnostics. Providers receive already-prepared prompts/context and should not read files, resolve secrets or query Databricks directly.

Provider capabilities are explicit. OpenAI and Azure OpenAI can use strict structured-output controls, DeepSeek is OpenAI-compatible but JSON-mode only, Anthropic uses tool schema, Gemini uses native JSON schema through `generateContent`, Bedrock uses Converse tool schema through `boto3`, and Databricks Model Serving depends on the served endpoint/model. See [Provider configuration](docs/providers.md) for the current matrix and planned provider registry.

Evaluate a configured provider before using it in reviewed workflows:

```bash
contractforge-ai eval-provider --provider openai --format markdown
```

Recommend a provider for a task without calling a model:

```bash
contractforge-ai route-provider --task project_planning --require-strict-schema
```

## Documentation

- [Getting started](docs/getting-started.md)
- [Onboarding profiles](docs/onboarding.md)
- [Agent and IDE instruction assets](docs/agent-instructions.md)
- [Security model](docs/security.md)
- [CI usage](docs/ci.md)
- [Databricks notebook usage](docs/databricks.md)
- [Provider configuration](docs/providers.md)
- [Evidence and confidence model](docs/evidence.md)
- [Evaluation and regression fixtures](docs/evaluation.md)
- [Enrichment quality evaluation](docs/enrichment-evaluation.md)
- [Prompt evaluation harness](docs/prompt-evaluation.md)
- [Project structure validation](docs/project-structure-validation.md)
- [Metadata and quality suggestions](docs/suggestions.md)
- [Shape suggestions](docs/shape.md)
- [Contract draft generation](docs/contract-generation.md)
- [Natural-language project planning](docs/project-planning.md)
- [Project generation core](docs/project-generation.md)
- [Architecture](docs/architecture.md)

## Design Principles

- **Companion package over the semantic core**: ContractForge AI depends on `contractforge-core` so validation, naming and contract semantics stay aligned. Platform adapters remain optional execution boundaries.
- **Deterministic checks first**: hard rules catch known risks before any LLM suggestion is requested.
- **Provider-neutral**: OpenAI, Azure OpenAI, Databricks Serving or local models can be added behind the same interface.
- **Redaction by default**: secrets, tokens and passwords are removed before context is sent to a model.
- **Human-reviewed output**: the tool proposes changes; it does not mutate production contracts or data without explicit user action.
- **Current-practice review before implementation**: AI-facing features require multi-source research into current implementation guidance, security risks, RAG practices, prompt engineering and eval strategy before code changes.

## Roadmap

- Contract reviewer with LLM-enriched recommendations.
- Failure explainer based on `ctrl_ingestion_runs` and `ctrl_ingestion_errors`.
- Annotation and quality-rule suggestions.
- Shape generator for nested JSON and arrays.
- Contract generator from source schema, sample payloads or existing notebooks.
- Additional project generation targets and optional model-enriched planning.
