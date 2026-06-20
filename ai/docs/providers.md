# Provider Configuration

ContractForge AI can run without a provider. Providers are needed only when a workflow calls a model for enriched explanation or generation.

## Install Provider Dependencies

```bash
pip install "contractforge-ai[openai]"
```

## Capability Registry

ContractForge AI keeps provider configuration separate from provider capabilities. The factory only creates implemented providers, while the capability registry records both implemented and planned providers so routing, evaluation and documentation can reason about provider differences explicitly.

OpenAI compatibility is not treated as a structured-output guarantee. For example, DeepSeek is OpenAI-compatible at the Chat Completions transport level, but its JSON mode is not equivalent to OpenAI strict schema enforcement. ContractForge AI therefore validates model output locally regardless of the provider-side controls.

| Provider | Status | Structured output | Transport | Databricks dependency | Primary use |
| --- | --- | --- | --- | --- | --- |
| `offline` | Implemented | None | None | None | Deterministic CI-safe workflows. |
| `openai` | Implemented | Strict schema | SDK | Optional SDK package | Strict schema-backed enrichment. |
| `azure_openai` | Implemented | Strict schema | SDK | Optional SDK package | Azure-governed strict schema-backed enrichment. |
| `deepseek` | Implemented | JSON mode only | HTTP | HTTP only | Provider diversity checks with local schema validation. |
| `databricks` | Implemented | Endpoint dependent | Platform endpoint | Platform native | Databricks-governed model serving endpoints. |
| `anthropic` | Implemented | Tool schema | HTTP | HTTP only | Tool-use based enrichment. |
| `gemini` | Implemented | Native schema | HTTP | HTTP only | Google native structured-output workflows. |
| `bedrock` | Implemented | Tool schema | SDK | Required SDK package | AWS Bedrock Converse/tool-use workflows. |

Programmatic lookup:

```python
from contractforge_ai.providers import (
    get_provider_capabilities,
    implemented_provider_names,
    planned_provider_names,
)

deepseek = get_provider_capabilities("deepseek")
assert deepseek.structured_output_strategy == "json_mode_only"
assert deepseek.needs_local_validation is True

print(implemented_provider_names())
print(planned_provider_names())
```

The registry is intentionally conservative:

- New providers should be added to the registry before routing or evaluation logic is added.
- Planned providers are visible for architecture and backlog decisions, but they are not instantiated by `create_provider`.
- Local schema validation remains the enforcement boundary even when provider-side structured output is available.

Before a provider/model is used for project planning or review enrichment, run the live provider evaluation harness:

```bash
contractforge-ai eval-provider --provider openai --format markdown
```

This does not replace product judgment. It verifies that the configured provider can answer ContractForge AI prompts with valid structured output, acceptable review boundaries and measurable latency.

## Provider Routing

`route-provider` recommends a provider for a ContractForge AI task without creating a provider client or calling a model. It is a deterministic policy layer over the capability registry.

```bash
contractforge-ai route-provider \
  --task project_planning \
  --require-strict-schema \
  --format markdown
```

Useful constraints:

| Option | Use when |
| --- | --- |
| `--require-strict-schema` | The output will drive generated artifacts and should use providers with strict schema support. |
| `--prefer-http-only` | The runtime should avoid extra SDK dependencies, common in constrained Databricks jobs. |
| `--prefer-databricks-boundary` | Model calls should stay behind Databricks Model Serving. |
| `--allow-planned` | Architecture review should include providers that are registered but not implemented yet. |
| `--allow-provider` | The organization allows only specific providers. Can be repeated. |
| `--exclude-provider` | A provider should be ruled out for policy, cost or availability reasons. Can be repeated. |

Prefer Databricks for operational failure explanation:

```bash
contractforge-ai route-provider \
  --task failure_explanation \
  --prefer-databricks-boundary
```

Prefer HTTP-only providers for review enrichment, while keeping local validation warnings visible:

```bash
contractforge-ai route-provider \
  --task review_enrichment \
  --prefer-http-only
```

Routing is intentionally explainable. The report includes scores, reasons, warnings and blockers. A provider can be OpenAI-compatible and still lose to a strict-schema provider when the task requires stronger structured-output guarantees.

## Offline Provider

The offline provider performs no network calls. It is the safe default for deterministic-only workflows.

```bash
export CONTRACTFORGE_AI_PROVIDER=offline
```

## OpenAI

```bash
export CONTRACTFORGE_AI_PROVIDER=openai
export CONTRACTFORGE_AI_MODEL=gpt-4.1
export OPENAI_API_KEY=...
```

Optional settings:

