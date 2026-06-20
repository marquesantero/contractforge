# Fabric OAuth REST Source Expansion

This project is a focused `F11` source-expansion smoke for
`auth.type: oauth_client_credentials` in the Fabric REST adapter path.

The source obtains a Microsoft Entra OAuth token through client credentials,
using a Key Vault placeholder for `auth.client_secret`, then calls a bounded
REST echo endpoint. The generated notebook must send an `Authorization: Bearer`
header and write standard ContractForge evidence.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-auth-rest-oauth/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

The expected result is one successful bronze target table under
`cf_fabric_source_expansion.auth_rest_oauth` plus a second contract-only probe
that validates target rows, bearer-header evidence and run, quality, schema and
source metadata evidence.
