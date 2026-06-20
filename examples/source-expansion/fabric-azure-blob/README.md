# Fabric Azure Blob Source Expansion

This project is a focused `F11` source-expansion smoke for Azure Blob object
storage reads in the Fabric adapter.

The source is a two-row public Azure Blob CSV fixture. The contract keeps the
portable `source.type: azure_blob` source descriptor and uses
`extensions.fabric.source_runtime_path` to declare the Fabric Spark-readable
runtime URI.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-azure-blob/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

The expected result is one successful bronze target table under
`cf_fabric_source_expansion.azure_blob_orders` plus a second contract-only probe
that validates target rows, positive amounts and run, quality, schema and source
metadata evidence.
