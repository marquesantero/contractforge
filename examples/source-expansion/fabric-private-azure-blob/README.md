# Fabric Private Azure Blob Source Expansion

This project is a focused `F11` source-expansion smoke for private Azure Blob
CSV reads in the Fabric adapter.

The portable contract keeps `source.type: azure_blob`; the Fabric binding adds:

- `extensions.fabric.source_runtime_path`: Spark-readable `wasbs://` path.
- `extensions.fabric.storage_account_key_secret`: Key Vault placeholder used by
  the generated notebook to configure the Blob account key before `spark.read`.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-private-azure-blob/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```
