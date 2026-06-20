# Fabric PostgreSQL JDBC Source Smoke

This project validates a non-SQLServer JDBC source path in the Fabric adapter.
It reads a small PostgreSQL-compatible fixture through generated Fabric
notebook JDBC code, resolves JDBC URL/user/password from Azure Key Vault and
writes ContractForge control-table evidence.

Validated source fixture:

- provider: PostgreSQL-compatible hosted database
- database: `neondb`
- source table: `contractforge_fabric_f11.orders`
- expected rows: `2`

Run:

```powershell
$env:PYTHONPATH='src;adapters/fabric/src'
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-postgres-jdbc/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

This is still `F11` partial evidence. It validates PostgreSQL JDBC through the
notebook path, but it does not validate every JDBC dialect.
