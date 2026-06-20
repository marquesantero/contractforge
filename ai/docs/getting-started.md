# Getting Started

ContractForge AI is useful before any model provider is configured. The first layer is deterministic: it reviews contracts, validates generated artifacts and explains failures with explicit, testable rules. With a configured provider, the tool can reason over intent, schemas, examples, generated projects and operational evidence before producing reviewable artifacts.

The recommended mental model is simple: deterministic validation is the gate, provider-backed reasoning is the assistant. Model output can enrich specifications, reports and remediation guidance, but generated artifacts remain reviewable until deterministic validation and required decisions are clean.

## Install

```bash
pip install contractforge-ai
```

For local development:

```bash
pip install -e ".[dev]"
```

## Review a Contract

Before reviewing contracts in a new environment, inspect setup and select the integration profile:

```bash
contractforge-ai environment-report
contractforge-ai profiles
contractforge-ai profile local-cli
```

Generate onboarding configuration files:

```bash
contractforge-ai init --profile local-cli --output-dir ./contractforge-ai-setup
```

Use JSON output for support bundles, CI and notebooks:

```bash
contractforge-ai environment-report --format json
contractforge-ai profile databricks-job --config databricks-profile.json --format json
contractforge-ai init --profile databricks-job --catalog main --ctrl-schema ops --dry-run --format json
```

See [Onboarding profiles](onboarding.md) for profile-specific requirements.

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml
```

If the repository uses separated ContractForge contracts, review the ingestion file with its sibling `.annotations.yaml` and `.operations.yaml` files:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --bundle
```

Use JSON output when integrating with scripts or CI:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --format json
```

Fail CI when severe findings are present:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --fail-on high
```

The reviewer currently checks operational risks such as missing targets, unsafe write modes, missing merge-key quality rules, JSON sources without explicit schema, Auto Loader checkpoint gaps and missing governance metadata. Standalone review expects metadata in the reviewed contract. Bundle-aware review accepts the standard ContractForge separation across ingestion, annotations and operations files.

## Explain a Failed Run

Create a JSON file with run and error evidence:

```json
{
  "run": {
    "run_id": "run-123",
    "status": "FAILED",
    "source_connector": "azure_blob",
    "runtime_type": "serverless",
    "error_message": "AuthorizationPermissionMismatch: This request is not authorized"
  },
  "errors": [
    {
      "stack_trace": "PERMISSION_DENIED: Service Principal does not have required storage permissions"
    }
  ]
}
```

Run:

```bash
contractforge-ai explain-run --input failed-run.json
```

For automation:

```bash
contractforge-ai explain-run --input failed-run.json --format json
```

When running in Databricks, the command can collect ContractForge control-table evidence directly by `run_id`:

```bash
contractforge-ai explain-run \
  --run-id run-123 \
  --catalog main \
  --ctrl-schema ops \
  --format json
```

## Analyze Operational Evidence

Use aggregate control-table analysis when you want health signals across multiple runs instead of one failed run:

```bash
contractforge-ai analyze-control-tables \
  --input control-table-evidence.json \
  --format markdown
```

The input is a JSON evidence package containing arrays such as `runs`, `errors`, `quality`, `streams` and `schema_changes`. The output includes status, risk, metrics, deterministic findings, recommendations and follow-up SQL queries.

This uses `ctrl_ingestion_runs`, `ctrl_ingestion_errors`, `ctrl_ingestion_quality` and `ctrl_ingestion_streams` when available. Collected evidence is redacted before classification.

## Suggested Workflow

1. Run deterministic review in CI for every contract change.
2. Use failure explanation after failed jobs or failed integration tests.
3. Generate annotation and quality-rule suggestions from schema/profile metadata.
4. Generate shape suggestions from nested JSON samples when working with structs or arrays.
5. Use `generate` or `guided-project` when you want a complete reviewable scaffold.
6. Enable model providers for AI-first guided generation, richer explanations and operational analysis.
7. Review `AI_REVIEW.html` as the primary approval artifact.
8. Keep generated recommendations and provider-suggested business decisions under review.
9. Add recurring failure modes as deterministic tests before relying on model output.

## Route Work Before Model Calls

Use task routing when you want ContractForge AI to choose the workflow, prompt template, provider-routing task and cited local context before calling any provider:

```bash
contractforge-ai route-task \
  --intent "Review this AWS Glue contract and identify portability risks" \
  --knowledge-index .contractforge-ai/knowledge.json \
  --format markdown
```

For low-risk advisory work, prefer HTTP-only provider boundaries without changing the deterministic validation gate:

```bash
contractforge-ai route-task \
  --intent "Summarize documentation gaps for this connector" \
  --knowledge-index .contractforge-ai/knowledge.json \
  --prefer-http-only \
  --format markdown
```

