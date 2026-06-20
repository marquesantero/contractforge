# Contract Draft Generation

`contractforge-ai generate-contract` creates a first draft ContractForge ingestion contract from schema/profile metadata and explicit source/target parameters.

The command is deterministic. It does not call a model provider and does not execute ContractForge.

## Basic Usage

```bash
contractforge-ai generate-contract \
  --schema schema-profile.json \
  --connector files \
  --source-path /Volumes/main/landing/orders \
  --target-catalog main \
  --target-schema bronze \
  --target-table b_orders
```

## Generated Contract Guarantees

Every generated contract includes:

```yaml
_metadata:
  generated_by: contractforge-ai
  draft: true
  review_required: true
```

This is intentional. A generated contract is a starting point for review, not an executable production decision.

## Layer Defaults

If `--mode` is not provided, the generator chooses conservative defaults:

| Layer | Default mode |
| --- | --- |
| `bronze` | `append` |
| `silver` | `hash_diff_upsert` |
| `gold` | `overwrite` |
| other | `append` |

These defaults must be reviewed. For merge-based modes, the generator may suggest a merge key candidate from not-null/key-like fields, but it cannot know the business key with certainty.

## Deterministic Validation

Generated draft contracts include a `validation` block. The validation pass runs before the result is returned and does not require Spark or the ContractForge core package.

The validator checks:

- whether the artifact is YAML serializable;
- whether `_metadata.draft: true` and `_metadata.review_required: true` are present;
- whether source connector/location fields exist;
- whether target catalog, schema and table exist;
- whether merge-based modes include merge keys;
- whether merge keys are protected by `quality_rules.not_null`;
- whether `REVIEW_REQUIRED` placeholders remain.

Validation statuses:

- `PASS`: no deterministic artifact issues were found;
- `WARN`: the artifact is structurally usable but still contains review placeholders or draft-marker issues;
- `FAIL`: required source, target, mode or merge-key structure is missing.

Example JSON excerpt:

```json
{
  "validation": {
    "status": "WARN",
    "summary": "WARN: 2 finding(s), including 0 critical, 0 high and 2 medium.",
    "findings": [
      {
        "code": "generated.review_placeholder",
        "severity": "medium",
        "path": "operations.expected_frequency"
      }
    ]
  }
}
```

## Example Input Schema

```json
{
  "columns": [
    {"name": "order_id", "type": "STRING", "nullable": false},
    {"name": "customer_email", "type": "STRING", "nullable": true},
    {"name": "amount", "type": "DOUBLE", "nullable": true}
  ]
}
```

## Review Checklist

Before using a generated contract:

- Confirm connector type and source options.
- Confirm credentials and secret references.
- Confirm target catalog, schema and table.
- Confirm write mode.
- Confirm merge keys for merge-based modes.
- Review generated PII annotations with data owners.
- Review quality rules with data stewards.
- Run ContractForge dry-run or validation when available.

## Limits

The generator cannot infer business ownership, legal classification, source completeness, SLA, runtime constraints or data product semantics from schema alone. Those decisions remain outside automatic generation.

