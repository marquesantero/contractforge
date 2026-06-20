# Fabric HTTP JSON Source Expansion

This project is a focused `F11` source-expansion smoke for the Fabric adapter.
It validates a public/no-auth bounded `http_json` source through the generated
Fabric notebook runtime.

The contract uses the USGS GeoJSON payload as an HTTP file, not as the
`rest_api` connector. That gives Fabric source-family evidence beyond the
already validated public REST path while keeping the same contract-only
execution rule.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-http-json/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

The expected result is one successful bronze target table under
`cf_fabric_source_expansion.http_json_usgs_geojson` plus a second contract-only
probe that validates target rows and run, quality, schema and source metadata
evidence.
