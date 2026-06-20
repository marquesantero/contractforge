# Architecture

ContractForge AI is organized around a simple boundary: collect safe context, run deterministic checks, optionally ask a provider for enrichment, and return structured output.

```text
contract / run evidence / sample data
        |
        v
context collectors + redaction
        |
        v
deterministic analyzers
        |
        v
traceability model
        |
        v
optional model provider
        |
        v
structured recommendation
```

## Package Layout

```text
src/contractforge_ai/
  cli.py                  # command line interface
  models.py               # shared dataclasses and traceability model
  context/                # context loading and redaction
  reviewers/              # contract review logic
  generators/             # future contract/shape/annotation generators
  explainers/             # future run failure explainers
  onboarding/             # integration profiles and environment discovery
  projects/               # project artifact model and safe writer
  providers/              # model provider abstraction
  prompts/                # prompt templates
```

## Provider Boundary

Providers receive already-redacted context and return plain text or structured JSON. They should not read files, query Databricks or resolve secrets directly. This keeps security and observability controlled by the ContractForge AI layer.

Current provider implementations are intentionally thin:

- `OfflineProvider` returns deterministic text and never performs network calls.
- `OpenAIProvider` uses the OpenAI SDK lazily and sends requests through the Responses API surface.
- `AzureOpenAIProvider` uses explicit Azure endpoint, deployment/model and API version configuration.
- `DatabricksModelServingProvider` calls Databricks Model Serving with a narrow chat-style request boundary.
- `DeepSeekProvider` calls DeepSeek's OpenAI-compatible Chat Completions API and relies on local schema validation for structured output enforcement.
- `AnthropicProvider` calls Anthropic Messages API over HTTP and uses tool `input_schema` for structured output before local validation.
- `GeminiProvider` calls Google Gemini `generateContent` over HTTP and uses native JSON response schema before local validation.
- `BedrockProvider` calls AWS Bedrock Runtime Converse through `boto3` and uses tool `inputSchema.json` before local validation.

Provider capability metadata lives beside the provider implementations, but it is not the provider factory. The registry records implemented and planned providers, their transport model, structured-output strategy and Databricks runtime dependency. This keeps future routing decisions explicit: a provider can be OpenAI-compatible for transport while still requiring local JSON/schema validation because its structured-output guarantee is weaker.

The package imports provider SDKs only when a provider instance is created. This keeps deterministic review available in CI without OpenAI dependencies.

## Review Boundary

The reviewer should not rely only on LLM reasoning. Known operational risks should be implemented as deterministic rules first. Model output can explain tradeoffs, prioritize findings or propose improved contract snippets.

Contract review has two explicit modes. Standalone review evaluates the file exactly as provided and reports missing governance metadata when annotations or operations are absent. Bundle-aware review is opt-in and loads sibling `.annotations.*` and `.operations.*` files for the same `.ingestion.*` contract before running governance checks. This preserves strict CI behavior for isolated files while supporting ContractForge repositories that intentionally separate ingestion, annotations and operations contracts.

## Evidence and Confidence Boundary

All advisory outputs should carry traceability data. The shared model includes evidence items, confidence levels, assumptions and required decisions. This keeps future AI enrichment grounded in deterministic facts and makes CI output reviewable without model access.

Confidence is a justification score, not a guarantee that the generated contract or suggestion is correct for a business domain. Any output that depends on ownership, merge keys, source completeness, PII policy, grain or runtime deployment choices should remain review-required.

See [Evidence and confidence model](evidence.md) for the concrete schema and rubric.

## Failure Explanation Boundary

The failure explainer accepts already-collected run evidence as JSON. This keeps the first implementation independent from Databricks connectivity and makes it easy to test with fixtures. Future collectors can read directly from `ctrl_ingestion_runs`, `ctrl_ingestion_errors`, `ctrl_ingestion_quality` and stream control tables, but they should still normalize evidence into the same redacted structure before classification.

The initial explainer uses deterministic pattern classification for recurring operational failures:

- Authentication and authorization.
- Network, DNS and egress.
- Cloud storage access.
- Schema, SQL and type compatibility.
- Quality gate failures.
- Missing dependencies, libraries and drivers.
- Runtime capability limitations.
- API rate limit or quota failures.