```bash
export OPENAI_ORG_ID=...
export OPENAI_PROJECT=...
export CONTRACTFORGE_AI_TIMEOUT=30
export CONTRACTFORGE_AI_MAX_RETRIES=2
```

## Azure OpenAI

```bash
export CONTRACTFORGE_AI_PROVIDER=azure_openai
export CONTRACTFORGE_AI_MODEL=<deployment-name>
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
export AZURE_OPENAI_API_VERSION=<api-version>
```

Aliases:

```bash
export CONTRACTFORGE_AI_ENDPOINT=https://<resource>.openai.azure.com
export CONTRACTFORGE_AI_API_KEY=...
export CONTRACTFORGE_AI_API_VERSION=<api-version>
```

## Databricks Model Serving

Use the Databricks provider when AI calls should stay inside the Databricks platform boundary or when the workspace already exposes a model serving endpoint.

```bash
export CONTRACTFORGE_AI_PROVIDER=databricks
export CONTRACTFORGE_AI_MODEL=<serving-endpoint-name>
export DATABRICKS_HOST=https://<workspace-host>
export DATABRICKS_TOKEN=<token>
```

Aliases:

```bash
export DATABRICKS_SERVING_ENDPOINT=<serving-endpoint-name>
export DATABRICKS_MODEL_SERVING_ENDPOINT=<serving-endpoint-name>
export CONTRACTFORGE_AI_ENDPOINT=https://<workspace-host>
export CONTRACTFORGE_AI_API_KEY=<token>
```

Example:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml \
  --with-ai \
  --provider databricks \
  --format json
```

The provider invokes:

```text
POST <DATABRICKS_HOST>/serving-endpoints/<endpoint-name>/invocations
```

with a chat-style `messages` payload. It extracts text from common response shapes such as `choices[].message.content`, `output_text`, `text`, `response`, `result` or `predictions`.

If running inside a Databricks notebook and explicit host/token values are not configured, the provider attempts to read notebook context authentication when available. For jobs and CI, prefer explicit environment variables or Databricks secrets injected into the runtime.

Databricks provider output still passes through local structured-output validation. Invalid provider output does not replace deterministic ContractForge AI results.

## DeepSeek

Use the DeepSeek provider when model enrichment should call DeepSeek directly through its OpenAI-compatible Chat Completions API. This provider does not require the OpenAI SDK.

```bash
export CONTRACTFORGE_AI_PROVIDER=deepseek
export CONTRACTFORGE_AI_MODEL=deepseek-chat
export DEEPSEEK_API_KEY=<api-key>
```

Optional settings:

```bash
export DEEPSEEK_BASE_URL=https://api.deepseek.com
export CONTRACTFORGE_AI_TIMEOUT=30
export CONTRACTFORGE_AI_MAX_RETRIES=2
```

Generic aliases are also supported:

```bash
export CONTRACTFORGE_AI_API_KEY=<api-key>
export CONTRACTFORGE_AI_ENDPOINT=https://api.deepseek.com
```

For structured enrichment, ContractForge AI asks DeepSeek for JSON mode and then validates the returned JSON against ContractForge AI's local schema. This is intentionally different from OpenAI's strict Responses API schema path: provider-specific request controls are useful, but local validation remains the actual enforcement boundary.

Example:

```bash
contractforge-ai plan-project \
  "Create a silver ingestion from s3a://landing/orders into main.silver.orders using hash_diff_upsert" \
  --with-ai \
  --provider deepseek \
  --format json
```

## Anthropic

Use the Anthropic provider when model enrichment should call Anthropic directly through the Messages API. This provider uses direct HTTP and does not require an Anthropic SDK.

```bash
export CONTRACTFORGE_AI_PROVIDER=anthropic
export CONTRACTFORGE_AI_MODEL=claude-sonnet-4-5
export ANTHROPIC_API_KEY=<api-key>
```

Optional settings:

```bash
export ANTHROPIC_BASE_URL=https://api.anthropic.com
export ANTHROPIC_VERSION=2023-06-01
export CONTRACTFORGE_AI_TIMEOUT=30
export CONTRACTFORGE_AI_MAX_RETRIES=2
```

Generic aliases are also supported:

```bash
export CONTRACTFORGE_AI_API_KEY=<api-key>
export CONTRACTFORGE_AI_ENDPOINT=https://api.anthropic.com
export CONTRACTFORGE_AI_API_VERSION=2023-06-01
```

For structured enrichment, ContractForge AI sends the prompt schema as an Anthropic tool `input_schema` and forces `tool_choice` to that tool. Tool-use responses are converted back to JSON text and then validated locally by ContractForge AI. Local validation remains required because tool schema is not treated as the same guarantee as OpenAI strict schema.

Example:

```bash
contractforge-ai eval-provider \
  --provider anthropic \
  --prompt project.plan.enrichment.v1 \
  --format markdown
