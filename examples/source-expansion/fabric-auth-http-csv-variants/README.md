# Fabric Authenticated HTTP CSV Variants Source Expansion

This project is a focused `F11` source-expansion smoke for authenticated
bounded `http_csv` reads in the Fabric adapter.

The source endpoint returns a small CSV payload. The contracts validate that the
generated Fabric notebooks resolve Key Vault placeholders and execute the
`http_csv` reader path with:

- Basic auth
- bearer token
- API key

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-auth-http-csv-variants/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

The endpoint does not enforce the headers; this smoke proves Fabric runtime
resolution/materialization for authenticated `http_csv`, while enforced
authorization behavior remains connector-endpoint-specific.
