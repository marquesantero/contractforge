# Snowflake Adapter

The Snowflake adapter is the third ContractForge adapter. It targets the
Snowflake SQL warehouse as the runtime surface, mapping contract intent into
Snowflake-native SQL, evidence tables, governance operations and deployment
artifacts.

The adapter is not a generic Snowflake abstraction. It is a set of explicit
Snowflake subtargets, each with declared capabilities and review boundaries.

Current status: stable supported surface for table sources, SQL sources,
bounded REST API sources, staged files, write modes, quality, schema policy,
governance, state/idempotency, evidence, cost reconciliation, lineage, project
deployment artifacts and the hosted Snowpark procedure library runner on
`snowflake_sql_warehouse`.
The reference hash-diff benchmark and task graph live execution are validated.
historical/snapshot soft delete, continuous ingestion surfaces such as Snowpipe,
Streams, Snowpipe Streaming and Kafka connector ingestion, and
account-feature-dependent row access or masking policy enforcement are excluded
from stable-final where the connected Snowflake account does not provide those
native policy features.

The release gate for this supported surface is tracked in
[Snowflake stable-surface criteria](../specs/snowflake-ga-criteria.md), the
[Snowflake waiver registry](../specs/snowflake-ga-waivers.md) and the
[Snowflake stabilization matrix](../specs/snowflake-stabilization-matrix.md).

The default execution model is the library-runner pattern. Contracts and
environments are published as runtime JSON artifacts to a Snowflake internal
stage. The runner loads those artifacts through the Snowflake connector, renders
the reviewed Snowflake SQL body with the same adapter renderer, and executes it
in the active Snowflake session.

## Initial Target

| Area | Decision |
| --- | --- |
| Subtarget | `snowflake_sql_warehouse` |
| Runtime | Snowflake SQL warehouse |
| Table format | Snowflake native tables |
| Storage | Snowflake managed storage |
| Catalog | Snowflake database/schema |
| Governance | Snowflake tags, comments, row access policies, masking policies |
| Evidence | ContractForge control tables in Snowflake |
| Deployment | Tasks calling the stable runner procedure |

## Runtime Entrypoints

The adapter provides a single stable runtime execution path through the
library runner.

```bash
contractforge-snowflake run \
  --contract-uri @CONTRACTFORGE_ARTIFACTS/dev/runtime/ANALYTICS.BRONZE_ORDERS.contract.json \
  --environment-uri @CONTRACTFORGE_ARTIFACTS/dev/runtime/ANALYTICS.BRONZE_ORDERS.environment.json \
  --connect-options connection.yaml
```

```bash
contractforge-snowflake run \
  --contract-uri contracts/bronze/orders/orders.contract.yaml \
  --dry-run
```

The runner:

1. loads the contract and environment artifacts from the stage or local filesystem;
2. renders source SQL, preparation, quality, schema policy, write SQL and evidence
   DDL for the Snowflake dialect;
3. executes the rendered operations in order through a Snowflake connector session;
4. records run, error, quality, quarantine, schema change, state, annotation,
   access, operations, lineage and explain evidence.

## Sources

The Snowflake source registry supports table, view, SQL expression, bounded
REST API and staged file sources. File format detection is conservative: the
adapter requires a named Snowflake file format object; inline file format
definitions are not permitted because they make syntax validation harder.

| Source | Planner | Runtime |
| --- | --- | --- |
| `table` and `view` | `SUPPORTED` | `SELECT * FROM <qualified>` |
| `sql` / `query` | `SUPPORTED` | Executes the provided SQL after stripping trailing semicolons |
| `rest_api` | `SUPPORTED` | Uses the shared core REST client and materializes bounded records into a temporary Snowflake source table |
| `staged_files` with CSV, JSON, Parquet | `SUPPORTED` for named file formats | `SELECT ... FROM @stage` with positional or typed projections |
| `staged_files` with unsupported formats | `REVIEW_REQUIRED` | Blocked |
| `autoloader` | `UNSUPPORTED` | Blocked |
| `kafka` | `UNSUPPORTED` | Blocked |

