# Fabric Authenticated HTTP Text API-Key Source Expansion

This project is a focused `F11` source-expansion smoke for endpoint-enforced
API-key authentication on bounded `http_text` reads in the Fabric adapter.

The source endpoint is a tiny Azure Function fixture. It returns `401` when the
`x-api-key` header is missing, `403` when it is wrong and a small text payload
when the Fabric notebook resolves the Key Vault placeholder correctly.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-auth-http-text-api-key/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```
