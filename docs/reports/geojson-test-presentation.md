# GeoJSON E2E Test Presentation Runbook

## Purpose

This runbook presents the ContractForge adapter parity proof based on the
USGS GeoJSON medallion contracts. Keep the public documentation page named
`test-contracts-across-adapters`; that page is the canonical side-by-side
contract comparison for Databricks, AWS, Snowflake, Fabric and GCP.

The scenario proves that the same ingestion intent can run through all stable
adapters with only native table, SQL dialect, storage and account-network
bindings changed:

- public USGS `2.5_day.geojson` earthquake payload;
- bronze raw GeoJSON landing;
- silver event shaping from `features[]`;
- coordinate extraction, timestamp normalization and deduplication;
- gold daily and magnitude-band aggregates;
- adapter-native execution and control-table evidence.

The presentation rule is strict: no workaround project code. Contracts,
environment files and adapter CLIs drive the execution.

## Canonical Page

Use this page in the site and demos:

```text
docs/adapters/test-contracts-across-adapters.md
```

Published route:

```text
/docs/adapters/test-contracts-across-adapters
```

## Shared Contract Set

```text
examples/real-world/usgs-earthquake-rest-medallion/
```

| Contract | Shared ingestion intent |
| --- | --- |
| `bronze_usgs_geojson.ingestion.yaml` | Store the GeoJSON payload as one bronze raw response row. |
| `silver_usgs_events.ingestion.yaml` | Parse `features[]`, type fields, extract coordinates and deduplicate events. |
| `gold_usgs_daily_summary.ingestion.yaml` | Aggregate silver events by event date. |
| `gold_usgs_magnitude_bands.ingestion.yaml` | Aggregate silver events by magnitude band and event type. |

## Expected Cross-Adapter Results

| Output | Expected rows |
| --- | ---: |
| bronze GeoJSON raw response | 1 |
| silver earthquake events | 30 |
| gold daily summary | 2 |
| gold magnitude bands | 3 |

| Evidence surface | Expected result |
| --- | --- |
| `ctrl_ingestion_runs` | Four successful target runs. |
| `ctrl_ingestion_quality` | Quality rows recorded for bronze, silver and gold contracts. |
| `ctrl_ingestion_quarantine` | Empty for the validated payload. |
| `ctrl_ingestion_errors` | Empty for successful runs. |

## Adapter Bindings

| Concern | Databricks | AWS | Snowflake |
| --- | --- | --- | --- |
| Bronze source | REST API request to the USGS endpoint. | REST API request to the USGS endpoint. | REST API request to the USGS endpoint through Snowflake external access integration. |
| Runtime | Databricks adapter runtime. | AWS Glue stable runner. | Snowflake hosted procedure SQL runner. |
| Table format | Delta. | Iceberg. | Snowflake native tables. |
| Artifact publication | Databricks workspace/bundle artifacts. | S3 Glue artifacts. | Snowflake stage artifacts. |
| Evidence | Delta control tables. | Iceberg control tables queried through Athena. | Snowflake control tables. |

## Presentation Storyline

1. Open `test-contracts-across-adapters`.
2. Show that the contract intent is the same: source payload, bronze raw
   landing, silver event shape, gold aggregates and quality rules.
3. Show the small native binding differences for each adapter.
4. Run or present the adapter executions.
5. Compare the target row counts and evidence tables.
6. Call out honest portability: where a source binding is not native, the
   adapter must use explicit review-required or adapter-specific binding, not a
   hidden workaround.

## Commands To Reproduce

Local planning and rendering should use the project contracts directly:

```powershell
uv run contractforge validate-project examples/real-world/usgs-earthquake-rest-medallion
uv run contractforge-databricks render-project-bundle examples/real-world/usgs-earthquake-rest-medallion/project.yaml
uv run contractforge-aws deploy-project examples/real-world/usgs-earthquake-rest-medallion/project.yaml --dry-run --summary-only
uv run contractforge-snowflake deploy-project examples/real-world/usgs-earthquake-rest-medallion/project.yaml --dry-run --summary-only
uv run contractforge-fabric run-project examples/real-world/usgs-earthquake-rest-medallion/project.yaml --environment-key fabric
uv run contractforge-gcp run-project examples/real-world/usgs-earthquake-rest-medallion/project.yaml --environment-key gcp
```

Runtime commands depend on the configured profiles and environments, but the
acceptance gate is the same for all adapters: the four medallion targets must
complete from contracts and evidence must show successful runs, passing quality,
no quarantine rows and no errors.

## Claims Allowed

- GeoJSON is the cross-adapter parity proof for Databricks, AWS, Snowflake,
  Fabric and GCP.
- The same medallion intent is preserved across Delta, Iceberg, Snowflake
  native tables and BigQuery native tables.
- Runtime artifacts are native to each platform.
- Control-table evidence is a ContractForge product surface.
- Source and table bindings may differ when they are explicit contract
  parameters.
- Snowflake REST execution has an explicit account prerequisite:
  `CF_USGS_REST_ACCESS` must allow outbound HTTPS to `earthquake.usgs.gov:443`.

## Claims To Avoid

- Do not claim every source connector is equally native on every adapter.
- Do not use JDBC/database-source tests as the three-adapter parity proof.
- Do not claim unsupported features are silently translated.
- Do not claim historical semantics or governance behavior beyond the maturity
  evidence already recorded for each adapter.

## Cleanup

Only clean up after release evidence has been captured.

Databricks cleanup:

```sql
DROP SCHEMA IF EXISTS workspace.cf_usgs_rest_bronze CASCADE;
DROP SCHEMA IF EXISTS workspace.cf_usgs_rest_silver CASCADE;
DROP SCHEMA IF EXISTS workspace.cf_usgs_rest_gold CASCADE;
DROP SCHEMA IF EXISTS workspace.cf_usgs_rest_ops CASCADE;
```

AWS cleanup:

```powershell
aws glue get-jobs --region $AWS_REGION
aws glue delete-job --job-name <job-name> --region $AWS_REGION
aws glue delete-database --name contractforge_cf_usgs_rest_bronze --region $AWS_REGION
aws glue delete-database --name contractforge_cf_usgs_rest_silver --region $AWS_REGION
aws glue delete-database --name contractforge_cf_usgs_rest_gold --region $AWS_REGION
aws s3 rm s3://$AWS_ARTIFACT_BUCKET/contractforge-usgs-rest/ --recursive --region $AWS_REGION
```

Snowflake cleanup:

```sql
DROP TABLE IF EXISTS CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_BRONZE;
DROP TABLE IF EXISTS CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_SILVER;
DROP TABLE IF EXISTS CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_GOLD_DAILY;
DROP TABLE IF EXISTS CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_GOLD_BANDS;
```

## Completion Checklist

- [ ] `test-contracts-across-adapters` reviewed as the canonical page.
- [ ] Databricks execution completed from the GeoJSON contracts.
- [ ] AWS Glue execution completed from the GeoJSON contracts.
- [ ] Snowflake execution completed from the GeoJSON contracts.
- [ ] Target row counts match the expected cross-adapter result.
- [ ] Run, quality, quarantine and error evidence captured for each adapter.
- [ ] Any warning, review-required or unsupported boundary recorded explicitly.