Snowflake hosted procedure execution for `rest_api` requires an external access
integration that permits the target HTTPS host. For the USGS example this is
`CF_USGS_REST_ACCESS` allowing `earthquake.usgs.gov:443`.

Minimal account setup for the unauthenticated USGS REST example:

```sql
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE NETWORK RULE CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_RULE
  TYPE = HOST_PORT
  MODE = EGRESS
  VALUE_LIST = ('earthquake.usgs.gov:443');

CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION CF_USGS_REST_ACCESS
  ALLOWED_NETWORK_RULES = (CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_RULE)
  ALLOWED_AUTHENTICATION_SECRETS = none
  ENABLED = TRUE;

GRANT USAGE ON INTEGRATION CF_USGS_REST_ACCESS
TO ROLE CONTRACTFORGE_INGEST_ROLE;
```

If the service role creates the integration instead of `ACCOUNTADMIN`, it also
needs `USAGE` on `CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_RULE` and `CREATE
EXTERNAL ACCESS INTEGRATION` on the account. Use `ALLOWED_AUTHENTICATION_SECRETS
= none` for unauthenticated REST; `(none)` is parsed as a secret identifier in
some Snowflake accounts.

Staged file sources accept `columns` as a list (CSV positional) or a mapping
(JSON/Parquet `$1:field::TYPE` projections). Unsafe stage paths containing `..`
or characters outside the stage identifier set are rejected.

## Write Modes

| Mode | Planner | Runtime |
| --- | --- | --- |
| `append` | `SUPPORTED` | `INSERT INTO <target> SELECT * FROM (<source>)` |
| `overwrite` | `SUPPORTED` | `CREATE OR REPLACE TABLE <target> AS SELECT * FROM (<source>)` |
| `upsert` | `SUPPORTED` | `MERGE INTO <target> USING (<source>) ON <merge_keys> WHEN MATCHED THEN UPDATE WHEN NOT MATCHED THEN INSERT` |
| `hash_diff_upsert` | `SUPPORTED_WITH_WARNINGS` | Compute `HASH` over non-merge, non-excluded columns, then `MERGE` only on changed rows |

Merge-key preflight validation runs for `upsert` and `hash_diff_upsert`:
null merge keys and duplicate merge keys in the source view reject the run
before any write is attempted.

## Schema Policy

Schema policy is enforced through `INFORMATION_SCHEMA.COLUMNS` when connected,
falling back to connector metadata. The standard policies are supported:

- `additive_only`: new columns are added with `ADD COLUMN IF NOT EXISTS`.
- `strict`: any column difference between source and target rejects the run.
- `permissive`: ignores column mismatches.

Incompatible type changes (e.g. `VARCHAR` to `NUMBER`) reject the run
regardless of policy.

Schema change evidence is recorded in `ctrl_ingestion_schema_changes`.

## Quality

| Rule | Planner | Runtime |
| --- | --- | --- |
| `not_null` | `SUPPORTED` | `SELECT COUNT(*) WHERE <column> IS NULL` |
| `required_columns` | `SUPPORTED` | Column existence check |
| `accepted_values` | `SUPPORTED` | `SELECT COUNT(*) WHERE <column> NOT IN (...)` |
| `min_rows` | `SUPPORTED` | Row count check |
| `unique_key` | `SUPPORTED` | `SELECT COUNT(*) ... GROUP BY <key> HAVING COUNT(*) > 1` |
| `max_null_ratio` | `SUPPORTED` | Null ratio calculation |
| Row-level expression | `SUPPORTED_WITH_WARNINGS` | Expression evaluated in a Snowflake SQL `WHERE` clause |

Aggregate quarantine without a row predicate is rejected. Quarantined rows are
written to a quarantine table with the run id. Quality evidence is recorded in
`ctrl_ingestion_quality` and `ctrl_ingestion_quarantine`.

## Preparation

SQL-compatible preparation transforms are supported:

- Column selection and projection.
- `cast`: renders `CAST(<column> AS <type>)` with `SELECT * REPLACE`.
- `derive`: renders the Snowflake-compatible expression.
- `standardize`: `TRIM`, `LOWER`, `NULLIF(..., '')`.
- Filters: rendered as a `WHERE` clause.
- Deterministic deduplicate: `QUALIFY ROW_NUMBER() OVER (PARTITION BY <keys> ORDER BY <order>) = 1`.

