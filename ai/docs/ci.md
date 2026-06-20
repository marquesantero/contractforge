# CI Usage

ContractForge AI should provide value in CI without requiring model credentials. The baseline CI workflow should run deterministic checks only.

## Contract Review

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --fail-on high
```

For repositories that split ContractForge contracts into `.ingestion.yaml`, `.annotations.yaml` and `.operations.yaml`, run bundle-aware review on ingestion files:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --bundle --fail-on high
```

Recommended policy:

- Use `--fail-on critical` during early adoption.
- Move to `--fail-on high` after teams have cleaned up existing contracts.
- Do not fail CI on low/medium advisory findings until the organization agrees on those standards.

## JSON Output

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --format json
```

Use JSON output to aggregate findings, publish artifacts or annotate pull requests.

## Pull Request Comment Output

Use Markdown output when posting review results to pull requests:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml --format markdown > contractforge-review.md
```

The Markdown report includes status, risk, summary, a compact findings table and detailed finding sections with recommendations.

## Finding Code Policies

Fail by specific finding code:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml \
  --fail-on-code write.keys.nullable \
  --fail-on-code source.json.schema.missing
```

`--fail-on-code` can be repeated. It is useful when a team wants to block specific known risks while allowing other advisory findings to remain visible but non-blocking.

Severity and code policies can be combined:

```bash
contractforge-ai review contracts/silver/orders.ingestion.yaml \
  --fail-on high \
  --fail-on-code autoloader.checkpoint.missing \
  --format markdown
```

## GitHub Actions Example

```yaml
name: ContractForge AI Review

on:
  pull_request:
    paths:
      - "contracts/**/*.yaml"

jobs:
  review-contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: python -m pip install contractforge-ai
      - name: Review contracts
        run: |
          for file in contracts/**/*.ingestion.yaml; do
            contractforge-ai review "$file" --bundle --fail-on high
          done
```

## Model Calls in CI

Avoid real model calls in standard CI:

- They add cost and latency.
- They can be flaky due to provider/network behavior.
- They require secret management in pull request workflows.
- They make regression behavior harder to reproduce.

If model-enriched checks are required, run them in a separate scheduled or manually triggered workflow with controlled credentials and stored artifacts.

`--with-ai` should be treated as advisory in CI. Deterministic severity and finding-code policies should remain the gate.

