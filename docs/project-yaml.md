# Project YAML Reference

`project.yaml` describes how a group of ContractForge contracts is delivered as
one ingestion project. It is not an ingestion contract and it must not contain
dataset semantics such as source columns, write mode, quality rules or access
policies.

Use it for repository-level concerns:

- which environments exist;
- where reusable connection YAMLs live;
- how contract steps depend on each other;
- how a project is scheduled;
- which platform artifacts should be deployed;
- which validation commands and evidence checks prove the delivery.

The goal is minimum platform drift: portable project fields stay at the top
level; adapter differences live under explicit adapter blocks.

## Canonical Shape

```yaml
name: usgs_geojson_medallion
description: Real USGS GeoJSON medallion ingestion across stable adapters.

source_system:
  name: usgs_earthquake_feed
  type: rest_api

environments:
  databricks: environments/databricks.environment.yaml
  aws: environments/aws.environment.yaml
  snowflake: environments/snowflake.environment.yaml
  fabric: environments/fabric.environment.yaml
  gcp: environments/gcp.environment.yaml

connections:
  usgs_geojson: connections/usgs.yaml

defaults:
  catalog: workspace
  schemas:
    bronze: cf_bronze
    silver: cf_silver
    gold: cf_gold
    tmp: cf_tmp
  schema_policy: additive_only
  operations:
    technical_owner: data-platform
    criticality: medium
    expected_frequency: daily
  annotations:
    table:
      tags:
        domain: seismology
  adapters:
    databricks:
      catalog: workspace
      schemas:
        bronze: cf_bronze
        silver: cf_silver
        gold: cf_gold
    snowflake:
      catalog: CONTRACTFORGE_TEST_DB
      schemas:
        bronze: PUBLIC
        silver: PUBLIC
        gold: PUBLIC

deployment:
  databricks:
    bundle_name: contractforge_usgs_geojson_medallion
    job_key: usgs_geojson_medallion
    job_name: contractforge_usgs_geojson_medallion
    workspace_root_path: /Workspace/Shared/contractforge-examples/USGS_GeoJSON_Medallion
  aws:
    state_machine_name: contractforge_usgs_geojson_medallion

schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false
  max_concurrent_runs: 1
  queue: true
  adapters:
    databricks:
      pause_status: PAUSED
      tasks:
        bronze_usgs_geojson:
          task_key: bronze_usgs_geojson
    aws:
      state: DISABLED

execution_order:
  - name: bronze_usgs_geojson
    layer: bronze
    depends_on: []
    contracts:
      databricks: contracts/databricks/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml
      aws: contracts/aws/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml
      snowflake: contracts/snowflake/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml
      fabric: contracts/fabric/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml
      gcp: contracts/gcp/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml

  - name: silver_usgs_events
    layer: silver
    depends_on: [bronze_usgs_geojson]
    contracts:
      databricks: contracts/databricks/silver/silver_usgs_events/silver_usgs_events.ingestion.yaml
      aws: contracts/aws/silver/silver_usgs_events/silver_usgs_events.ingestion.yaml
      snowflake: contracts/snowflake/silver/silver_usgs_events/silver_usgs_events.ingestion.yaml
      fabric: contracts/fabric/silver/silver_usgs_events/silver_usgs_events.ingestion.yaml
      gcp: contracts/gcp/silver/silver_usgs_events/silver_usgs_events.ingestion.yaml

validation:
  databricks:
    bundle: databricks.yml
    job_name: contractforge_usgs_geojson_medallion
  aws:
    artifact_bucket_parameter: CONTRACTFORGE_AWS_ARTIFACT_BUCKET
    glue_role_parameter: CONTRACTFORGE_AWS_GLUE_ROLE_ARN
```

## Field Reference

| Field | Required | Owner | Purpose |
| --- | --- | --- | --- |
| `name` | yes | core | Stable project id. Used for default job, bundle, state machine and schedule names. |
| `description` | no | core | Readable project description. |
| `source_system` | no | core | Project-level source context for documentation and test data. Dataset-level source semantics still belong in ingestion contracts. |
| `environments` | yes for deploy | core | Maps environment keys to `*.environment.yaml` files. |
| `connections` | no | core | Named reusable connection YAMLs for humans and project organization. Ingestion contracts still use `source.connection_path`. |
| `defaults` | no | core | Deterministic project defaults applied to split bundles before semantic validation. Existing contract values always win. |
| `deployment` | no | adapters | Adapter deployment metadata. Keep only platform deployment settings here. |
| `schedule` | no | core plus adapters | Core-owned schedule intent plus adapter-specific scheduler overrides. |
| `execution_order` | yes for projects | core | Ordered contract steps and dependencies. |
| `validation` | no | adapters/tooling | Test, deploy and audit hints used by adapter CLIs and examples. |
| `portability` | no | documentation/tooling | Explains intentional contract differences between platforms. |