Model-enriched explanations can be added later, but deterministic classification remains the source of truth for CI and regression tests.

## Operational Analysis Boundary

Operational analysis is broader than single-run explanation. It accepts redacted ContractForge evidence for runs, errors, quality, quarantine, streams, schema changes, lineage, annotations, access, operations, cost, state and collection errors, then computes deterministic metrics and findings before any provider is called.

The analyzer should detect aggregate risks such as repeated failures, quality instability, quarantine volume, schema drift, stream metric inconsistencies, governance application failures, missing cost evidence, stale state and latency outliers. Provider enrichment may explain prioritization or remediation sequencing, but it must not change deterministic status, risk or evidence.

This layer intentionally starts from JSON evidence rather than direct platform queries. Databricks collectors, AWS Athena/Iceberg collectors and future platform collectors can all feed the same analyzer without coupling it to Spark, boto3 or any adapter runtime.

## Metadata Suggestion Boundary

Metadata suggestions are generated from schema/profile evidence and returned as reviewable drafts. The generator can suggest annotations, PII candidates, key/timestamp tags, `not_null`, accepted values and simple non-negative expressions when evidence is strong enough.

The generator must not:

- mutate contract files automatically;
- claim business definitions without evidence;
- mark sensitive data without explaining why;
- infer row-level policy or masking behavior;
- replace stewardship review.

When LLM enrichment is added, deterministic evidence should remain attached to every suggestion so reviewers can distinguish observed facts from model interpretation.

## Shape Suggestion Boundary

Shape suggestions are generated from sample JSON and should be treated as draft transformation plans. The generator can discover primitive paths, nested structs, arrays, arrays of structs and nested arrays.

Array handling is intentionally conservative. Explode operations are emitted with `requires_review` and decision notes because they can multiply row counts and change table grain. The generator should never silently choose business grain, deduplication keys or explode order for the user.

When model enrichment is added, it may explain alternatives, but cardinality-changing operations must remain explicit and reviewable.

## Contract Draft Boundary

Contract generation produces first drafts, not production-ready contracts. Draft contracts must carry `_metadata.draft: true` and `_metadata.review_required: true`.

The generator can assemble source, target, layer, mode, schema, quality, annotations and operations starter blocks. It must also return assumptions and required decisions. Merge keys, credentials, source completeness, governance ownership and runtime-specific options remain reviewed decisions.

Generated contracts should be validated with `contractforge-core`. The validation adapter avoids platform execution and treats ContractForge semantic normalization as the source of truth.

## Project Generation Boundary

Project generation uses a normalized `ProjectPlan` before any files are written. A plan contains artifacts, a review report and traceability. This lets generators produce complete project structures for ContractForge YAML, Python, Databricks Asset Bundles, dbt or classic PySpark without coupling generation to the filesystem.

Generated projects include review artifacts by default: `README.md` for usage, `DECISIONS.md` for unresolved assumptions, `RUNBOOK.md` for operational execution and `VALIDATION.md` for deterministic validation evidence. ContractForge AI requires `contractforge-core` and uses it for contract validation and semantic normalization. This validation path does not require Spark and does not execute ingestion.

Generated artifact naming also delegates to ContractForge Core. ContractForge AI uses `contractforge_core.naming.derive_names` for contract basenames, bundle names, job names and task keys. Physical target identifiers remain user input and are not rewritten by the AI layer.

Context-aware project generation builds a `ProjectContextPackage` before generation. The package records user intent, runtime hints, discovered sample files, inferred schema evidence, warnings and required decisions. Supported local samples include JSON, JSONL/NDJSON and CSV. Inferred schema profiles are review aids, not source-of-truth contracts; generated projects attach `CONTEXT.md` and `context/context-package.json` so reviewers can see exactly which evidence was used.

AI-first guided generation uses an `EnrichedProjectSpec` between planning and artifact generation. The deterministic planner creates the initial spec from intent and context. When `guided-project --with-ai` is enabled, the provider receives the spec, user intent, context package and ContractForge capability summary through `project.spec.enrichment.v1`. The response must be structured JSON and pass local schema validation before any field is used.

