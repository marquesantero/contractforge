# Fabric OneLake Shortcut Source Smoke

This source-expansion project validates a Fabric OneLake shortcut read through
the notebook-first adapter path. The shortcut is created in the configured
Lakehouse `Files` area and points at an existing Lakehouse ORC fixture.

Validated shortcut-backed read path:

```text
Files/source-expansion/onelake-shortcuts/source_expansion_shortcut/lakehouse-file-formats/orc_orders
```

The shortcut target used for validation is:

```text
Files/source-expansion
```

Run locally against the configured Fabric workspace:

```powershell
$env:PYTHONPATH='adapters/fabric/src;src'
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-onelake-shortcut/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```
