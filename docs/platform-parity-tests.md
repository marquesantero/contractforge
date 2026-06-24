# Platform Parity Tests

These scenarios validate how easily a ContractForge contract moves between
Databricks, AWS, Snowflake, Fabric and GCP.

The rule is strict:

- ingestion intent, target shape, write mode, quality, annotations, operations
  and access intent stay the same;
- only runtime binding changes: source location, environment contract and
  adapter-owned extensions;
- if a platform cannot preserve the same semantics, the adapter must return
  `SUPPORTED_WITH_WARNINGS`, `REVIEW_REQUIRED` or `UNSUPPORTED`.

## Scenarios

The executable scenario definitions live in
`tools/platform_parity/contracts.py`.

| Scenario | Intent | Databricks | AWS | Snowflake | Fabric | GCP |
|---|---|---|---|---|---|---|
| `orders_append_quality` | JSON append with casts, standardization, annotations and quality/quarantine. | `SUPPORTED` | `SUPPORTED` | `SUPPORTED` | `SUPPORTED_WITH_WARNINGS` | `SUPPORTED_WITH_WARNINGS` |
| `orders_overwrite_shape` | JSON overwrite with parse/explode/select shape and expression quality. | `SUPPORTED` | `SUPPORTED_WITH_WARNINGS` | `REVIEW_REQUIRED` | `SUPPORTED_WITH_WARNINGS` | `UNSUPPORTED` |
| `customers_upsert` | current-state upsert with deterministic deduplicate and merge-key guards. | `SUPPORTED` | `SUPPORTED` | `SUPPORTED` | `SUPPORTED_WITH_WARNINGS` | `SUPPORTED_WITH_WARNINGS` |
| `customers_hash_diff` | hash-diff upsert update minimization. | `SUPPORTED` | `SUPPORTED_WITH_WARNINGS` | `SUPPORTED_WITH_WARNINGS` | `SUPPORTED_WITH_WARNINGS` | `REVIEW_REQUIRED` |
| `customers_historical` | Historical SCD2 with effective dating, delete expression and late-arriving reject semantics. | `SUPPORTED` | `REVIEW_REQUIRED` | `REVIEW_REQUIRED` | `SUPPORTED_WITH_WARNINGS` | `REVIEW_REQUIRED` |
| `customers_snapshot_soft_delete` | Complete-source snapshot reconciliation with soft-delete semantics. | `SUPPORTED` | `REVIEW_REQUIRED` | `REVIEW_REQUIRED` | `SUPPORTED_WITH_WARNINGS` | `REVIEW_REQUIRED` |
| `governance_review_boundary` | Same row-filter and column-mask intent. | `SUPPORTED` | `REVIEW_REQUIRED` | `SUPPORTED` | `REVIEW_REQUIRED` | `REVIEW_REQUIRED` |

## Local validation

Run the parity contract tests:

```powershell
uv run pytest tests/test_platform_parity_contracts.py
```

Generate a machine-readable report:

```powershell
uv run python -m tools.platform_parity.report
```

The report includes all adapter statuses, artifact names and the exact
platform delta allowed by the test.

Generate deterministic JSONL data for real smoke runs:

```powershell
uv run python -m tools.platform_parity.data --output .tmp/platform-parity-data
```

Upload each generated scenario directory to the source path shown by
`tools.platform_parity.report`:

- Databricks: `dbfs:/tmp/contractforge/parity/<dataset>/`;
- AWS: `s3://contractforge-parity-us-east-1/data/<dataset>/`;
- Snowflake: `@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_PARITY_DATA"/<dataset>/`.
- Fabric: `Files/contractforge/parity/<dataset>/`.
- GCP: `gs://contractforge-parity-us/data/<dataset>/`.

## Real execution validation

The same scenario contracts should be used for real Databricks, AWS,
Snowflake, Fabric and GCP smoke runs. Do not hand-edit the
ingestion semantics per platform.

