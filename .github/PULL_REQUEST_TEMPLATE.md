## Summary

Describe the change and why it is needed.

## Scope

- [ ] Core semantics
- [ ] Databricks adapter
- [ ] AWS adapter
- [ ] Snowflake adapter
- [ ] Fabric adapter
- [ ] GCP adapter
- [ ] ContractForge AI
- [ ] Documentation/site
- [ ] Packaging/release

## Validation

List the commands run and relevant results.

```text
uv run pytest ...
```

## Review Flow

- [ ] This PR targets `main`
- [ ] This PR is from a feature/fix/docs branch, not a direct commit to `main`
- [ ] Required CI checks are expected to pass
- [ ] CODEOWNER review is requested when required

## Contract Compatibility

- [ ] No public contract syntax changed
- [ ] Public contract syntax changed and docs/tests were updated
- [ ] Adapter-specific behavior is documented as warning/review/unsupported

## Security

- [ ] No credentials, tokens, private keys or tenant-specific secrets are included
- [ ] Secret placeholders remain unresolved in committed files
