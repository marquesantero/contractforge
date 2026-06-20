# GCP HTTP File Binary Formats

This source-expansion project validates declared `http_file` binary formats for the GCP BigQuery adapter.

The contracts read Avro, ORC and Parquet fixtures through the shared HTTP file reader, then load the fetched bytes into BigQuery local load jobs. The fixture server is local to the smoke runner; BigQuery still executes the target load, quality and evidence writes in the configured GCP project.

Run:

```powershell
uv run python examples/source-expansion/gcp-http-file-binary/serve_fixtures.py --port 8765
```

Then, in another shell:

```powershell
$env:PYTHONPATH='.;src;adapters/gcp/src'
uv run python -m contractforge_gcp.cli run-project examples/source-expansion/gcp-http-file-binary/project.yaml --environment-key gcp --execute --runtime bq --report docs/reports/gcp-http-file-binary-bigquery-smoke.json
```