Provider-backed spec enrichment is allowed to improve low-risk, evidence-backed technical fields such as source format, full ContractForge `transform` blocks, draft quality rules, annotations and operations metadata. The allowlist is enforced in code. Unsupported fields become required decisions instead of hidden mutations.

`transform` is the canonical provider surface for transformations. Shape-specific updates are still accepted for compatibility, but new enrichment should preserve the complete ContractForge transform structure so future transformation capabilities can pass through the same validation and rendering path.

Critical business decisions remain review-required even when the provider suggests them. Examples include merge keys, hash-diff columns, owner, SLA, deletion semantics, legal PII policy and credentials. The provider can propose candidates, but the generated project must still expose the decision boundary.

Provider-backed project synthesis remains a post-generation review layer over the generated project and context package. The `project.synthesis.enrichment.v1` prompt can improve the review narrative, but it does not override deterministic validation or the enriched spec. Local schema validation and deterministic review remain the authority because provider structured-output behavior is not treated as a portable validation runtime.

Report translation is another post-rendering layer. ContractForge AI renders the canonical English Markdown/HTML report first, then a configured provider may translate narrative prose for a requested `language`. Technical labels, status values, paths, code, JSON/YAML and identifiers remain in English to preserve supportability and avoid changing machine-facing semantics.

Generated review output is intentionally consolidated. The primary review
artifact is `AI_REVIEW.html`; it should contain the interpreted request,
evidence, generated artifacts, required decisions, deterministic validation,
critique and provider guidance. Markdown and JSON outputs remain available for
automation, but generated project directories should avoid scattering review
context across many small prose files.

Project patching is a separate safety boundary from greenfield generation. The
patch planner represents create/skip/conflict decisions before writing files,
preserves existing reviewed artifacts by default and prevents path traversal.
This supports workflows where a user asks ContractForge AI to complete or extend
an existing project rather than replace it.

The writer is intentionally narrow:

- it writes only relative artifact paths;
- it rejects path traversal;
- it skips existing files by default;
- it overwrites only with an explicit force option;
- it supports dry-run output.

This boundary will be reused by onboarding, scaffold generators and future agent/IDE integration.

## Onboarding Boundary

Onboarding is a deterministic setup layer. It defines supported integration profiles and discovers local environment capabilities without resolving secrets or calling a model provider.

Integration profiles make expectations explicit for:

- local CLI usage;
- GitHub Actions and other CI runners;
- Databricks notebooks;
- Databricks jobs and Databricks Asset Bundles;
- coding assistant instructions;
- future MCP/tool integrations.

Environment discovery reports package availability, command availability, provider-related environment variables with redacted values and Databricks runtime hints. It is intended for setup checks, support bundles and CI diagnostics. It must not print raw tokens, API keys, passwords or private material.

The onboarding layer should stay independent from provider implementations. Missing provider configuration is reported as setup evidence; provider clients are not created during environment discovery.

## Implementation Standards

Before implementing an AI-facing issue, research current practices for the relevant capability. Do not limit the review to one provider. Compare API-specific documentation with broader implementation guidance from providers, security frameworks and RAG/evaluation ecosystems.

The research pass should cover:

- Provider API behavior and current SDK surface.
- Structured output and schema validation support.
- Prompt engineering patterns from multiple providers.
- Prompt-injection and data-exfiltration risks.
- Redaction and data minimization.
- RAG design, retrieval evaluation and grounding checks when retrieval is involved.
- Observability, tracing and regression evaluation.
- Unit, integration and eval test strategy.

The implementation should capture the resulting decisions in the PR or technical notes.

LLM calls should be excluded from unit tests. Provider integrations should use mocked clients and fixtures. Real provider calls belong in explicitly marked integration tests or external validation workflows.

## Golden Regression Fixtures

The deterministic layer is protected by golden fixtures under `tests/fixtures/golden`. These tests compare stable behavioral projections for contract review, failure explanation, metadata suggestions, shape suggestions and contract generation.

Golden fixtures are intentionally narrower than full snapshots. They assert the fields that represent user-facing decisions, such as finding codes, failure category, merge keys, validation status and cardinality-changing shape operations. This avoids brittle formatting tests while still making behavior changes visible in PRs.

See [Evaluation and regression fixtures](evaluation.md) for fixture layout and update rules.
