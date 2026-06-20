# Evidence and Confidence Model

ContractForge AI treats every recommendation as advisory output backed by explicit evidence, confidence and review boundaries. This model is deterministic and provider-neutral. Future model-enriched features must attach to this model instead of replacing it.

## Core Objects

### `EvidenceItem`

Represents one fact used to justify an output.

Fields:

- `source`: where the evidence came from, such as `schema`, `profile`, `contract`, `sample` or `run_evidence`.
- `path`: optional path inside the input, such as `columns.customer_email.name`.
- `reason`: why this evidence matters.
- `value`: optional observed value or summary.
- `confidence`: optional numeric confidence for this evidence item.

Example:

```json
{
  "source": "schema",
  "path": "columns.customer_email.name",
  "reason": "Column name matched PII pattern for email.",
  "value": "customer_email",
  "confidence": 0.94
}
```

### `Assumption`

Represents something the tool inferred but cannot prove from the supplied evidence.

Fields:

- `statement`: the assumption.
- `confidence`: deterministic confidence score.
- `review_required`: whether it must be confirmed.
- `evidence`: optional supporting evidence.

Example:

```json
{
  "statement": "First not_null column may be the merge key.",
  "confidence": 0.6,
  "confidence_level": "medium",
  "review_required": true
}
```

### `RequiredDecision`

Represents a decision that must be made before output can be treated as production-ready.

Fields:

- `question`: the decision the user must make.
- `reason`: why the tool cannot safely decide automatically.
- `path`: optional contract or artifact path.
- `options`: optional candidate options.

Example:

```json
{
  "question": "Confirm merge_keys",
  "reason": "Merge keys are business decisions.",
  "path": "merge_keys",
  "options": ["customer_id", "order_id"]
}
```

### `Traceability`

Groups confidence, evidence, assumptions and required decisions for a result.

Fields:

- `confidence`: numeric score from `0.0` to `1.0`.
- `confidence_level`: deterministic bucket: `low`, `medium` or `high`.
- `review_required`: `true` when output needs confirmation.
- `evidence`: list of `EvidenceItem`.
- `assumptions`: list of `Assumption`.
- `decisions_required`: list of `RequiredDecision`.

## Confidence Rubric

Confidence buckets are intentionally simple and stable:

- `high`: score is greater than or equal to `0.80`.
- `medium`: score is greater than or equal to `0.55` and lower than `0.80`.
- `low`: score is lower than `0.55`.

This rubric is not a business-quality score. It describes how strongly the tool can justify its recommendation from the supplied evidence.

## Where Traceability Appears

Current outputs include a `traceability` block in:

- contract review results;
- failure explanations;
- metadata and quality suggestions;
- shape suggestions;
- draft contract generation.

Individual suggestions and findings can also carry local evidence. This keeps output useful in CI, notebooks and future AI-enriched review flows.

## Design Rules

- Deterministic evidence is the source of truth.
- Low-confidence or business-semantic decisions must be marked for review.
- LLM enrichment may improve wording, prioritization or alternatives, but must not remove evidence or decisions.
- Invalid or unstructured model output should fall back to the deterministic result.
- Secrets must be redacted before evidence is assembled for any model-facing context.