```

## Google Gemini API

Use the Gemini provider when model enrichment should call Google's Gemini API directly through `generateContent`. This provider uses direct HTTP, stores the API key in the `x-goog-api-key` header and does not require a Google SDK package.

```bash
export CONTRACTFORGE_AI_PROVIDER=gemini
export CONTRACTFORGE_AI_MODEL=gemini-2.5-flash
export GEMINI_API_KEY=<api-key>
```

Optional settings:

```bash
export GEMINI_BASE_URL=https://generativelanguage.googleapis.com
export GEMINI_API_VERSION=v1beta
export CONTRACTFORGE_AI_TIMEOUT=30
export CONTRACTFORGE_AI_MAX_RETRIES=2
```

Generic aliases are also supported:

```bash
export CONTRACTFORGE_AI_API_KEY=<api-key>
export CONTRACTFORGE_AI_ENDPOINT=https://generativelanguage.googleapis.com
export CONTRACTFORGE_AI_API_VERSION=v1beta
```

For structured enrichment, ContractForge AI sends `generationConfig.responseMimeType=application/json` and the requested local schema as `generationConfig.responseJsonSchema`. Gemini's native schema controls improve output shape, but ContractForge AI still validates the returned JSON locally before trusting it.

The provider invokes:

```text
POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent
```

with `contents`, optional `systemInstruction` and optional `generationConfig`. If `CONTRACTFORGE_AI_ENDPOINT` already points to a full `:generateContent` URL, the provider uses that URL as-is.

Example:

```bash
contractforge-ai eval-provider \
  --provider gemini \
  --prompt project.plan.enrichment.v1 \
  --format markdown
```

## AWS Bedrock

Use the Bedrock provider when model enrichment should run through AWS Bedrock Runtime and the environment already has an AWS identity model. This provider uses `boto3` and the standard AWS credential chain instead of accepting raw access keys in ContractForge AI configuration.

Install the AWS extra:

```bash
pip install "contractforge-ai[aws]"
```

Configure the provider:

```bash
export CONTRACTFORGE_AI_PROVIDER=bedrock
export CONTRACTFORGE_AI_MODEL=anthropic.claude-3-5-sonnet-20240620-v1:0
export AWS_REGION=us-east-1
```

Optional settings:

```bash
export BEDROCK_ENDPOINT_URL=https://bedrock-runtime.us-east-1.amazonaws.com
export CONTRACTFORGE_AI_TIMEOUT=30
export CONTRACTFORGE_AI_MAX_RETRIES=2
```

Authentication should come from AWS-supported mechanisms such as instance profiles, environment variables, shared config profiles, Databricks secrets injected as environment variables, or workload identity patterns supported by the runtime. ContractForge AI does not introduce custom access-key fields for Bedrock.

For structured enrichment, ContractForge AI sends the local schema as a Bedrock Converse `toolConfig.tools[].toolSpec.inputSchema.json` and requests that tool through `toolChoice` when a schema is provided. Tool-use responses are converted back to JSON text and then validated locally.

The provider invokes:

```text
bedrock-runtime.converse(modelId=..., messages=..., system=..., inferenceConfig=..., toolConfig=...)
```

Example:

```bash
contractforge-ai eval-provider \
  --provider bedrock \
  --prompt project.plan.enrichment.v1 \
  --format markdown
```

## Provider Boundary

Providers should only receive prepared prompt/context strings. They should not:

- read local files;
- call Databricks;
- resolve secrets;
- query control tables;
- mutate contracts;
- execute remediation.

This boundary keeps provider implementations small and makes the security model easier to audit.

## Provider-Neutral Design

Provider documentation is necessary for API details, but product behavior should not be designed around one vendor. When adding a provider or AI workflow, compare current guidance across relevant ecosystems:

- OpenAI for Responses API, structured outputs and production controls.
- Anthropic for prompt structure, tool-use boundaries and long-context practices.
- Google Gemini for structured output and multimodal/file-aware workflows.
- Azure OpenAI for enterprise deployment, identity, network and governance constraints.
- Databricks Mosaic AI for notebook/runtime integration and lakehouse-native model serving.

The provider interface should stay narrow enough that these implementations can coexist without leaking provider-specific behavior into reviewers, explainers or generators.

## Error Handling

Provider configuration errors should be actionable and redacted. Missing endpoint, model, deployment or key values should fail before any model call is attempted.