Allowed runtime differences:

- Databricks source path, for example `dbfs:/tmp/contractforge/parity/...`;
- AWS source path, for example `s3://contractforge-parity-us-east-1/data/...`;
- Snowflake staged-file source path, for example
  `@"CONTRACTFORGE_TEST_DB"."PUBLIC"."CF_PARITY_DATA"/...`;
- Fabric OneLake Files path, for example `Files/contractforge/parity/...`;
- GCP Cloud Storage source path, for example
  `gs://contractforge-parity-us/data/...`;
- Databricks environment evidence catalog/schema;
- AWS environment evidence database and Glue job deployment defaults;
- Snowflake environment warehouse/schema/stage bindings;
- Fabric environment tenant/workspace/lakehouse/warehouse bindings;
- GCP environment project, location, dataset and evidence dataset bindings;
- AWS `extensions.aws.iceberg.warehouse`;
- Snowflake `extensions.snowflake.explain_enabled`.

Acceptance criteria for a real run:

- target tables are created on all platforms;
- core evidence/control tables are created through the adapters;
- `ctrl_ingestion_runs` records the same logical status per scenario;
- `rows_read`, `rows_written`, `rows_quarantined` and quality status match
  expected scenario data;
- AWS review-only governance remains review-only until Lake Formation
  equivalence is validated for a concrete consumer engine.
- Snowflake shape-heavy nested JSON remains review-required until SQL/Snowpark
  shape parity is validated against Spark/Glue behavior.
- GCP shape-heavy nested JSON remains unsupported in the central parity harness
  until an equivalent BigQuery/Dataflow/Dataproc shaping path is promoted.
- GCP advanced write modes remain review-required in default planning even
  though hash-diff production parity is accepted and historical/snapshot review
  evidence exists.

## USGS GeoJSON Cross-Adapter E2E

The canonical end-to-end adapter parity page is
[Test contracts across adapters](adapters/test-contracts-across-adapters.md).
That page stays focused on the stable Databricks/AWS/Snowflake side-by-side.
The broader USGS example and the shared parity report add the current Fabric
notebook-first subset without changing the core contract intent.

This scenario covers:

- public USGS GeoJSON source intent;
- raw GeoJSON bronze landing;
- `features[]` parsing, array flattening, coordinate extraction and typed event
  fields;
- deterministic event deduplication by `earthquake_id`;
- silver quality rules for event ids, timestamps, latitude and longitude;
- gold daily and magnitude-band aggregates;
- adapter-native target binding for Delta, Iceberg and Snowflake native tables;
- control-table evidence for runs, quality, quarantine and errors.

Expected row counts for the USGS 2.5 day GeoJSON feed validation:

| Output | Rows |
| --- | ---: |
| bronze GeoJSON raw response | 1 |
| silver earthquake events | 30 |
| gold daily summary | 2 |
| gold magnitude bands | 3 |

The adapters keep the same ingestion intent and only change native binding:

| Concern | Databricks | AWS | Snowflake |
| --- | --- | --- | --- |
| Bronze source | REST API request | REST API request | REST API request with Snowflake external access integration |
| Runtime | Databricks adapter runtime | AWS Glue stable runner | Snowflake SQL procedure runner |
| Table format | Delta | Iceberg | Snowflake native table |
| Evidence | Delta control tables | Iceberg control tables queried through Athena | Snowflake control tables |

The parity claim is intentionally narrow: GeoJSON validates the same medallion
contract family across all three adapters. JDBC/database-source parity remains a
separate connector-specific concern and is not the cross-adapter proof page.
Snowflake hosted-procedure REST execution requires `CF_USGS_REST_ACCESS` to
allow outbound HTTPS to `earthquake.usgs.gov:443`.
For authenticated REST sources, the contract uses
`{{ secret:snowflake/<alias> }}` and the Snowflake environment maps that alias
under `parameters.snowflake.secrets`; plaintext credentials are not part of the
parity contract.
