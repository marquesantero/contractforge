# USGS Earthquake REST Medallion

This example is a real ingestion project fixture for ContractForge adapters.
It reads the public USGS Earthquake GeoJSON feed through the portable `rest_api`
connector, keeps the raw response in bronze, normalizes GeoJSON features in
silver, and produces two gold marts.

The same ingestion intent is used for Databricks, AWS, Snowflake, Fabric and GCP. Platform
differences are limited to runtime binding:

| Concern | Databricks | AWS | Snowflake | Fabric | GCP |
|---|---|---|---|---|---|
| Target catalog binding | Unity Catalog catalog such as `workspace` | Glue Catalog database derived from target catalog + schema | Snowflake database/schema | Fabric Lakehouse schema/table | BigQuery project/dataset/table |
| Storage/table engine | Delta through the Databricks adapter | Iceberg through the AWS Glue adapter | Snowflake native tables | Delta Lakehouse tables | BigQuery native tables |
| Runtime dependencies | Workspace wheels installed on the job | Glue `--extra-py-files` core wheel plus Python dependencies | Staged adapter ZIP imported by the Snowpark runner procedure | Fabric Notebook runtime with installed ContractForge packages | Local ContractForge runtime plus BigQuery load/query jobs |
| Evidence persistence | Delta control tables | Iceberg control tables | Snowflake control tables | Fabric Lakehouse control tables | BigQuery control tables |

Pipeline:

1. `bronze_usgs_geojson` pulls `2.5_day.geojson` with `source.type: rest_api`
   and stores one raw GeoJSON payload row.
2. `silver_usgs_events` reads bronze as a table source, parses the raw JSON,
   explodes `payload.features`, extracts coordinates, standardizes fields and
   writes the current feed snapshot with `overwrite`.
3. `gold_usgs_daily_summary` aggregates daily activity.
4. `gold_usgs_magnitude_bands` aggregates by magnitude band and event type.

Project layout:

```text
project.yaml
contracts/
  databricks/
    bronze/bronze_usgs_geojson/
    silver/silver_usgs_events/
    gold/gold_usgs_daily_summary/
    gold/gold_usgs_magnitude_bands/
  aws/
    bronze/bronze_usgs_geojson/
    silver/silver_usgs_events/
    gold/gold_usgs_daily_summary/
    gold/gold_usgs_magnitude_bands/
  snowflake/
    bronze/bronze_usgs_geojson/
    silver/silver_usgs_events/
    gold/gold_usgs_daily_summary/
    gold/gold_usgs_magnitude_bands/
  fabric/
    bronze/bronze_usgs_geojson/
    silver/silver_usgs_events/
    gold/gold_usgs_daily_summary/
    gold/gold_usgs_magnitude_bands/
  gcp/
    bronze/bronze_usgs_geojson/
    silver/silver_usgs_events/
    gold/gold_usgs_daily_summary/
    gold/gold_usgs_magnitude_bands/
environments/
  databricks.environment.yaml
  aws.environment.yaml
  snowflake.environment.yaml
  fabric.environment.yaml
  gcp.environment.yaml
```

Each dataset folder is a split ContractForge bundle:

- `*.ingestion.yaml` declares source, target table, write mode, shape and quality.
- `*.annotations.yaml` declares table/column metadata.
- `*.operations.yaml` declares operational ownership and runbook metadata.

`project.yaml.defaults` keeps repeated platform bindings out of every
ingestion contract. The compact contract declares only the target table:

```yaml
target:
  table: b_usgs_earthquake_geojson
```

The core resolves catalog, schema and default schema policy from the project
before adapter planning. Inspect the effective contract and default decision
ledger with:

```bash
contractforge resolve-bundle \
  examples/real-world/usgs-earthquake-rest-medallion/contracts/databricks/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml
```

The reusable contract builder in `tools/rest_medallion/usgs.py` mirrors these
YAML files and is used by automated tests, but the real project source of truth
is the YAML tree under `contracts/`.

`project.yaml` declares the medallion execution order and the platform-specific
contract path for each step. Runners should use that order instead of sorting
files by name.

Snowflake REST execution inside the hosted procedure requires the account-level
external access integration declared by `environments/snowflake.environment.yaml`
(`CF_USGS_REST_ACCESS`) to allow outbound HTTPS to `earthquake.usgs.gov`.
USGS is intentionally unauthenticated, so it does not declare
`parameters.snowflake.secrets`.

Fabric execution uses generated notebooks in the configured Lakehouse. The
Fabric binding removes Unity Catalog-style `workspace.` prefixes from
cross-layer table references and otherwise preserves the same bronze source,
silver shaping, gold aggregations, quality rules, annotations and operations.

GCP execution uses the core REST connector to materialize the public GeoJSON
payload into BigQuery bronze, then runs BigQuery SQL for silver and gold. The
bronze `source` block is identical to the other adapters; BigQuery-specific
differences are limited to target datasets and native JSON SQL syntax.

Account setup for the unauthenticated Snowflake REST source:

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

Use `ALLOWED_AUTHENTICATION_SECRETS = none`, without parentheses. The form
`(none)` can be parsed as a secret named `PUBLIC.NONE`.

For authenticated REST sources, keep the contract credential-free and declare
Snowflake secret bindings in the environment:

```yaml
source:
  type: rest_api
  request:
    headers:
      Authorization: "Bearer {{ secret:snowflake/api_token }}"
```

```yaml
parameters:
  snowflake:
    external_access_integrations:
      - CF_TMDB_REST_ACCESS
    secrets:
      api_token: CONTRACTFORGE_TEST_DB.PUBLIC.CF_TMDB_API_TOKEN
```

The hosted procedure binds that alias through Snowflake `SECRETS = (...)` and
resolves the value at runtime inside Snowflake.

Recent live validation:

| Platform | Status | Notes |
| --- | --- | --- |
| Databricks | `PASS` | USGS REST bronze-to-gold ran through a Databricks Asset Bundle job on serverless with PyPI-installed ContractForge packages. |
| AWS | `PASS` | TMDB authenticated REST bronze-to-gold ran through deployed Glue jobs and S3-hosted artifacts. |
| Snowflake | `PASS` | TMDB authenticated REST bronze-to-gold ran through hosted procedure tasks, `{{ secret:snowflake/<alias> }}` resolution and task-history polling. |
| Fabric | `PASS` | TMDB authenticated REST bronze-to-gold completed through generated Fabric notebooks; capacity availability remains an operational platform concern. |
| GCP | `PASS` | TMDB authenticated REST bronze-to-gold completed through the BigQuery/Workflows runtime path. |
