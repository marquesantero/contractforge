# Advanced Write Production Benchmark

This fixture tracks production-sized GCP BigQuery review evidence for advanced
write modes that remain outside the stable-final GCP claim:

- `historical`
- `snapshot_reconcile_soft_delete`

The contracts are intentionally normal ContractForge contracts. Live validation
uses the GCP smoke runtime with explicit `--allow-review-required` so the
adapter still records that these modes are review-required.

Example:

```powershell
$env:PYTHONPATH = "src;adapters\gcp\src"
uv run python -m contractforge_gcp.cli smoke `
  examples\benchmarks\advanced-write-production\contracts\gcp\customers_historical.ingestion.yaml `
  --environment examples\benchmarks\advanced-write-production\environments\gcp.environment.yaml `
  --execute --allow-review-required --runtime bq --skip-quality `
  --report .tmp\gcp-historical-prod.json
```
