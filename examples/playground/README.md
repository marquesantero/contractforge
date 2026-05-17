# ContractForge Playground

Example project for exploring ContractForge without depending on real external sources.

The goal is to show complete contracts, validate structure and provide copyable patterns for real projects.

## Scenarios

```text
contracts/
  bronze/
    b_orders_api.*              # incremental REST API
    b_nasa_eonet_events.*       # REST API raw payload + shape.parse_json in silver
    b_orders_files.*            # Auto Loader JSON available_now
  silver/
    s_orders.*                  # incremental JDBC + SCD1
    s_nasa_eonet_event_observations.* # complex JSON structured by shape
    s_devices.*                 # snapshot_soft_delete
    s_customers_history.*       # SCD2
  gold/
    g_daily_orders.*            # Gold full refresh KPI
notebooks/
  run_contract.py               # generic Databricks notebook
scripts/
  validate_playground.py        # validates all contracts through the CLI
```

## Local Validation

Install the library in development mode:

```bash
pip install -e ".[dev]"
```

Validate the playground:

```bash
python examples/playground/scripts/validate_playground.py
```

Or directly:

```bash
contractforge validate-project examples/playground/contracts
contractforge governance-preview examples/playground/contracts/silver/s_orders
contractforge templates list
```

## Use in a Real Project

1. Copy the closest scenario into your repository.
2. Adjust `target.catalog`, `target.schema` and `target.table`.
3. Replace URLs, paths, names and secrets.
4. Review `quality_rules`, `operations` and `access`.
5. Run `contractforge validate-bundle`.
6. Execute with the generic notebook or with `ingest_bundle()`.

## Note

Contracts are structure and governance examples. Do not run them as real ingestion without adjusting sources, credentials, schemas, permissions and paths.

The `b_nasa_eonet_events` / `s_nasa_eonet_event_observations` pair demonstrates the recommended pattern for REST APIs with complex JSON: the connector downloads the raw payload with `response.mode: raw`, while `shape.parse_json`, `shape.arrays` and `shape.columns` perform declarative structuring with an explicit schema.