## Environments

`environments` maps a logical key to an environment contract:

```yaml
environments:
  databricks: environments/databricks.environment.yaml
  aws: environments/aws.environment.yaml
```

The environment file chooses adapter, evidence location and runtime/deployment
parameters. It must not contain ingestion semantics.

Example AWS environment:

```yaml
name: smoke
adapter: aws
artifacts:
  uri: s3://contractforge-artifacts/usgs-geojson/
  include_contract_bundle: true
  include_normalized_contract: true
parameters:
  aws:
    iceberg:
      warehouse: s3://contractforge-warehouse/
    glue_job:
      role_arn: arn:aws:iam::123456789012:role/ContractForgeGlueRole
    step_functions:
      role_arn: arn:aws:iam::123456789012:role/ContractForgeStepFunctionsRole
    scheduler:
      role_arn: arn:aws:iam::123456789012:role/ContractForgeSchedulerRole
```

## Reusable Connections

`connections` is a project inventory of shared connector files:

```yaml
connections:
  supabase_postgres: connections/supabase.yaml
```

The actual inheritance happens in the ingestion contract through
`source.type: connection`:

```yaml
source:
  type: connection
  connection_path: project://connections/supabase.yaml
  table: public.products
  read:
    partition_column: product_id
    lower_bound: 1
    upper_bound: 100000
    num_partitions: 8
```

Connection file:

```yaml
type: connector
connector: postgres
system: supabase_inventory_demo
options:
  url: "{{ secret:supabase/jdbc_url }}"
  driver: org.postgresql.Driver
auth:
  type: username_password
  username: "{{ secret:supabase/user }}"
  password: "{{ secret:supabase/password }}"
read:
  fetchsize: 10000
```

The core bundle loader resolves the connection file before adapter planning and
deep-merges it with dataset-specific source fields. The connection YAML provides
defaults; the ingestion `source` block overrides them. This includes nested
fields such as `read.fetchsize`, `read.num_partitions` or `options.driver`.

For the complete merge behavior, examples and path safety rules, see
[Connection YAML](connection-yaml.md).

Security rules:

- use `project://connections/...` for centralized project connections;
- use same-bundle relative paths only when the connection file lives under the
  ingestion bundle directory;
- do not use absolute paths or `..` traversal;
- keep secrets as secret references;
- do not put table-specific semantics in the connection file;
- use connection files for endpoint, auth, driver and common read defaults.

## Contract Defaults

Use `defaults` to remove repeated project-level values from individual
contracts while keeping execution deterministic:

```yaml
defaults:
  catalog: workspace
  schemas:
    bronze: cf_bronze
    silver: cf_silver
    gold: cf_gold
    tmp: cf_tmp
  schema_policy: additive_only
  operations:
    technical_owner: data-platform
    criticality: medium
    expected_frequency: daily
  annotations:
    table:
      tags:
        domain: commerce
  adapters:
    aws:
      catalog: contractforge
      schemas:
        bronze: cf_orders_bronze
        silver: cf_orders_silver
        gold: cf_orders_gold
```

Then an ingestion contract can stay focused on dataset intent:

```yaml
source:
  type: table
  ref: bronze.orders

target:
  table: orders_current

layer: silver
mode: upsert
merge_keys: [order_id]
```

When the split bundle is loaded, the core resolves a complete contract:

```yaml
target:
  table: orders_current
  catalog: workspace
  schema: cf_silver
schema_policy: additive_only
quality_rules:
  unique_key: [order_id]
  not_null: [order_id]
operations:
  ownership:
    technical_owner: data-platform
  criticality: medium
  expected_frequency: daily
annotations:
  table:
    tags:
      domain: commerce
```

Only safe values are inferred. `source`, `target.table`, secrets, access rules
and identity keys are never guessed. Existing contract fields always override
project defaults.

Inspect the effective contract before deploying:

```bash
contractforge resolve-bundle contracts/silver/orders/orders.ingestion.yaml
```

The output includes `defaults.decisions[]`, a ledger with the field path, value,
source and reason for every value added by the resolver.

For cross-platform projects, put shared defaults directly under `defaults` and
platform bindings under `defaults.adapters.<adapter>`. When a contract path is
under `contracts/<adapter>/...`, the bundle loader applies the matching adapter
defaults after the shared defaults. This is useful for catalog and schema
bindings that differ between Databricks, AWS, Snowflake, Fabric and GCP while
the contract intent remains the same.

