# Contributing To ContractForge

ContractForge is a contract-first ingestion platform with a strict package
boundary between the semantic core and runtime adapters. Contributions should
preserve that boundary.

## Before Opening A Change

1. Read [README.md](README.md), [docs/architecture.md](docs/architecture.md)
   and [docs/specs/adapter-authoring.md](docs/specs/adapter-authoring.md).
2. Check existing issues for related work.
3. For behavior changes, open an issue first unless the fix is small and
   clearly scoped.

## Pull Request Flow

`main` is the protected integration branch. Do not work directly on `main`.
Create a focused branch, push it and open a pull request into `main`.

```bash
git switch main
git pull --ff-only
git switch -c feature/short-description
```

Each pull request should:

- describe the intent and scope using the pull request template;
- keep unrelated refactors, generated reports and local cloud artifacts out of
  the diff;
- include focused tests for the changed behavior;
- update docs when public contract syntax, CLI behavior, adapter support,
  maturity status, packaging or release behavior changes;
- pass the required `CI / Test` check before merge;
- receive at least one maintainer or CODEOWNER approval before merge.

The repository uses `CODEOWNERS` to route approvals to the maintainer. Admins
may bypass branch protection only for emergency recovery or release
maintenance, and should leave a clear audit note when doing so.

Maintainers may use squash merge for small changes and regular merge for
release, architecture or multi-commit work where preserving commit boundaries
helps future audits.

## Development Setup

```bash
uv sync --extra dev
uv pip install -e adapters/databricks -e adapters/aws -e adapters/snowflake -e adapters/fabric -e adapters/gcp -e ai
```

Run focused tests while developing:

```bash
uv run pytest tests/test_publication_packaging.py tests/test_package_version.py
uv run pytest tests/test_adapter_cli_standardization.py
```

Run the full suite before a broad change:

```bash
uv run pytest
```

Build packages when touching packaging or public exports:

```bash
uv build --wheel --sdist
(cd adapters/databricks && uv build --wheel --sdist)
(cd adapters/aws && uv build --wheel --sdist)
(cd adapters/snowflake && uv build --wheel --sdist)
(cd adapters/fabric && uv build --wheel --sdist)
(cd adapters/gcp && uv build --wheel --sdist)
(cd ai && uv build --wheel --sdist)
```

## Architecture Rules

- `contractforge-core` owns portable contract semantics, validation,
  normalization, capability matching, abstract planning and neutral evidence
  models.
- Adapter packages own platform-specific rendering, deployment and runtime
  execution.
- The core package must not import Spark, Databricks SDK, boto3, Azure SDK,
  Fabric SDK, Snowflake clients or Google Cloud clients.
- Adapter behavior should use the same public contract vocabulary whenever
  possible. Do not introduce adapter-only contract fields without documenting
  the portability impact.
- If a platform cannot preserve a semantic contract safely, return a clear
  `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or `UNSUPPORTED` result instead
  of silently changing behavior.

## Pull Request Checklist

- The branch targets `main` through a pull request.
- Tests cover the changed behavior.
- Docs are updated when public contract syntax, CLI behavior, adapter support
  or maturity status changes.
- The required GitHub Actions checks pass.
- A maintainer or CODEOWNER approval is present before merge.
- New runtime features include evidence or explain output where applicable.
- New dependencies are declared in the owning package only.
- Generated artifacts, credentials, local agent folders and cloud API key files
  are not committed.
- Package boundaries still pass `tests/test_publication_packaging.py` and
  `tests/test_adapter_independence.py`.

## Commit Style

Use concise imperative commit messages, for example:

```text
Add GCP schema policy smoke evidence
Fix Fabric notebook retry rendering
Document adapter parameter aliases
```

## Security

Do not open public issues for vulnerabilities or exposed credentials. Follow
[SECURITY.md](SECURITY.md).
