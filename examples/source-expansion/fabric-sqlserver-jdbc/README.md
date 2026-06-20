# Fabric SQL Server JDBC Source Expansion

This project is a focused `F11` source-expansion smoke for SQL Server JDBC
reads in the Fabric adapter.

The source is an Azure SQL Database seeded with two rows. The JDBC password is
not present in the contract or rendered notebook: it is referenced as
`{{ secret:fabric/sqlserver-admin-password }}` and resolved at runtime through
Azure Key Vault by the generated Fabric notebook.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-sqlserver-jdbc/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

The expected result is one successful bronze target table under
`cf_fabric_source_expansion.sqlserver_jdbc_orders` plus a second contract-only
probe that validates target rows, positive amounts and run, quality, schema and
source metadata evidence.
