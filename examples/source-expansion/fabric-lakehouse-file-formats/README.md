# Fabric Lakehouse File Formats Source Smoke

This source-expansion project validates bounded Lakehouse `orc`, `avro` and
`xml` file sources on the Fabric adapter. Fixture directories must exist under
the configured Lakehouse `Files` area before the smoke runs.

Validated fixture paths:

```text
Files/source-expansion/lakehouse-file-formats/orc_orders
Files/source-expansion/lakehouse-file-formats/avro_orders
Files/source-expansion/lakehouse-file-formats/xml_orders
```

Run locally against the configured Fabric workspace:

```powershell
$env:PYTHONPATH='adapters/fabric/src;src'
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-lakehouse-file-formats/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