Complex nested shapes (`parse_json`, array explosions) remain `REVIEW_REQUIRED`
until live-tested.

## Governance

### Annotations

- Table and column comments are applied directly.
- Snowflake tags are rendered when tag objects exist. Fully qualified tag names
  such as `GOVERNANCE.PUBLIC.DOMAIN` produce deterministic live apply.
- `annotation_tag_mode: validate_only` validates tag intent and records evidence
  without executing DDL.
- Annotation evidence is recorded in `ctrl_ingestion_annotations`.

Annotation error policy controls whether invalid tags or comments stop the run:

```yaml
extensions:
  snowflake:
    annotation_failure: warn
    annotation_tag_mode: validate_only
```

### Access

- `validate_only` grant planning records intended grants in `ctrl_ingestion_access`
  without executing DDL.
- Row access policy SQL and masking policy SQL are rendered from contract
  declarations.
- Destructive revokes are gated as `REVIEW_REQUIRED`.

## State, Idempotency And Watermarks

- Last success state is persisted for every run with source metadata and
  watermark values.
- Watermark candidates are calculated from `MAX(order_column)` on the
  source view.
- Previous watermark filtering skips rows already processed in earlier runs
  using state evidence.
- Idempotency lookup checks `ctrl_ingestion_runs` for successful replays and
  skips already-completed runs.
- Opt-in lock acquire and release guards against concurrent execution.

## Eviction And Recall

The adapter records the standard ContractForge evidence surface into Snowflake
control tables under the configured evidence schema:

| Control Table | Content |
| --- | --- |
| `ctrl_ingestion_runs` | Run identity, status, metrics, source/target metadata |
| `ctrl_ingestion_errors` | Error message, redacted stack trace, run reference |
| `ctrl_ingestion_quality` | Per-rule quality evaluation results and status |
| `ctrl_ingestion_quarantine` | Quarantined rows with run id and rule reference |
| `ctrl_ingestion_schema_changes` | Added/removed/changed columns with types |
| `ctrl_ingestion_annotations` | Comments, tags, applied/validate-only status |
| `ctrl_ingestion_access` | Grants, policies, validate-only or applied status |
| `ctrl_ingestion_state` | Last success watermark, idempotency key, run reference |
| `ctrl_ingestion_operations` | Operations intent and applied status |
| `ctrl_ingestion_lineage` | Source-to-target lineage events with OpenLineage metadata |
| `ctrl_ingestion_explain` | `EXPLAIN USING TEXT` output for write operations |
| `ctrl_ingestion_cost` | Query history and attribution signals from Account Usage |

All control table identifiers are quoted to protect reserved words. Database and
schema bootstrap is additive: `CREATE DATABASE IF NOT EXISTS` and `CREATE SCHEMA
IF NOT EXISTS` are skipped when the database or schema already exists, so
service-role deployments avoid unnecessary failures.

## Cost Reconciliation

Cost reconciliation uses the canonical `cost-report` command documented in
[Adapter CLI](../cli.md). Snowflake-specific options include the run id, target
table, connection options and bounded polling for Account Usage latency.

The reconciliation:

1. probes `QUERY_HISTORY` by structured `QUERY_TAG` containing the run id;
2. records query history signals and optional query attribution signals;
3. returns `PENDING` when Account Usage latency delays row availability;
4. deletes prior adapter-owned cost signals before inserting new ones.

The `--wait` flag polls until rows appear or a timeout is reached.

## Lineage

Two lineage paths are available:

1. **Immediate lineage** (`ctrl_ingestion_lineage`): written during runtime
   execution with source, target, run id and OpenLineage-compatible metadata.
2. **Delayed reconciliation** (`ctrl_ingestion_lineage` from `ACCESS_HISTORY`):
   reconcilable later through the CLI when Account Usage latency allows.

```bash
contractforge-snowflake reconcile-lineage \
  --run-id "ANALYTICS.BRONZE_CUSTOMERS:abc123" \
  --wait --max-wait-seconds 3600
```

`EXPLAIN USING TEXT` output for write statements is written to
`ctrl_ingestion_explain`.

