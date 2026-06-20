# Metadata and Quality Suggestions

`contractforge-ai suggest-metadata` generates draft `annotations` and `quality_rules` from schema/profile metadata.

The command is deterministic. It does not call a model provider and does not mutate files.

## Input Format

JSON:

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

YAML:

```yaml
columns:
  customer_id:
    type: string
    nullable: false
  customer_email:
    type: string
    nullable: true
  status:
    type: string
    nullable: false
    profile:
      distinct_values: [open, closed, cancelled]
```

## Generate YAML Blocks

```bash
contractforge-ai suggest-metadata --schema schema-profile.json --format yaml
```

The output is intended to be reviewed and copied into ContractForge contracts:

```yaml
annotations:
  table: {}
  columns:
    customer_email:
      description: Customer Email value (string).
      pii:
        enabled: true
        type: email
        sensitivity: restricted
quality_rules:
  not_null:
    - customer_id
    - status
  accepted_values:
    status:
      - open
      - closed
      - cancelled
```

## Evidence and Confidence

Use text or JSON output when you need to inspect why a suggestion was made:

```bash
contractforge-ai suggest-metadata --schema schema-profile.json --format json
```

Each suggestion includes:

- `kind`: suggestion category.
- `target`: column or contract section.
- `value`: proposed value.
- `confidence`: numeric confidence from deterministic heuristics.
- `evidence`: facts used to produce the suggestion.

## Current Heuristics

- Column names such as `email`, `phone`, `cpf`, `ssn`, `tax_id` and `credit_card` produce PII candidates.
- Columns with `nullable=false` produce `quality_rules.not_null`.
- Key-like names such as `id`, `customer_id`, `uuid` and `guid` produce key tags and `not_null`.
- Small observed value sets produce `accepted_values`.
- Numeric measure names such as `amount`, `price`, `cost`, `revenue`, `quantity` and `total` produce non-negative expression suggestions.
- Timestamp-like names produce timestamp tags.

## Limits

The generator is conservative by design. It cannot know business ownership, legal classification, domain semantics or required quality policy from schema alone. Treat output as a draft for data stewards and engineers.

