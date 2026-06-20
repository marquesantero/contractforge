# Fabric Stable-Surface Smoke Suite

This project exercises the Fabric adapter surface that must pass before the
adapter can be called stable for notebook-first Lakehouse execution.

The suite uses SQL sources only. That keeps the test focused on Fabric runtime
semantics instead of external connector availability.

## Scope

- `append`
- `overwrite`
- `upsert`
- `hash_diff_upsert`
- `historical`
- `snapshot_reconcile_soft_delete`
- quality abort failure evidence
- strict schema failure evidence
- operations, annotations and access review evidence
- control-table evidence probe

Run locally against the configured Fabric workspace:

```powershell
$env:PYTHONPATH='adapters/fabric/src;core/src'
uv run python -m contractforge_fabric.cli smoke-project examples/stable-surface/fabric/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

Expected result: project status `SUCCEEDED`. Fabric job-instance status is
expected to be completed for all submitted notebooks; the final evidence probe
must prove at least 2 failed control-table run/error records for the quality and
schema failure probes.