### Defaults Reference

The default resolver accepts these keys under `defaults` and under
`defaults.adapters.<adapter>`. Adapter-specific values are merged after shared
defaults. Explicit contract fields always win.

| Default key | Applies to | Supports layer map? | Effect |
| --- | --- | --- | --- |
| `catalog` | `target.catalog` | no | Fills target catalog when omitted. |
| `catalog_type` | `target.catalog_type` | no | Fills logical catalog type when omitted. |
| `layer` | schema selection only | no | Used only to select `schemas.<layer>` when the contract omits `layer`; it does not write `layer` into the contract. |
| `schema` | `target.schema` | no | Fallback schema when `schemas` does not provide the contract layer. |
| `schemas.<layer>` | `target.schema` | yes | Fills target schema for the contract `layer`, for example `schemas.bronze`, `schemas.silver` or `schemas.gold`. |
| `schemas.default` | `target.schema` | no | Fallback schema when the contract layer is not listed. |
| `schemas.tmp` | custom transform output inference | no | Temporary schema used to infer `transform.custom.output` for `source.type: custom_transform`. |
| `schemas.staging` | custom transform output inference | no | Secondary fallback for custom transform output inference when `schemas.tmp` is not set. |
| `tmp_schema` | custom transform output inference | no | Explicit temporary schema for inferred custom transform output. Takes precedence over `schemas.tmp`. |
| `mode` | `mode` | yes | Fills write mode when omitted. Use with care; most production contracts should keep mode explicit unless a preset owns it. |
| `schema_policy` | `schema_policy` | yes | Fills schema policy when omitted. Common pattern: `bronze: permissive`, `silver/gold: additive_only`. |
| `on_quality_fail` | `on_quality_fail` | yes | Fills quality failure action when omitted. |
| `operations` | `operations` section | nested merge | Fills omitted operations metadata. Flat owner fields such as `technical_owner` are normalized under `operations.ownership`. |
| `annotations` | `annotations` section | nested merge | Fills omitted annotation metadata, commonly shared table tags. |
| `adapters.<adapter>` | any key above | same as key | Adapter-specific override block selected from contract path `contracts/<adapter>/...`. |

The resolver also performs two deterministic inferences:

| Inference | Condition | Result |
| --- | --- | --- |
| Identity quality | `merge_keys` is declared and mode is `upsert`, `hash_diff_upsert`, `historical` or `snapshot_reconcile_soft_delete` | Fills missing `quality_rules.unique_key` and appends missing `quality_rules.not_null` entries from `merge_keys`. |
| Custom transform output | `source.type: custom_transform`, no `transform.custom.output`, and catalog plus temp schema are known | Fills `transform.custom.output` as `<catalog>.<tmp_schema>.<target_table>__custom_output`. |

Defaults do not infer `source`, `target.table`, `merge_keys`, secrets,
authentication, access grants, row filters or masks.

## Deployment

`deployment` contains adapter deployment settings only.

```yaml
deployment:
  databricks:
    bundle_name: contractforge_usgs_geojson_medallion
    job_key: usgs_geojson_medallion
    job_name: contractforge_usgs_geojson_medallion
    workspace_root_path: /Workspace/Shared/contractforge-examples/USGS_GeoJSON_Medallion
  aws:
    state_machine_name: contractforge_usgs_geojson_medallion
  gcp:
    workflows:
      location: us-central1
```

Deployment blocks may name native jobs, bundles, state machines, workspace
paths or artifact roots. They must not redefine write modes, source semantics,
quality rules or governance policy.

## Schedule

Use top-level `schedule` for portable project scheduling:

```yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  enabled: false
  max_concurrent_runs: 1
  queue: true
  adapters:
    databricks:
      pause_status: PAUSED
    aws:
      state: DISABLED
```

Core-owned fields:

| Field | Meaning |
| --- | --- |
| `cron` | Standard five-field cron: minute, hour, day-of-month, month, day-of-week. |
| `timezone` | IANA timezone name, for example `America/Sao_Paulo`. |
| `enabled` | Portable intent. `false` means deploy the schedule paused/disabled. |
| `max_concurrent_runs` | Portable concurrency intent. Adapter support varies. |
| `queue` | Portable queueing intent. Adapter support varies. |

Adapter translations:

| Adapter | Translation |
| --- | --- |
| Databricks | `cron: "0 6 * * *"` -> Jobs Quartz cron `0 0 6 * * ?`; timezone -> `timezone_id`; `enabled: false` or `pause_status: PAUSED` -> paused schedule. |
| AWS | `cron: "0 6 * * *"` -> EventBridge Scheduler `cron(0 6 * * ? *)`; timezone -> `ScheduleExpressionTimezone`; `enabled: false` or `state: DISABLED` -> disabled schedule. |

