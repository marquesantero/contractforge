# ContractForge Snowflake Adapter

`contractforge-snowflake` is the Snowflake adapter for ContractForge.

The documented `snowflake_sql_warehouse` surface is stable-supported: real
Snowflake validation has covered table, SQL and staged-file sources, hosted
procedure execution, quality, schema policy, evidence/control tables,
governance comments/tags, lineage/explain and cost reconciliation. Task graph
live execution and the reference hash-diff production benchmark are also
validated. SCD2/snapshot soft delete are excluded from stable-final.
Continuous ingestion surfaces and account-feature-dependent access policy
validation remain explicit review or final-certification boundaries.

The implementation is planning/publish/runtime-first:

- consumes ContractForge Core contracts through public core models;
- declares conservative Snowflake capabilities;
- builds publish bundles for a stable Snowflake library runner;
- runs supported contracts through the adapter runtime with Snowflake sessions;
- writes ContractForge evidence/control tables in Snowflake;
- renders project task graph deployment artifacts for schedule/timezone and
  step dependencies;
- keeps Snowflake connector and Snowpark dependencies optional.

```bash
pip install contractforge-core contractforge-snowflake
```

```python
from contractforge_snowflake import plan_snowflake_contract

result = plan_snowflake_contract(contract)
print(result.status)
```

```python
from contractforge_snowflake import build_snowflake_publish_bundle

bundle = build_snowflake_publish_bundle(contract)
print(bundle.artifacts["snowflake.publish_manifest.json"])
```

```python
from contractforge_snowflake import run_snowflake_contract

result = run_snowflake_contract(
    contract_uri="@CONTRACTFORGE_ARTIFACTS/dev/runtime/ANALYTICS.BRONZE_CUSTOMERS.contract.json",
    environment_uri="@CONTRACTFORGE_ARTIFACTS/dev/runtime/ANALYTICS.BRONZE_CUSTOMERS.environment.json",
    session=snowflake_session,
)
print(result["status"])
```

The adapter does not generate per-contract ingestion SQL as the default
execution model. Published contracts are consumed by the `contractforge_snowflake`
runtime library. Project deployment artifacts may create Snowflake tasks, but
those tasks only call the stable runner with contract and environment artifact
URIs.

Governance annotations support table and column comments, plus Snowflake tags
when tag objects are already provisioned. Use fully qualified tag names such as
`GOVERNANCE.PUBLIC.DOMAIN` for deterministic live apply. To validate tag intent
and record `ctrl_ingestion_annotations` evidence without executing tag DDL, set:

```yaml
extensions:
  snowflake:
    annotation_tag_mode: validate_only
```

Access governance supports table grants, row access policy attachments and
masking policy attachments, with each step recorded in
`ctrl_ingestion_access`. Use `access.mode: validate_only` to verify grant and
policy intent without applying DDL. `revoke_unmanaged: true` remains
review-required because it can remove inherited or unmanaged Snowflake access.

Use `contractforge-snowflake smoke-stage-publish --execute --execute-cleanup`
to live-test stage publication. The smoke creates a temporary internal stage,
uploads the publish bundle, reloads the staged manifest and runtime artifacts,
and runs the contract through the connector-backed library runner.
Live smoke commands accept either `--connect-options <yaml>` or
`--connection <name>` when the Snowflake Python connector can resolve that
connection name, for example `--connection cfingestsvc-pat`.

Staged-file sources support CSV, JSON and Parquet batch reads from Snowflake
stages. Provide a named Snowflake file format through
`source.options.file_format`, or use a stage with a default file format. CSV
sources can project positional fields with `source.options.columns` as either a
list of names or a mapping of output names to Snowflake expressions. JSON and
Parquet sources default to a `payload` `VARIANT` projection and can project
typed columns with expressions such as `$1:order_id::NUMBER`.

```yaml
source:
  type: staged_files
  path: '@RAW_STAGE/orders/orders.csv'
  format: csv
  options:
    file_format: RAW_CSV_FORMAT
    columns:
      order_id: '$1::NUMBER'
      status: '$2::STRING'
      amount: '$3::NUMBER(10,2)'
```

