# Publication And Packaging

## Purpose

ContractForge Core, every platform adapter and the AI companion are published as separate Python distributions.

This is a packaging boundary, not only a source-code preference. Installing `contractforge-core` must never install Databricks, AWS, Fabric, Snowflake, GCP or other platform adapter packages unless the user explicitly installs one.

## Distribution Ownership

| Distribution | Owns package | Owns console scripts | Depends on |
| --- | --- | --- | --- |
| `contractforge-core` | `contractforge_core` | `contractforge` | Core runtime dependencies only. |
| `contractforge-databricks` | `contractforge_databricks` | `contractforge-databricks` | `contractforge-core` plus optional Databricks runtime dependencies. |
| `contractforge-aws` | `contractforge_aws` | `contractforge-aws` | `contractforge-core` plus optional AWS runtime dependencies. |
| `contractforge-fabric` | `contractforge_fabric` | `contractforge-fabric` | `contractforge-core` plus optional Fabric runtime dependencies. |
| `contractforge-snowflake` | `contractforge_snowflake` | `contractforge-snowflake` | `contractforge-core` plus optional Snowflake runtime dependencies. |
| `contractforge-gcp` | `contractforge_gcp` | `contractforge-gcp` | `contractforge-core` plus optional GCP runtime dependencies. |
| `contractforge-ai` | `contractforge_ai` | `contractforge-ai` | `contractforge-core` plus optional provider and adapter extras. |

The dependency direction is one way:

```text
platform adapter wheel -> contractforge-core wheel
contractforge-core wheel -> no platform adapter wheel
```

The core may define public protocols, semantic models, contract parsing, capability models, planning, evidence models and generic CLI commands. It must not depend on an adapter package to provide those surfaces.

## Core Wheel Rules

The `contractforge-core` wheel must include only:

- `contractforge_core`
- core documentation and metadata needed for publication
- the `contractforge` console script
- platform-neutral dependencies

The core wheel must not include:

- `contractforge_databricks`
- adapter packages such as `contractforge_aws`, `contractforge_fabric`, `contractforge_snowflake` or `contractforge_gcp`
- adapter console scripts such as `contractforge-databricks`
- platform SDKs or runtime clients
- Spark, Databricks SDK, boto3, Azure SDK, Fabric SDK or Snowflake connector dependencies

## Adapter Wheel Rules

Each adapter wheel must include only its adapter package and adapter-owned entry points.

For `contractforge-databricks`, the adapter distribution owns:

- `contractforge_databricks`
- the `contractforge-databricks` console script
- Databricks-specific rendering, SQL, runtime helpers, control-table DDL, Lakeflow, Unity Catalog, Delta and Asset Bundle logic
- an explicit dependency on a compatible `contractforge-core` version

The adapter package may expose optional extras for runtime integrations. For example, Databricks Connect or PySpark support should be optional unless the adapter intentionally publishes a runtime-heavy extra.

## Monorepo Layout

The repository is organized so each publishable distribution has its own project manifest:

```text
pyproject.toml
src/
  contractforge_core/
adapters/
  databricks/
    pyproject.toml
    src/
      contractforge_databricks/
  aws/
    pyproject.toml
    src/
      contractforge_aws/
  fabric/
    pyproject.toml
    src/
      contractforge_fabric/
  snowflake/
    pyproject.toml
    src/
      contractforge_snowflake/
  gcp/
    pyproject.toml
    src/
      contractforge_gcp/
ai/
  pyproject.toml
  src/
    contractforge_ai/
```

The root `pyproject.toml` is the `contractforge-core` project. `adapters/databricks/pyproject.toml` is the `contractforge-databricks` project. `adapters/aws/pyproject.toml` is the `contractforge-aws` project. `adapters/fabric/pyproject.toml` is the `contractforge-fabric` project. `adapters/snowflake/pyproject.toml` is the `contractforge-snowflake` project. `adapters/gcp/pyproject.toml` is the `contractforge-gcp` project. `ai/pyproject.toml` is the `contractforge-ai` project.

## Monorepo Development Rule

A development checkout may keep `contractforge_core` and one or more adapters in the same repository while the architecture is being built.

Publication must still produce separate wheels. Source colocation is not permission to publish a combined distribution.

Tests may import both packages from the local checkout, but packaging tests must prove that the core build target only packages `contractforge_core`.

## CLI Boundary

The core `contractforge` CLI owns platform-neutral commands:

- validate contracts
- compose split contracts
- inspect semantic plans
- render generic review output
- show public schema/spec information

Adapter CLIs own adapter-native commands:

- render platform artifacts
- inspect adapter capabilities
- render adapter dashboards or bundles
- run adapter-specific governance previews
- execute adapter-owned runtime helpers when explicitly supported

The core CLI may discover installed adapters in the future, but it must not import adapter packages at module import time.

## Versioning

Core and adapter wheels may version independently.

Recommended policy:

1. Core changes that alter public models or planner semantics increment the core minor version until `1.0`.
2. Adapter wheels declare a compatible core range.
3. Adapter-only artifact/runtime improvements do not require a core release.
4. A new core semantic concept is not complete until specs, tests, capability mapping and adapter behavior or explicit blockers are updated.

Example adapter dependency:

```toml
dependencies = [
  "contractforge-core>=0.2,<0.3",
]
```

## Build Verification

Before publishing `contractforge-core`, verify:

```text
python -m build --wheel
```

The produced wheel must contain `contractforge_core` and must not contain `contractforge_databricks`.

Before publishing an adapter, verify the adapter wheel contains the adapter package, depends on `contractforge-core`, and does not vendor or copy the core package.

For Databricks:

```text
cd adapters/databricks
python -m build --wheel
```

For AWS:

```text
cd adapters/aws
python -m build --wheel
```

For Fabric:

```text
cd adapters/fabric
python -m build --wheel
```

For Snowflake:

```text
cd adapters/snowflake
python -m build --wheel
```

For GCP:

```text
cd adapters/gcp
python -m build --wheel
```

For AI:

```text
cd ai
python -m build --wheel
```

The AI distribution currently uses `setuptools` while core and adapter
distributions use `hatchling`. This is intentional for the first public AI
release because `contractforge-ai` ships prompt templates as package data and
the existing setuptools configuration is already covered by the release build.
Do not migrate the backend during a release unless the wheel and sdist contents
are revalidated.

## GitHub Release Assets

PyPI is the canonical Python package index, but GitHub Releases must also carry
runtime-ready assets for environments that cannot reach PyPI or that require a
specific file suffix:

- `.whl` for normal Python installation and S3/workspace-hosted runtime
  dependencies;
- `.tar.gz` source distributions for rebuild and audit workflows;
- `.zip` aliases copied from the wheel archive for runtimes such as Snowflake
  Python procedures that accept staged ZIP imports but reject `.whl` imports.

The ZIP alias must contain the same bytes as the wheel. It is a runtime delivery
format, not a different package build.

## Acceptance Criteria

A release is publishable only when:

- `contractforge-core` builds its own wheel.
- each adapter builds its own wheel.
- the core wheel does not include adapter modules or adapter scripts.
- each adapter declares `contractforge-core` as a dependency.
- the AI companion declares `contractforge-core` as a dependency.
- adapter dependencies never leak into core dependencies.
- docs describe installation and usage for core-only and core-plus-adapter flows.
- release workflow assets include wheel, source distribution and ZIP alias
  outputs for runtime delivery.