`--prefer-http-only` is cost and dependency guidance only. Project planning, contract generation and deployable-artifact workflows still require strict schema support because their output can affect real ingestion behavior.

## Suggest Metadata

Input schema/profile files can be JSON or YAML. A minimal JSON example:

```json
{
  "columns": [
    {"name": "customer_id", "type": "STRING", "nullable": false},
    {"name": "customer_email", "type": "STRING", "nullable": true},
    {
      "name": "status",
      "type": "STRING",
      "nullable": false,
      "profile": {"distinct_values": ["open", "closed", "cancelled"]}
    },
    {"name": "order_amount", "type": "DOUBLE", "nullable": true}
  ]
}
```

Generate YAML snippets:

```bash
contractforge-ai suggest-metadata --schema schema-profile.json --format yaml
```

The output contains `annotations` and `quality_rules` blocks compatible with ContractForge. JSON/text output also includes evidence and confidence for each suggestion.

Suggested metadata should be reviewed before use. The deterministic generator is intentionally conservative: it uses column names, nullability, types and optional profiles, but it does not claim business meaning that is not present in the evidence.

## Suggest Shape

Use `suggest-shape` to inspect nested JSON and produce a draft `shape` block:

```bash
contractforge-ai suggest-shape --sample sample.json --format yaml
```

The command discovers primitive paths, nested structs and arrays. Arrays are marked with `requires_review` because explode operations can multiply rows.

## Generate Contract Draft

Use `generate-contract` to create a reviewable ContractForge ingestion contract draft from schema/profile metadata:

```bash
contractforge-ai generate-contract \
  --schema schema-profile.json \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders
```

The generated contract includes `_metadata.draft: true` and `_metadata.review_required: true`. Review connector options, credentials, target naming, write mode, merge keys, annotations and quality rules before execution.

## Generate a Guided Project

Use `guided-project` when the user request should become a complete reviewable project instead of a single contract:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders." \
  --schema schemas/orders.json \
  --target contractforge-yaml \
  --output-dir ./generated/orders
```

Add `--with-ai` only when a configured provider should help before generation:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/events into main.bronze.b_events. The endpoint returns nested JSON payloads." \
  --schema schemas/events.json \
  --target contractforge-yaml \
  --with-ai \
  --provider openai \
  --allow-review-required \
  --output-dir ./generated/events
```

In the AI-first path, ContractForge AI validates provider output before applying it. Supported suggestions can improve generated `source.format`, `transform.shape`, `quality_rules`, `.annotations.yaml` and `.operations.yaml`. Merge keys, ownership, SLA, delete semantics, legal PII policy and credentials remain explicit review decisions.

When a prompt names a supported execution platform, generated project metadata
adds the matching environment scaffold while keeping contract semantics shared:

```bash
contractforge-ai generate \
  --prompt "Create an AWS Glue bronze project from s3://landing/orders into analytics.bronze.b_orders using append." \
  --schema schemas/orders.json \
  --target aws-glue-iceberg \
  --output-dir ./generated/orders-aws
```

The explicit `--target` also contributes a deterministic platform hint. For
example, `--target aws-glue-iceberg` adds the AWS environment scaffold even
when the prompt only describes the source and target.

Generated `project.yaml` points both review and AWS to the same contract:

```yaml
environments:
  review: environments/review.environment.yaml
  aws: environments/aws.environment.yaml

execution_order:
  - name: bronze_b_orders
    contracts:
      review: contracts/bronze/b_orders.ingestion.yaml
      aws: contracts/bronze/b_orders.ingestion.yaml
```

The environment file can contain adapter deployment values, evidence location
and artifact publication settings. It must not contain source, target, write
mode, quality, access or transform intent.

## Review the Generated HTML

Project generation, guided project generation and operational analysis produce rich HTML reports for review. The HTML report is intentionally more useful than a collection of separate Markdown notes: it consolidates the interpreted request, evidence, generated artifacts, deterministic validation, critique, provider guidance and next actions.

Expected review artifacts:

| Artifact | Produced by | Use it for |
| --- | --- | --- |
| `AI_REVIEW.html` | `generate`, `guided-project`, project materialization helpers | Primary review surface for generated projects and provider-backed guidance. |
| `REPORT.html` | validation notebooks or exported runs | Downloadable validation summary for Databricks or local smoke tests. |
| Operational HTML output | `analyze-control-tables --format html` | Incident review, operational health, failure clusters and provider remediation guidance. |

Use Markdown or JSON for automation, but prefer HTML when the output is intended for a reviewer, screenshot, approval flow or handoff.
