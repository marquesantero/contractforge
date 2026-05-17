# ContractForge Project Template

Minimal template for a declarative ingestion project with ContractForge and Databricks Asset Bundles.

## Structure

```text
contracts/
  bronze/
    b_orders.ingestion.yaml
  silver/
    c_orders.ingestion.yaml
    c_orders.annotations.yaml
    c_orders.operations.yaml
    c_orders.access.yaml
notebooks/
  run_contract.py
databricks.yml
```

## Flow

1. Adjust `catalog`, schemas, paths and permissions.
2. Install the versioned ContractForge wheel on the job or cluster.
3. Validate contracts in CI:

```bash
contractforge init --output contracts/bronze/b_orders.ingestion.yaml --source main.raw.orders --target-table b_orders
contractforge validate contracts/bronze/b_orders.ingestion.yaml
contractforge validate-bundle contracts/silver/c_orders
contractforge validate-project contracts
```

4. Run the generic notebook with the `contract` parameter.
