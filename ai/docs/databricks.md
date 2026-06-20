# Databricks Usage

ContractForge AI can be used from Databricks notebooks as a diagnostic companion. The package should not replace ContractForge execution; it reviews contracts and explains evidence after runs.

## Notebook Contract Review

```python
from contractforge_ai import review_contract

result = review_contract("/Workspace/Shared/contracts/silver/orders.ingestion.yaml")
display(result.to_dict())
```

## Failure Explanation from Control Tables

`collect_databricks_run_evidence` collects run, error, quality and stream rows from ContractForge control tables and returns a redacted evidence payload compatible with `explain_failure`.

```python
from contractforge_ai.context import collect_databricks_run_evidence
from contractforge_ai import explain_failure

run_id = "264f171c-83e9-43f5-baea-c0391838145a"

evidence = collect_databricks_run_evidence(
    run_id=run_id,
    catalog="main",
    ctrl_schema="ops",
    spark=spark,
)
explanation = explain_failure(evidence)
display(explanation.to_dict())
```

The collector queries these tables when available:

- `ctrl_ingestion_runs`
- `ctrl_ingestion_errors`
- `ctrl_ingestion_quality`
- `ctrl_ingestion_streams`

Missing optional tables are recorded under `collection.collection_errors` instead of failing the whole collection. Secrets and credential-like fields are redacted before the evidence is returned.

The same path is available from the CLI when running inside a Databricks runtime with Spark available:

```bash
contractforge-ai explain-run \
  --run-id 264f171c-83e9-43f5-baea-c0391838145a \
  --catalog main \
  --ctrl-schema ops \
  --format json
```

## Provider Configuration in Databricks

Use Databricks secrets or environment variables to configure providers. Do not hardcode keys in notebooks.

```python
import os

os.environ["CONTRACTFORGE_AI_PROVIDER"] = "azure_openai"
os.environ["CONTRACTFORGE_AI_MODEL"] = "contract-review"
os.environ["AZURE_OPENAI_ENDPOINT"] = dbutils.secrets.get("contractforge-ai", "azure_openai_endpoint")
os.environ["AZURE_OPENAI_API_KEY"] = dbutils.secrets.get("contractforge-ai", "azure_openai_api_key")
os.environ["AZURE_OPENAI_API_VERSION"] = dbutils.secrets.get("contractforge-ai", "azure_openai_api_version")
```

Provider-enriched workflows should still use redacted context and review.

## Operational Pattern

1. Run ContractForge ingestion normally.
2. Collect control-table evidence by `run_id`.
3. Use `explain_failure` or `contractforge-ai explain-run --run-id` to classify the failure.
4. Attach explanation output to troubleshooting notebooks, tickets or dashboards.
5. Convert recurring unknown failures into deterministic patterns and tests.

