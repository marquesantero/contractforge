# Prompt Evaluation Harness

ContractForge AI treats LLM enrichment as an optional layer over deterministic output. Prompt evaluation exists to keep that layer safe before it is connected to live providers.

The current harness does not call a model. It validates prompt templates, required variables, redaction behavior, instruction boundaries and expected output schemas. This gives the project a stable base for later live-provider evals.

## Design Inputs

The implementation follows common guidance from multiple sources:

- OpenAI evaluation guidance: define objectives, datasets, metrics, compare runs and continuously evaluate changes. Source: https://platform.openai.com/docs/guides/evaluation-best-practices
- OpenAI Evals API reference: eval items are built around structured prompt/context inputs and JSON-schema output formats. Source: https://platform.openai.com/docs/api-reference/evals
- Anthropic evaluation guidance: use test cases, compare prompt versions and iterate across scenarios. Source: https://docs.anthropic.com/en/docs/test-and-evaluate/eval-tool
- Anthropic prompt structure guidance: use explicit XML-style tags to separate instructions, examples and context. Source: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags
- Google Vertex AI prompt design guidance: use clear instructions, role, context, structured prompts, output format and rigorous testing. Source: https://cloud.google.com/vertex-ai/generative-ai/docs/learn/prompts/prompt-design-strategies
- Microsoft Azure OpenAI prompt guidance: break complex tasks down, be specific, constrain output and validate model responses. Source: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/prompt-engineering
- OWASP LLM Top 10: prompt injection and insecure output handling are core risks for LLM applications. Source: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- NIST AI RMF Generative AI Profile: evaluation, risk management and governance should be part of GenAI system design. Source: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf

## Prompt Templates

List registered templates:

```bash
contractforge-ai eval-prompts --list-templates
```

Current templates:

| Template | Purpose |
| --- | --- |
| `review.enrichment.v1` | Explain and prioritize deterministic contract review findings. |
| `adapter.validation.enrichment.v1` | Explain deterministic adapter planning findings without changing adapter statuses. |
| `explain.enrichment.v1` | Enrich deterministic failure explanations from redacted run evidence. |
| `metadata.enrichment.v1` | Improve annotation and quality-rule suggestions without inventing domain policy. |
| `observability.enrichment.v1` | Explain and prioritize deterministic control-table analysis findings. |
| `project.plan.enrichment.v1` | Refine generated project plans and runbooks without hiding decisions. |
| `project.spec.enrichment.v1` | Enrich pre-generation project specifications while keeping business decisions review-bound. |
| `project.synthesis.enrichment.v1` | Review context-aware generated project scaffolds without hiding deterministic decisions. |

Each template declares:

- a version;
- required variables;
- a system instruction;
- a user prompt template;
- a strict advisory output schema;
- safety requirements.

## Run Prompt Evals

```bash
contractforge-ai eval-prompts
```

For automation:

```bash
contractforge-ai eval-prompts --format json
```

The command exits with non-zero status when any prompt case fails.

## What The Harness Checks

The deterministic harness verifies:

- required variables are present before rendering;
- secret-like values are redacted before prompt rendering;
- expected prompt fragments are present;
- forbidden prompt fragments are absent;
- adversarial text is isolated inside explicit evidence/context boundaries;
- schemas require `summary`, `evidence`, `confidence` and `review_required`;
- schemas reject additional properties.

## Validate Model Output

Use `validate-output` to check a model response before treating it as an enriched result:

```bash
contractforge-ai validate-output \
  --prompt review.enrichment.v1 \
  --input model-output.json
```

For automation:

```bash
contractforge-ai validate-output \
  --prompt review.enrichment.v1 \
  --input model-output.json \
  --fallback deterministic-result.json \
  --format json
```

The command exits with non-zero status when the output is invalid.

Validation checks:

- output must be valid JSON;
- output must be a JSON object;
- required schema fields must be present;
- `kind` must match the prompt schema;
- unsupported additional properties are rejected;
- scalar types, arrays and numeric bounds are validated;
- accepted output and deterministic fallback payloads are redacted before being returned.

When validation fails, ContractForge AI should keep the deterministic fallback available. Invalid model output must not mutate generated files, override deterministic findings or hide required decisions.

## Optional Enrichment

`review` and `explain-run` support optional model enrichment:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --with-ai --format json
```

```bash
contractforge-ai explain-run \
  --input failed-run.json \
  --with-ai \
  --format json
```

The deterministic result is still produced first and remains authoritative. Enrichment is attached under `ai_enrichment`.

Adapter-validation enrichment follows the same rule. It may explain why an AWS
or Databricks planner returned `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or
`UNSUPPORTED`, but it must not convert those statuses into `READY` or remove
required decisions from CI output.

Behavior:

- if no provider is configured, enrichment is marked `SKIPPED`;
- if the provider call fails, enrichment is marked `FAILED`;
- if the provider returns invalid structured output, enrichment is marked `FAILED`;
- if output validates against the prompt schema, enrichment is marked `ENRICHED`;
- the command exit code remains based on the deterministic command behavior, not on advisory enrichment.

Provider selection uses `CONTRACTFORGE_AI_PROVIDER` by default and can be overridden per command:

```bash
contractforge-ai review contract.yaml --with-ai --provider openai
```

Supported provider values currently include `offline`, `openai`, `azure_openai`, `databricks` and `deepseek`.

## Boundaries

Prompt evals do not replace golden regression fixtures. They validate the prompt and schema layer for future model-enriched outputs.

Prompt evals also do not validate model quality yet. Live-provider evals will be added separately and must remain opt-in, because unit tests and CI should not depend on external model calls.

## Updating Prompt Evals

When adding or changing a prompt template:

1. Add a deterministic eval case for the expected behavior.
2. Add at least one adversarial or malformed-input case when the prompt consumes logs, contracts, samples or user intent.
3. Keep secret values in fixtures synthetic.
4. Assert stable behavior through projections, not full rendered prompt snapshots.
5. Document why the prompt needs a new version if the output contract changes.
