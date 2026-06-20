# Fabric Authenticated REST Source Expansion

This project is a focused `F11` source-expansion smoke for authenticated
bounded REST reads in the Fabric adapter.

The contract calls a Basic-auth endpoint that returns only an authentication
success flag. The password is not present in the contract or rendered notebook:
it is referenced as `{{ secret:fabric/postman-basic-password }}` and resolved
at runtime through Azure Key Vault by the generated Fabric notebook.

```powershell
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-auth-rest/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

The expected result is one successful bronze target table under
`cf_fabric_source_expansion.auth_rest_basic` plus a second contract-only probe
that validates target rows, authenticated output and run, quality, schema and
source metadata evidence.