## Project Deployments

The adapter can deploy and run task graphs from project files using the
canonical `deploy-project` and `run-project` commands documented in
[Adapter CLI](../cli.md). `cleanup-plan` remains a Snowflake-specific
non-destructive helper.

Deployment artifacts include:

- Stable runner procedure `CREATE OR REPLACE PROCEDURE`.
- Task graph `CREATE TASK` for scheduled or dependency-driven execution.
- Task history polling for `run-project --wait`.

Procedure live smoke has passed with the hosted Snowpark library runner. Task
graph live smoke has also passed with root/dependent task execution and cleanup.

## Smoke Tests

The canonical `smoke` command validates the adapter against a real Snowflake
account. Additional Snowflake-specific smoke variants cover failure paths,
stage publish, hosted procedure execution and task graphs.

Each smoke command defaults to non-destructive `CF_SMOKE_*` prefixed objects.
The `--execute-cleanup` flag is required before any DROP statements are run.

## Live Validation

Recent live Snowflake validation covered:

| Scenario | Status | Notes |
| --- | --- | --- |
| `smoke-procedure` | `PASS` | Hosted Snowpark procedure imported ZIP-packaged core/adapter libraries and wrote 2 rows; procedure query id `00000000-0000-0000-0000-000000000000`. |
| `smoke-task-graph` | `PASS` | Live task graph deployed two tasks, executed the root task, waited for bronze/silver `SUCCEEDED` states, verified 2-row bronze/silver counts and cleaned up smoke artifacts. |
| USGS GeoJSON REST medallion | `LOCAL PASS` | The example project now declares Snowflake bronze-to-gold contracts beside the Databricks and AWS contracts, with Snowflake bronze using the same `source.type: rest_api` URL/method/raw response contract. Local runtime tests execute the declared Snowflake contracts in project order. Live hosted-procedure execution requires `CF_USGS_REST_ACCESS` in the Snowflake account. |

## Install And Dependencies

```bash
pip install contractforge-core contractforge-snowflake
```

Runtime connection:

```bash
pip install contractforge-snowflake[runtime]
```

Snowpark procedure support (optional):

```bash
pip install contractforge-snowflake[snowpark]
```

The adapter does not import the Snowflake connector or Snowpark SDK on default
import. Runtime dependencies are activated lazily through the `[runtime]` and
`[snowpark]` extras.

## Comparison With Other Adapters

| Area | Databricks | AWS | Snowflake |
| --- | --- | --- | --- |
| Runtime | Direct workspace Spark | Glue Spark | Snowpark stored procedure and SQL |
| Table format | Delta | Apache Iceberg | Snowflake native |
| Deployment | Asset Bundles | Glue jobs deployed via boto3 | Staged package imported by the stable runner procedure |
| Governance | Unity Catalog | Lake Formation | Tags, comments, row access policies, masking policies |
| Evidence | Delta tables by default | Iceberg tables | Snowflake control tables |
| Source parity | Autoloader, files, JDBC, REST, native passthrough | S3 files, JDBC, REST, HTTP file, incremental files | Tables/views, SQL, bounded REST, staged files, review-required for continuous surfaces |

For side-by-side ingestion parity guidance across Databricks, AWS and
Snowflake, see [Test contracts across adapters](test-contracts-across-adapters.md).

## Roadmap And Parity

The adapter's parity status is tracked in:

- [Snowflake capacity parity spec](../specs/snowflake-capability-parity.md)
- [Snowflake adapter parity execution plan](../specs/snowflake-adapter-parity-execution-plan.md)
- [Snowflake stabilization matrix](../specs/snowflake-stabilization-matrix.md)
- [Snowflake stable-surface criteria](../specs/snowflake-ga-criteria.md)
- [Snowflake stable-surface waiver registry](../specs/snowflake-ga-waivers.md)

Continuous ingestion surfaces (`copy_into`, Snowpipe, Streams, Snowpipe
Streaming and Kafka connector ingestion), Data Metric Functions, and
account-feature-dependent access policy validation remain outside the
stable-final claim until a separate runtime/evidence mapping or available
account feature set is implemented and live validation is complete.
