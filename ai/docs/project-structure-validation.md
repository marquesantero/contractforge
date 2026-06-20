# Project Structure Validation

ContractForge AI validates real ContractForge project folders before generated
output is treated as ready. This is a deterministic gate: it does not call a
model provider and it does not execute adapters. By default it validates the
core project shape only. When adapter packages are installed, it can also call
their public planning APIs as an optional portability gate.

Use it after AI-assisted generation, before CI deployment, and before asking a
model to critique or enrich a project.

```bash
contractforge-ai validate-project-structure ./examples/real-world/supabase-jdbc-medallion
```

JSON output is suitable for CI:

```bash
contractforge-ai validate-project-structure ./my-project --format json
```

Markdown output is suitable for pull requests:

```bash
contractforge-ai validate-project-structure ./my-project --format markdown
```

HTML output is the preferred review surface when validating a complete
project folder:

```bash
contractforge-ai validate-project-structure ./my-project --format html > project_validation.html
```

The HTML report uses the same ContractForge AI review visual system as
generated `AI_REVIEW.html` files. Long findings and adapter-planning evidence
are rendered as cards, not wide tables, so paths, planner status, details and
recommendations remain readable.

Adapter-aware validation is explicit:

```bash
contractforge-ai validate-project-structure ./my-project \
  --adapter databricks \
  --adapter aws \
  --format html > project_validation.html
```

## What It Checks

The validator discovers and checks:

- `project.yaml` or `project.yml`;
- referenced `*.environment.yaml` files;
- referenced reusable connection YAMLs;
- all `*.ingestion.yaml`, `*.ingestion.yml` and `*.ingestion.json` files;
- sibling `annotations`, `operations`, `access` and `environment` section files
  through the ContractForge Core bundle loader.

The validator uses ContractForge Core APIs for the semantics that belong to the
core:

- environment contract validation;
- `source.type: connection` resolution, including `project://connections/...`;
- split-bundle composition;
- semantic contract normalization;
- public five-field schedule cron parsing.

ContractForge AI adds friendly project-level findings around those core checks.

When `--adapter` is provided, the validator also:

- loads each ingestion bundle through ContractForge Core;
- passes the resolved contract to the adapter's public planner;
- uses the matching `project.environments.<adapter>` file when available;
- treats `SUPPORTED` as `READY`;
- treats adapter warnings as `READY_WITH_WARNINGS` when there are no critical
  or high findings;
- treats blockers, unsupported semantics and validation failures as non-ready
  states;
- treats `UNSUPPORTED` or adapter planning failures as `INVALID`.

This gate does not run a platform job, create infrastructure, or render
deployment artifacts. It only proves that generated contracts can be understood
by the selected adapter planner before a deploy command is allowed.

Optional model enrichment may explain the adapter findings through
`adapter.validation.enrichment.v1`, but it cannot change this deterministic
status. If the adapter gate returns `NEEDS_DECISIONS`, `INVALID` or `UNSAFE`,
generated artifacts must remain review-bound even when a provider produces
friendly guidance.

## Canonical Project Shape

```yaml
name: orders_project

environments:
  databricks: environments/databricks.environment.yaml
  aws: environments/aws.environment.yaml

connections:
  postgres: connections/postgres.yaml

schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false

execution_order:
  - name: bronze_orders
    depends_on: []
    contracts:
      databricks: contracts/bronze/orders.ingestion.yaml
      aws: contracts/bronze/orders.ingestion.yaml
```

This is the preferred minimum-drift shape: both adapters receive the same
canonical contract when the ingestion intent is portable. Use separate
adapter-specific contract paths only when the semantic planner proves that a
platform-specific extension is required and the portability impact is documented.

## Reusable Connection YAML

Connection YAMLs centralize source endpoint, auth and shared read defaults.
They must not contain dataset semantics such as target, write mode, quality
rules or access grants.

```yaml
# connections/postgres.yaml
source:
  type: connector
  connector: postgres
  system: supabase
  options:
    url: "{{ secret:scope/jdbc-url }}"
    driver: org.postgresql.Driver
auth:
  type: basic
  username: "{{ secret:scope/user }}"
  password: "{{ secret:scope/password }}"
read:
  fetchsize: 10000
```

An ingestion contract inherits the connection and overrides only dataset-specific
fields:

```yaml
source:
  type: connection
  connection_path: project://connections/postgres.yaml
  table: public.orders
  read:
    partition_column: order_id
    lower_bound: 1
    upper_bound: 100000
    num_partitions: 8

target:
  catalog: main
  schema: bronze
  table: b_orders

mode: append
```

The ingestion source override wins over the global connection source. For
example, `source.read.num_partitions` in the ingestion contract overrides the
same key in `connections/postgres.yaml`.

## Findings

Important finding families:

| Finding | Meaning |
| --- | --- |
| `project_structure.project_yaml.missing` | The folder is not a complete project root. |
| `project_structure.project_yaml.semantic_field` | `project.yaml` contains dataset semantics that belong in contracts. |
| `project_structure.environment.invalid` | A referenced environment contract failed core validation. |
| `project_structure.connection.inline_secret` | A connection YAML contains a raw secret-like value. |
| `project_structure.ingestion.legacy_field` | An ingestion contract uses old flat fields such as `target_table`. |
| `project_structure.ingestion_bundle.invalid` | The core bundle loader rejected the ingestion plus sibling sections. |
| `adapter.<name>.planning.warning.*` | The selected adapter planned the contract with reviewable warnings. |
| `adapter.<name>.planning.blocker.*` | The selected adapter found an unsupported capability or blocker. |
| `adapter.<name>.package_unavailable` | The adapter gate was requested but the adapter package is not installed. |

Statuses:

- `READY`: structure is usable.
- `READY_WITH_WARNINGS`: structure is usable and `ready=true`, but adapter
  warnings should be reviewed. This is the expected status for known-good
  projects whose adapter planner exposes portability or production-scale
  warnings.
- `NEEDS_DECISIONS`: review items remain that require a decision before the
  project should be treated as deployable.
- `INVALID`: required project, environment, connection or contract structure is wrong.
- `UNSAFE`: inline secret-like values were found.

## Real Project Validation Reports

The real-world USGS REST/GeoJSON and Supabase JDBC medallion projects validate
as complete project folders:

```bash
contractforge-ai validate-project-structure examples/real-world/usgs-earthquake-rest-medallion \
  --adapter databricks \
  --adapter aws \
  --format html > usgs-project-validation.html

contractforge-ai validate-project-structure examples/real-world/supabase-jdbc-medallion \
  --adapter databricks \
  --adapter aws \
  --format html > supabase-project-validation.html
```

Both reports are expected to show `READY_WITH_WARNINGS` when AWS planner
warnings are present but no critical/high findings exist. That means the
contracts are structurally valid and adapter-plannable, while reviewable AWS
warnings such as Spark SQL quality expression portability remain visible.

## AI Boundary

Model output cannot override this validator. Prompt-driven generation,
provider-backed enrichment and second-pass critique must treat
`validate-project-structure` as authoritative.

This keeps ContractForge AI useful without allowing the model to invent a
different public API than ContractForge Core and the adapters actually support.