Use `contractforge-snowflake smoke-procedure --execute --execute-cleanup` to
deploy and call the stable Snowpark runtime procedure. The service role needs
`CREATE PROCEDURE` on the target schema. The smoke accepts the built core and
adapter wheels locally, stages Snowflake-compatible ZIP copies, and imports
those ZIP archives from the procedure:

```sql
GRANT CREATE PROCEDURE ON SCHEMA CONTRACTFORGE_TEST_DB.PUBLIC
  TO ROLE CONTRACTFORGE_INGEST_ROLE;
```

Use `contractforge-snowflake smoke-task-graph --execute --execute-cleanup` to
deploy and manually execute a two-step task graph. In addition to the procedure
grant, the service role needs task creation/execution privileges in the task
schema; the live validation account now has these grants:

```sql
GRANT CREATE TASK ON SCHEMA CONTRACTFORGE_TEST_DB.PUBLIC
  TO ROLE CONTRACTFORGE_INGEST_ROLE;
GRANT EXECUTE TASK ON ACCOUNT TO ROLE CONTRACTFORGE_INGEST_ROLE;
```

Project CLI parity includes `deploy-project`, `run-project`, and
`cleanup-plan`. `run-project --dry-run` renders the root task `EXECUTE TASK`
commands without connecting; `run-project --wait` polls bounded
`INFORMATION_SCHEMA.TASK_HISTORY` for terminal task states. `cleanup-plan`
prints explicit drop commands for tasks and the runtime procedure but does not
drop data target tables or staged artifacts.

Each runtime run records immediate lineage and explain evidence. The lineage
row in `ctrl_ingestion_lineage` includes a ContractForge/OpenLineage-style
event with the run id, source reference, target table, row count and Snowflake
query ids. The explain row in `ctrl_ingestion_explain` captures
`EXPLAIN USING TEXT` output for the rendered write statement. Disable plan
capture for a contract with:

```yaml
extensions:
  snowflake:
    explain_enabled: false
```

Native Snowflake lineage from `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` is
handled as delayed reconciliation because Account Usage can lag runtime
execution. The helper probes by structured `QUERY_TAG` `run_id` and returns
`PENDING` without inserting rows until matching Access History rows are visible.

```bash
contractforge-snowflake reconcile-lineage \
  --connect-options .tmp/snowflake-smoke/connect-options.yaml \
  --environment .tmp/snowflake-smoke/environment.json \
  --run-id "<contractforge-run-id>"
```

Use `contractforge-snowflake reconcile-cost` after a run to append delayed
`ctrl_ingestion_cost` signals from Snowflake Account Usage. The command probes
`QUERY_HISTORY` by structured `QUERY_TAG` `run_id`; if rows have not arrived
yet or the service role cannot read Account Usage, it returns `PENDING` without
inserting duplicate evidence and includes a warning when access is unavailable.
When rows are available, it deletes prior adapter-owned cost signals for the
same `run_id`/target table before inserting query-history and, when accessible,
query-attribution signals.

To let the same service role query Account Usage, grant the Snowflake database
role that covers `QUERY_HISTORY` and `QUERY_ATTRIBUTION_HISTORY`:

```sql
GRANT DATABASE ROLE SNOWFLAKE.GOVERNANCE_VIEWER
  TO ROLE CONTRACTFORGE_INGEST_ROLE;
```

```bash
contractforge-snowflake reconcile-cost \
  --connect-options .tmp/snowflake-smoke/connect-options.yaml \
  --environment .tmp/snowflake-smoke/environment.json \
  --run-id "<contractforge-run-id>" \
  --target-table '"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_SMOKE_APPEND_TARGET"' \
  --wait --max-wait-seconds 300
```

Architecture and implementation plan:

- `docs/specs/snowflake-capability-parity.md`
- `docs/specs/snowflake-ga-criteria.md`
- `docs/specs/snowflake-ga-waivers.md`
- `docs/specs/snowflake-adapter-implementation-plan.md`
- `docs/specs/snowflake-adapter-parity-execution-plan.md`
