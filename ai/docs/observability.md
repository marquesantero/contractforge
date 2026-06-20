# Operational Analysis

`contractforge-ai analyze-control-tables` analyzes ContractForge evidence across runs, errors, quality checks, quarantine, streams, schema changes, lineage, governance, operations, state and cost.

The analyzer is intentionally evidence-file based. It does not query Databricks or AWS directly. This keeps the analysis deterministic, testable in CI and reusable from Databricks notebooks, AWS Athena exports or any collector that has already gathered ContractForge evidence rows.

## Input Shape

Use a JSON object with any of the following arrays:

```json
{
  "scope": {
    "platform": "databricks",
    "catalog": "main",
    "ctrl_schema": "ops",
    "target_table": "main.silver.orders",
    "window": "last 7 days"
  },
  "runs": [],
  "errors": [],
  "quality": [],
  "quarantine": [],
  "streams": [],
  "schema_changes": [],
  "lineage": [],
  "access": [],
  "annotations": [],
  "operations": [],
  "cost": [],
  "state": [],
  "collection_errors": []
}
```

Aliases matching ContractForge table names are accepted, such as `ctrl_ingestion_runs`, `ctrl_ingestion_errors`, `ctrl_ingestion_quality`, `ctrl_ingestion_quarantine`, `ctrl_ingestion_state` and `ctrl_ingestion_cost`.

AWS-shaped aliases are also accepted, such as `aws_runs`, `aws_quality`, `aws_state` and `aws_cost`. A typical AWS scope is:

```json
{
  "scope": {
    "platform": "aws",
    "evidence_store": "iceberg",
    "database": "contractforge_ops"
  },
  "aws_runs": [],
  "aws_quality": [],
  "aws_state": []
}
```

Secret-like fields are redacted before analysis and before any provider call.

## CLI Usage

Markdown report:

```bash
contractforge-ai analyze-control-tables \
  --input control-table-evidence.json \
  --format markdown
```

JSON for automation:

```bash
contractforge-ai analyze-control-tables \
  --input control-table-evidence.json \
  --format json
```

Optional provider enrichment:

```bash
contractforge-ai analyze-control-tables \
  --input control-table-evidence.json \
  --with-ai \
  --provider openai \
  --language pt-BR \
  --format html
```

The model-enriched output is advisory. Deterministic metrics, risk and findings remain the review baseline.

`--language` translates the final review report through the configured provider after the English report has been rendered. It is designed for narrative prose only: labels, statuses, table headers, SQL, paths, identifiers and JSON-like evidence remain in English so operational handoff and automation stay consistent.

HTML output is the preferred review format. It uses the same rich visual
system as generated project reviews and includes:

- status and risk badges;
- high-level metrics cards;
- operational metric tables;
- run status counts;
- recurring failure clusters;
- error categories;
- deterministic findings and recommendations;
- follow-up queries;
- traceability evidence;
- provider guidance when enabled.

Use Markdown or JSON when another system will parse the result. Use HTML for
incident review, operational handoff, dashboard screenshots or approval.

## Deterministic Checks

The analyzer currently reports:

- high or non-zero failure rate;
- duration outliers and wide duration spread;
- failed quality checks;
- quarantine volume and unlinked quarantine rows;
- schema change events;
- inconsistent stream metrics;
- governance application failures;
- missing cost evidence;
- failed state continuation markers;
- partial evidence coverage;
- partial evidence collection.

It also returns aggregate metrics such as run counts, success rate, status distribution, median/max duration, rows written, quality failures, quarantined rows, quarantine records, schema changes, stream batches, lineage events, cost signals, state targets and error categories.

## Follow-up Queries

Reports include follow-up SQL query templates for reviewers. They are not executed automatically and should be adapted to the real catalog/schema/table layout.

## Boundary

The analyzer does not mutate contracts, Databricks jobs, access policies or data. It produces operational evidence for review, CI gates, notebooks and future provider-enriched diagnostics.
