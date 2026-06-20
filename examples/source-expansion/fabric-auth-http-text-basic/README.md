# Fabric Authenticated HTTP Text Source Expansion

This project is a focused `F11` source-expansion smoke for endpoint-enforced
Basic authentication on bounded `http_text` reads in the Fabric adapter.

The source endpoint returns `401 Unauthorized` without valid Basic auth and a
small authenticated response when the Fabric notebook resolves the Key Vault
placeholder correctly.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-auth-http-text-basic/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```
