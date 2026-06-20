# Fabric Public HTTP CSV Source Smoke

This source-expansion project validates a public, bounded `http_csv` source on
the Fabric adapter. It uses only ContractForge contracts: one bronze contract
loads a small CSV payload, and one SQL contract probes the target and evidence
tables.

Run locally against the configured Fabric workspace:

```powershell
$env:PYTHONPATH='adapters/fabric/src;core/src'
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-http-csv/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

