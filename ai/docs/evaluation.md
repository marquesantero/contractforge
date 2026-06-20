# Evaluation and Regression Fixtures

ContractForge AI uses deterministic golden fixtures before live model evaluation. These fixtures protect the stable behavior of review, explanation, suggestion and generation commands while the AI-enriched layer evolves.

The goal is not to freeze every field in every output. The goal is to protect the user-facing contract for the most important decisions:

- review status, risk and finding codes;
- failure category, risk and recommended-action count;
- metadata suggestions that affect annotations and quality rules;
- shape suggestions that affect flatten/explode decisions;
- generated contract mode, target, source schema, merge keys and validation status.

## Fixture Layout

```text
tests/fixtures/golden/
  review/
    *.yaml
    *.expected.json
  explain/
    *.json
    *.expected.json
  suggest/
    *.json
    *.expected.json
  generate/
    *.expected.json
```

Each fixture has an input file and an expected projection. Expected projections should contain stable behavior, not incidental formatting or full serialized objects.

## Running Golden Tests

```bash
PYTHONPATH=src python -m pytest tests/test_golden_fixtures.py -q
```

Golden tests are included in the default test suite.

## Updating Fixtures

When a deterministic rule changes, update the corresponding expected JSON in the same PR. The PR description should explain whether the change is:

- a bug fix in the deterministic rule;
- an intentional behavior change;
- a new supported case;
- a reduction in false positives.

Do not update expected files just to make tests pass. A changed golden fixture is evidence that user-facing behavior changed.

## Model Evaluation Boundary

Live provider evaluation is separate from golden fixtures. Unit tests must not call OpenAI, Azure OpenAI, Databricks Model Serving or any other live model provider.

Future model-enriched tests should compare:

- deterministic baseline output;
- model-enriched explanation or wording;
- schema validation result;
- redaction checks before and after model calls;
- fallback behavior when provider output is malformed or unavailable.

See [Prompt evaluation harness](prompt-evaluation.md) for deterministic prompt-template checks.

Structured model responses must pass local schema validation before they are used. This is provider-neutral: OpenAI, Azure OpenAI, Databricks Model Serving, Vertex AI or other providers may expose different structured-output APIs, but ContractForge AI still validates the response locally and falls back to deterministic output on failure.

Use [Enrichment Quality Evaluation](enrichment-evaluation.md) to compare accepted enrichment output with the deterministic baseline. This catches cases where model text removes review boundaries, hides required decisions, lacks evidence or leaks secret-like content.
