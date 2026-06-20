# ContractForge AI

ContractForge AI is the planning, review and diagnostics companion for
ContractForge. It helps translate user intent into deterministic project inputs,
then lets ContractForge Core and the adapter planners decide whether the result
is valid, review-required or unsafe.

The important boundary is simple: AI is advisory; deterministic validation is
authoritative.

## Product Role

ContractForge AI helps with:

- intent-first project generation from prompts and schema evidence;
- project-folder validation across `project.yaml`, environments, reusable
  connections and split contracts;
- adapter-aware planning checks when adapter packages are installed;
- rich HTML review reports such as `AI_REVIEW.html`;
- provider-backed explanation and enrichment when a model provider is
  configured;
- failure explanation from ContractForge run/error evidence;
- repository instruction and local knowledge-index generation.

It does not bypass core validation, adapter capability checks or human review
for unsafe platform decisions.

## Deterministic Gate

The generation flow is intentionally conservative:

1. Read prompt, schema evidence, samples or project context.
2. Extract intent into a normalized project plan.
3. Generate ContractForge project files deterministically.
4. Validate contracts with `contractforge-core`.
5. Optionally call installed adapter planners.
6. Record warnings, blockers, prompts, assumptions and generated YAML in a
   review report.

Provider output can enrich the plan, but it cannot silently overwrite identity
fields such as connector, target, write mode, layer or deployment runtime. When
the provider proposes behavior-changing fields, ContractForge AI records the
proposal as review-required unless the deterministic gate can prove it is safe.

## Installation

```bash
pip install contractforge-ai
```

Install adapter extras only when AI workflows need adapter-aware validation:

```bash
pip install "contractforge-ai[databricks]"
pip install "contractforge-ai[aws-adapter]"
pip install "contractforge-ai[snowflake-adapter]"
pip install "contractforge-ai[fabric-adapter]"
pip install "contractforge-ai[gcp-adapter]"
```

## Generate A Project

```bash
contractforge-ai generate \
  --prompt "Create a bronze to gold orders pipeline from main.raw.orders_sample. Silver must use hash_diff_upsert and gold should aggregate revenue by day." \
  --schema schemas/orders.json \
  --output-dir generated/orders-medallion
```

The output should include project files, contracts and an `AI_REVIEW.html`
report with inputs, prompts, generated YAML, decisions, warnings and validation
status.

## Validate A Project

```bash
contractforge-ai validate-project-structure generated/orders-medallion \
  --adapter databricks \
  --adapter aws \
  --adapter snowflake \
  --adapter fabric \
  --adapter gcp \
  --format html > generated/orders-medallion/project_validation.html
```

Adapter-aware validation calls public adapter planners. It does not deploy
infrastructure or run platform jobs.

## Provider-Backed Enrichment

Model providers can add explanation, suggestions and light inference, but every
provider-backed result remains subject to deterministic validation:

```bash
contractforge-ai generate \
  --prompt "Create a portable movie ingestion project from a SQL table and produce gold rating summaries." \
  --schema schemas/movie_ratings.json \
  --with-ai \
  --provider openai \
  --output-dir generated/movie
```

Use provider enrichment for review quality, not for bypassing missing contract
decisions. Unknown keys, unsafe secrets, unsupported runtime fields and
conflicting identity fields must be rejected or marked review-required.

## Current Stability

`contractforge-ai` is currently an alpha companion package. The deterministic
validation boundary is the stable design principle; prompt templates, provider
routing and generated report layout may still change in minor versions before a
future `1.0` API freeze.

See the package guide in [ai/README.md](../ai/README.md) for the full CLI
surface and provider configuration details.
