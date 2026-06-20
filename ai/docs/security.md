# Security Model

ContractForge AI is designed as an advisory layer. It should not own production credentials, mutate contracts automatically or query operational systems from provider code.

## Core Principles

- Deterministic checks run without model providers.
- Secrets are redacted before context reaches any provider.
- Providers receive prepared prompts/context only.
- Provider implementations do not read files, resolve secrets or query Databricks.
- Unit tests must not call external model APIs.
- AI output is advisory and must remain reviewable.

## Redaction

The redaction layer removes common secret-bearing fields before evidence is passed to reviewers, explainers or providers. Examples include:

- `password`
- `secret`
- `token`
- `api_key`
- `access_key`
- `private_key`
- `credential`
- `sas`

Secret reference templates such as `{{ secret:scope/key }}` are also redacted.

Free-form text can also contain inline secret assignments. ContractForge AI redacts common patterns such as `token=...`, `password:...`, `api_key=...` and `sas=...` before provider enrichment. This matters for natural-language planning because users may paste connection notes directly into an intent.

## Prompt Injection Boundary

Operational evidence can contain hostile or misleading text, especially when it includes API responses, file content, stack traces or row samples. Treat all external data as untrusted.

Safe implementation rules:

- Do not let evidence override system/developer instructions.
- Do not allow providers to execute actions directly.
- Do not include credentials, raw tokens or unredacted request headers in prompts.
- Prefer structured output and schema validation when provider enrichment is added.
- Keep deterministic classifiers as the source of truth for CI and regression tests.

## Data Minimization

Only include the context required for the task:

- For contract review, include contract fields and relevant metadata.
- For failure explanation, include run/error evidence and redacted source metadata.
- For future annotation or quality suggestions, prefer schema and profiles over raw data.
- For future RAG workflows, retrieve narrow documentation slices instead of broad repositories.

## Provider Risk

Providers are optional. Teams should choose a provider based on their security boundary:

- Use offline/deterministic mode for CI baseline checks.
- Use Azure OpenAI when enterprise policy requires Azure-hosted model access.
- Use Databricks Model Serving when model calls should remain inside the Databricks platform boundary.
- Use OpenAI directly when that is acceptable for the environment.

## Research Baseline

AI implementation guidance changes quickly. Before implementing AI-facing features, compare current guidance from multiple sources instead of relying on a single provider's documentation.

Recommended source categories:

- Provider documentation: OpenAI, Anthropic, Google Gemini, Azure OpenAI and Databricks Mosaic AI.
- Security and risk frameworks: OWASP Top 10 for LLM Applications and NIST AI Risk Management Framework.
- RAG and evaluation frameworks: LangChain/LangSmith, LlamaIndex and RAGAS-style evaluation literature.
- Platform documentation for the target runtime, especially Databricks when control-table evidence or notebooks are involved.

Use provider docs for API-specific behavior, but use cross-provider and independent sources for implementation patterns such as prompt-injection defense, retrieval evaluation, output validation, observability and regression testing.
