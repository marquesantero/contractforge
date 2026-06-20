# Fabric Lakehouse Text File Source Smoke

This source-expansion project validates a bounded Lakehouse `text` file source
on the Fabric adapter. A fixture file must exist under the configured
Lakehouse `Files` area before the smoke runs.

Validated fixture path:

```text
Files/source-expansion/lakehouse-text/orders.txt
```

Run locally against the configured Fabric workspace:

```powershell
$env:PYTHONPATH='adapters/fabric/src;src'
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-lakehouse-text/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

