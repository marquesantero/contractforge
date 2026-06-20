# Enrichment Quality Evaluation

`eval-enrichment` evaluates provider-backed enrichment against the deterministic baseline. It is provider-free and suitable for CI: the command reads JSON files, checks review boundaries and returns a deterministic PASS/WARN/FAIL report.

Use it when a workflow stores model-enriched output and needs to prove that the enrichment did not hide required decisions, remove review boundaries or make unsupported claims.

## Command

```bash
contractforge-ai eval-enrichment \
  --deterministic deterministic.json \
  --enrichment enriched.json \
  --kind project_plan \
  --format markdown
```

The enrichment file can be either the direct enrichment object:

```json
{
  "status": "ENRICHED",
  "provider": "databricks",
  "data": {
    "kind": "project_plan",
    "summary": "Use ContractForge YAML first and review merge keys.",
    "recommendations": ["Keep merge key review as a required decision."],
    "evidence": ["Deterministic planner status NEEDS_DECISIONS."],
    "decisions_required": ["Confirm merge keys."],
    "confidence": 0.82,
    "review_required": true
  }
}
```

Or a full command payload containing `ai_enrichment`:

```json
{
  "status": "NEEDS_DECISIONS",
  "intent": {},
  "ai_enrichment": {
    "status": "ENRICHED",
    "provider": "databricks",
    "data": {
      "kind": "project_plan",
      "summary": "Use ContractForge YAML first and review merge keys.",
      "recommendations": ["Keep merge key review as a required decision."],
      "evidence": ["Deterministic planner status NEEDS_DECISIONS."],
      "decisions_required": ["Confirm merge keys."],
      "confidence": 0.82,
      "review_required": true
    }
  }
}
```

## What Is Evaluated

The report checks:

- Enrichment status: `ENRICHED`, `SKIPPED` or `FAILED`.
- Expected `kind`, when supplied.
- Non-empty summary.
- Evidence presence.
- Actionable recommendations.
- Confidence in the range `0..1`.
- `review_required` boundary.
- Preservation of deterministic `decisions_required` and `missing_fields`.
- Secret-like fields or inline assignments such as `token=...` and `password:...`.

## Status

| Status | Meaning |
| --- | --- |
| `PASS` | Enrichment preserves deterministic boundaries and provides usable evidence. |
| `WARN` | Enrichment is not blocking, but should be reviewed. Example: provider was skipped. |
| `FAIL` | Enrichment should not be trusted. The deterministic baseline remains authoritative. |

`eval-enrichment` exits with a non-zero code on `FAIL`, making it usable in CI gates.

## Review Boundary

This command does not call a model provider. It evaluates already-produced enrichment. The goal is to make provider-backed output measurable before it appears in pull-request comments, generated runbooks or planning reports.

Recommended workflow:

1. Produce deterministic output.
2. Optionally attach `ai_enrichment` with `--with-ai`.
3. Run `eval-enrichment` against the deterministic baseline and enriched payload.
4. Fail CI or require review when enrichment hides decisions or lacks evidence.

## Live Provider Evaluation

`eval-provider` calls a configured provider against a small suite of registered prompt templates. Use it before promoting a provider/model for real ContractForge AI workflows, especially when comparing providers with different structured-output guarantees.

```bash
contractforge-ai eval-provider \
  --provider deepseek \
  --format markdown
```

Evaluate one prompt template:

```bash
contractforge-ai eval-provider \
  --provider openai \
  --prompt project.plan.enrichment.v1 \
  --format json
```

The command records:

- Provider capability metadata from the provider registry.
- Prompt-level execution status.
- Latency in milliseconds.
- Structured-output validation status.
- Enrichment-quality status after schema validation succeeds.
- Provider execution errors, invalid JSON, schema failures and review-boundary failures.

The default suite currently exercises:

- `review.enrichment.v1`
- `explain.enrichment.v1`
- `project.plan.enrichment.v1`

The command is intentionally opt-in. Unit tests use fake providers; real providers should be evaluated from local development, a Databricks notebook or a controlled CI job with explicit secrets. Provider output remains advisory even when `eval-provider` passes.