Use `schedule.adapters.<adapter>` only for platform-specific overrides:

```yaml
schedule:
  cron: "0 6 * * *"
  timezone: America/Sao_Paulo
  adapters:
    aws:
      flexible_time_window: OFF
    databricks:
      pause_status: PAUSED
```

Do not put separate cron definitions under each adapter unless the schedule is
intentionally different and documented as non-portable.

## Execution Order

`execution_order` is the portable project DAG:

```yaml
execution_order:
  - name: bronze_orders
    layer: bronze
    depends_on: []
    contracts:
      databricks: contracts/databricks/bronze/bronze_orders/bronze_orders.ingestion.yaml
      aws: contracts/aws/bronze/bronze_orders/bronze_orders.ingestion.yaml

  - name: silver_orders
    layer: silver
    depends_on: [bronze_orders]
    contracts:
      databricks: contracts/databricks/silver/silver_orders/silver_orders.ingestion.yaml
      aws: contracts/aws/silver/silver_orders/silver_orders.ingestion.yaml
```

Fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `name` | yes | Stable project step id. |
| `layer` | no | Human/tooling hint such as `bronze`, `silver`, `gold`. |
| `description` | no | Readable step purpose. |
| `depends_on` | no | List of step names that must complete before this step. |
| `contracts` | yes | Adapter key to ingestion contract path. |
| `expected_result` | no | Test-only hint, for example `failed` in failure-path projects. |

Adapter mappings:

- Databricks renders steps as tasks in one Databricks Asset Bundle job.
- AWS renders steps as Glue jobs and can orchestrate them with Step Functions.
- Future adapters should consume the same DAG before adding platform-specific
  deployment details.

## Logical Table References

Project contracts should avoid platform-qualified table names when reading
tables produced by earlier ContractForge steps.

Prefer:

```yaml
source:
  type: table
  ref: bronze.b_products_jdbc
```

or in SQL:

```sql
FROM {{ table_ref:silver.s_product_tags }}
```

The core preserves the logical `layer.table` reference. Each adapter renders
the native table name for its platform.

## Validation And Portability Metadata

`validation` stores test and presentation hints. `portability` documents
intentional differences when platform contracts cannot be byte-for-byte
identical. Neither section authorizes semantic downgrades.

```yaml
validation:
  databricks:
    bundle: databricks.yml
    job_name: contractforge_usgs_geojson_medallion
  aws:
    artifact_bucket_parameter: CONTRACTFORGE_AWS_ARTIFACT_BUCKET
  snowflake:
    connection: cfingestsvc-pat
  fabric:
    workspace: contractforge
  gcp:
    project: contractforge

portability:
  invariant_contract_intent:
    - source.type
    - target.layer
    - mode
    - schema_policy
    - quality_rules
  platform_bindings:
    databricks:
      table_format: delta
    aws:
      table_format: iceberg
    snowflake:
      table_format: native
    fabric:
      table_format: delta
    gcp:
      table_format: bigquery
```

## Commands

Core validation:

```powershell
uv run contractforge validate-project examples/real-world/supabase-jdbc-medallion
```

Databricks:

```powershell
uv run contractforge-databricks render-project-bundle examples/real-world/supabase-jdbc-medallion/project.yaml `
  --output databricks.yml `
  --force

uv run contractforge-databricks deploy-project examples/real-world/supabase-jdbc-medallion/project.yaml `
  --render-bundle `
  --force-render `
  --target dev
```

AWS:

```powershell
uv run contractforge-aws deploy-project examples/real-world/supabase-jdbc-medallion/project.yaml `
  --dry-run `
  --render-orchestration `
  --summary-only

uv run contractforge-aws deploy-project examples/real-world/supabase-jdbc-medallion/project.yaml `
  --deploy-orchestration `
  --summary-only
```

## Anti-Patterns

- Do not put `source`, `target`, `mode`, quality rules or access policy in
  `project.yaml`.
- Do not put one cron under `schedule.adapters.aws` and another under
  `schedule.adapters.databricks` unless the difference is intentional and
  documented.
- Do not place secrets in `project.yaml`; use environment contracts and secret
  references.
- Do not make the core aware of Databricks Jobs, AWS Step Functions, Fabric
  pipeline JSON or Snowflake tasks. The core owns project intent; adapters own
  native artifacts.
- Do not edit generated Glue or Databricks job code manually to make tests pass.
  Fix the contract, environment or adapter.
