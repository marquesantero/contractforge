# Fabric Authenticated REST Variants Source Expansion

This project is a focused `F11` source-expansion smoke for authenticated REST
variants beyond Basic auth in the Fabric adapter.

The sources call a bounded REST echo endpoint and validate that generated Fabric
notebooks resolve Key Vault placeholders and send the expected authentication
headers:

- bearer token through `auth.type: bearer_token`
- API key through `auth.type: api_key`

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-auth-rest-variants/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

The expected result is two successful bronze target tables under
`cf_fabric_source_expansion` plus a third contract-only probe that validates
target rows, auth-header evidence and run, quality, schema and source metadata
evidence.
