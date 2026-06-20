# GCP Azure SQL Server JDBC Medallion

This fixture promotes Azure SQL Database rows into BigQuery with the Google-provided Dataflow JDBC-to-BigQuery template, then runs normal GCP BigQuery contracts from bronze to gold.

The JDBC source uses GCP Secret Manager references for the connection URL, username and password. The contract does not contain secret values.

Execution shape:

1. `source-promotion` runs the bronze JDBC contract through Dataflow.
2. `run-project --start-at silver_azure_sql_orders_current` executes the BigQuery silver and gold contracts.
3. Evidence is written to `contractforge_gcp_azure_sql_ops`.
