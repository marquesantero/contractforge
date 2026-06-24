# Test Contracts Across Adapters

Define ingestion intent once. Run it natively anywhere.

This page shows the USGS GeoJSON medallion ingestion reused across Databricks,
AWS, Snowflake, Fabric and GCP. The contract set keeps the business intent,
quality rules, write behavior and medallion outputs the same. The few
differences are contract parameters needed to bind the same intent to each
adapter's native source, table names, SQL references and storage options.

The point of this page is contract reuse: the same medallion contract family is
carried across adapters, and only the minimal platform bindings change.

## Reused Contract Set

| Contract | Shared ingestion intent |
| --- | --- |
| `bronze_usgs_geojson.ingestion.yaml` | Read the USGS 2.5 day GeoJSON payload into one raw response row with `raw_response` and `response_page_number`. |
| `silver_usgs_events.ingestion.yaml` | Parse `features[]`, produce one row per earthquake event, derive event fields, filter invalid event ids and deduplicate by `earthquake_id`. |
| `gold_usgs_daily_summary.ingestion.yaml` | Aggregate silver events by `event_date` with event counts, tsunami counts, magnitude/depth metrics, reporting networks and latest update time. |
| `gold_usgs_magnitude_bands.ingestion.yaml` | Aggregate silver events by `magnitude_band` and `event_type` with event counts, magnitude metrics and first/latest event times. |

## Shared Contract Parameters

| Parameter group | Content kept the same |
| --- | --- |
| Execution order | `bronze_usgs_geojson`, `silver_usgs_events`, `gold_usgs_daily_summary`, `gold_usgs_magnitude_bands`. |
| Source payload | USGS `2.5_day.geojson` earthquake feed for the same date window and filters. |
| Bronze write behavior | `layer: bronze`, `mode: overwrite`, `schema_policy: permissive`. |
| Bronze quality rules | `required_columns: [raw_response, response_page_number]`, `not_null: [raw_response]`, `unique_key: [response_page_number]`. |
| Silver write behavior | `layer: silver`, `mode: overwrite`, `schema_policy: additive_only`. |
| Silver transformation intent | Shape one event per `features[]` item, standardize timestamps and coordinates, derive `event_date`, `magnitude_band` and `is_tsunami_related`, filter `earthquake_id IS NOT NULL`, deduplicate by `earthquake_id`. |
| Silver quality rules | `not_null: [earthquake_id, event_time, latitude, longitude]`, `unique_key: [earthquake_id]`, coordinate/depth/magnitude validation expressions. |
| Gold write behavior | `layer: gold`, `mode: overwrite`, `schema_policy: additive_only`. |
| Gold quality rules | Daily summary requires `event_date`; magnitude bands requires `magnitude_band`. |
| Expected output rows | Bronze `1`, silver `30`, gold daily `2`, gold magnitude bands `3`. |

## Shared Contract Content

The snippets below show the contract content that is reused, not only the
adapter-specific differences. Exact equality means the YAML block is copied
unchanged across the named adapters. Normalized equality means only native table
references or SQL dialect syntax differ; the contract intent and output shape
remain the same.

### Bronze Source Block

Exact same block in Databricks, AWS, Snowflake, Fabric and GCP:

```yaml
source:
  type: rest_api
  name: usgs_earthquake_2_5_day_geojson
  system: usgs
  request:
    url: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
    method: GET
    headers:
      Accept: application/geo+json, application/json
      User-Agent: ContractForge real ingestion test
  response:
    mode: raw
    raw_column: raw_response
  limits:
    timeout_seconds: 60
    retry_attempts: 3
    retry_backoff_seconds: 2
    max_page_bytes: 10485760
    max_total_bytes: 10485760
    max_records: 1
```

Exact same bronze lifecycle and quality block in Databricks, AWS, Snowflake,
Fabric and GCP:

```yaml
layer: bronze
mode: overwrite
schema_policy: permissive

quality_rules:
  required_columns: [raw_response, response_page_number]
  not_null: [raw_response]
  unique_key: [response_page_number]
```

### Silver Event Contract

Databricks, AWS, Fabric and GCP share the same declarative event-shaping
contract. Snowflake expresses the same output contract as native SQL because
its runtime path executes SQL directly.

```yaml
layer: silver
mode: overwrite
schema_policy: additive_only
select_columns: [raw_response, response_page_number]

schemas:
  usgs_geojson_feed: |
    STRUCT<
      type: STRING,
      metadata: STRUCT<generated: BIGINT, url: STRING, title: STRING, status: BIGINT, api: STRING, count: BIGINT>,
      bbox: ARRAY<DOUBLE>,
      features: ARRAY<STRUCT<
        type: STRING,
        id: STRING,
        properties: STRUCT<
          mag: DOUBLE, place: STRING, time: BIGINT, updated: BIGINT, tz: BIGINT, url: STRING,
          detail: STRING, felt: BIGINT, cdi: DOUBLE, mmi: DOUBLE, alert: STRING, status: STRING,
          tsunami: BIGINT, sig: BIGINT, net: STRING, code: STRING, ids: STRING, sources: STRING,
          types: STRING, nst: BIGINT, dmin: DOUBLE, rms: DOUBLE, gap: DOUBLE, magType: STRING,
          type: STRING, title: STRING
        >,
        geometry: STRUCT<type: STRING, coordinates: ARRAY<DOUBLE>>
      >>
    >

transform:
  shape:
    parse_json:
      - column: raw_response
        alias: payload
        schema_ref: usgs_geojson_feed
    arrays:
      - path: payload.features
        mode: explode_outer
        alias: feature
    columns:
      payload.metadata.generated: {alias: feed_generated_epoch_ms, cast: BIGINT}
      payload.metadata.title: {alias: feed_title, cast: STRING}
      payload.metadata.count: {alias: feed_event_count, cast: BIGINT}
      payload.metadata.api: {alias: feed_api_version, cast: STRING}
      payload.bbox: {alias: feed_bbox}
      feature.id: {alias: earthquake_id, cast: STRING}
      feature.type: {alias: geojson_feature_type, cast: STRING}
      feature.properties.title: {alias: event_title, cast: STRING}
      feature.properties.place: {alias: place, cast: STRING}
      feature.properties.mag: {alias: magnitude, cast: DOUBLE}
      feature.properties.magType: {alias: magnitude_type, cast: STRING}
      feature.properties.time: {alias: event_epoch_ms, cast: BIGINT}
      feature.properties.updated: {alias: updated_epoch_ms, cast: BIGINT}
      feature.properties.status: {alias: event_status, cast: STRING}
      feature.properties.type: {alias: event_type, cast: STRING}
      feature.properties.alert: {alias: alert_level, cast: STRING}
      feature.properties.tsunami: {alias: tsunami_flag, cast: INT}
      feature.properties.sig: {alias: significance, cast: BIGINT}
      feature.properties.net: {alias: network, cast: STRING}
      feature.properties.code: {alias: network_event_code, cast: STRING}
      feature.properties.url: {alias: event_url, cast: STRING}
      feature.properties.detail: {alias: detail_url, cast: STRING}
      feature.properties.felt: {alias: felt_reports, cast: BIGINT}
      feature.properties.cdi: {alias: community_intensity, cast: DOUBLE}
      feature.properties.mmi: {alias: instrumental_intensity, cast: DOUBLE}
      feature.geometry.type: {alias: geometry_type, cast: STRING}
      feature.geometry.coordinates: {alias: coordinates}
      longitude: {alias: longitude, expression: "CAST(feature.geometry.coordinates[0] AS DOUBLE)"}
      latitude: {alias: latitude, expression: "CAST(feature.geometry.coordinates[1] AS DOUBLE)"}
      depth_km: {alias: depth_km, expression: "CAST(feature.geometry.coordinates[2] AS DOUBLE)"}
  standardize:
    event_status: {trim: true, lower: true, empty_as_null: true}
    event_type: {trim: true, lower: true, empty_as_null: true}
    magnitude_type: {trim: true, lower: true, empty_as_null: true}
    alert_level: {trim: true, lower: true, empty_as_null: true}
    network: {trim: true, lower: true}
  derive:
    event_time: CAST(from_unixtime(event_epoch_ms / 1000) AS TIMESTAMP)
    updated_at: CAST(from_unixtime(updated_epoch_ms / 1000) AS TIMESTAMP)
    feed_generated_at: CAST(from_unixtime(feed_generated_epoch_ms / 1000) AS TIMESTAMP)
    event_date: to_date(CAST(from_unixtime(event_epoch_ms / 1000) AS TIMESTAMP))
    magnitude_band: CASE WHEN magnitude IS NULL THEN 'unknown' WHEN magnitude < 3 THEN 'minor' WHEN magnitude < 5 THEN 'light' WHEN magnitude < 7 THEN 'strong' ELSE 'major' END
    is_tsunami_related: tsunami_flag = 1
    normalized_at_utc: CURRENT_TIMESTAMP()
  deduplicate:
    keys: [earthquake_id]
    order_by:
      - {column: updated_at, direction: desc, nulls: last}
      - {column: feed_generated_at, direction: desc, nulls: last}

filter_expression: earthquake_id IS NOT NULL
```

Exact same silver quality block in Databricks, AWS, Snowflake, Fabric and GCP:

```yaml
quality_rules:
  not_null: [earthquake_id, event_time, latitude, longitude]
  unique_key: [earthquake_id]
  expressions:
    - name: valid_geojson_point
      expression: geometry_type = 'Point'
      severity: warn
      message: USGS summary feeds should expose point geometries.
    - name: valid_coordinates
      expression: latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180
      severity: abort
      message: Coordinates must be valid WGS84 latitude/longitude.
    - name: reasonable_depth
      expression: depth_km IS NULL OR depth_km BETWEEN -20 AND 800
      severity: warn
      message: Earthquake depth is outside the expected operational range.
    - name: non_negative_magnitude
      expression: magnitude IS NULL OR magnitude >= 0
      severity: warn
      message: Magnitude should not be negative for normal earthquake events.
```

### Gold Daily Summary Contract

Normalized same query shape in Databricks, AWS, Snowflake, Fabric and GCP. The
source table identifier differs by adapter; Snowflake uses `IFF` for the
boolean sum.

```sql
SELECT
  event_date,
  COUNT(*) AS earthquake_count,
  SUM(CASE WHEN is_tsunami_related THEN 1 ELSE 0 END) AS tsunami_related_count,
  AVG(magnitude) AS avg_magnitude,
  MAX(magnitude) AS max_magnitude,
  AVG(depth_km) AS avg_depth_km,
  COUNT(DISTINCT network) AS reporting_networks,
  MAX(updated_at) AS last_event_update_at,
  CURRENT_TIMESTAMP() AS computed_at_utc
FROM <silver_events_table>
WHERE event_date IS NOT NULL
GROUP BY event_date
```

Exact same daily summary lifecycle and quality block in Databricks, AWS,
Snowflake, Fabric and GCP:

```yaml
layer: gold
mode: overwrite
schema_policy: additive_only

quality_rules:
  not_null: [event_date]
  expressions:
    - name: positive_daily_count
      expression: earthquake_count > 0
      severity: abort
      message: Daily summary rows must represent at least one earthquake.
```

### Gold Magnitude Bands Contract

Normalized same query body in Databricks, AWS, Snowflake, Fabric and GCP. Only
the source table identifier changes.

```sql
SELECT
  magnitude_band,
  event_type,
  COUNT(*) AS event_count,
  MIN(magnitude) AS min_magnitude,
  AVG(magnitude) AS avg_magnitude,
  MAX(magnitude) AS max_magnitude,
  MIN(event_time) AS first_event_time,
  MAX(event_time) AS latest_event_time,
  CURRENT_TIMESTAMP() AS computed_at_utc
FROM <silver_events_table>
GROUP BY magnitude_band, event_type
```

Exact same magnitude-band lifecycle and quality block in Databricks, AWS,
Snowflake, Fabric and GCP:

```yaml
layer: gold
mode: overwrite
schema_policy: additive_only

quality_rules:
  not_null: [magnitude_band]
  expressions:
    - name: positive_band_count
      expression: event_count > 0
      severity: abort
      message: Magnitude-band summary rows must represent at least one event.
```

### Annotations And Operations

The annotation and operation contracts keep the same content across adapters.
For example, the bronze annotation block is:

```yaml
table:
  description: Raw USGS Earthquake GeoJSON feed response.
  tags:
    domain: geospatial
    provider: usgs
    source_format: geojson
columns:
  raw_response:
    description: Raw GeoJSON FeatureCollection response body.
  response_page_number:
    description: REST connector page number.
```

The bronze operations block is also identical across adapters:

```yaml
criticality: medium
expected_frequency: daily
freshness_sla_minutes: 1440
alert_on_failure: true
alert_on_quality_fail: true
runbook_url: https://example.com/runbooks/contractforge/usgs-earthquake-feed
ownership:
  business_owner: platform-data
  technical_owner: data-engineering
tags:
  project: usgs-rest-medallion
  layer: bronze
```

## Adapter Binding Differences

Formerly tracked as Contract Parameter Differences; the comparison is now
organized around adapter bindings because the reusable contract surface is
larger than the adapter-specific surface.

Each adapter writes to its native table namespace.

The reusable contract surface is larger than the adapter-specific surface. The
source connector, bronze raw response shape, medallion order, quality gates,
write mode and gold business outputs stay aligned. The differences below are
native bindings: where each adapter stores tables, how it references the
previous layer and which platform prerequisite is needed to execute the same
intent.

<div className="adapter-binding-summary">
<div><span>Source</span><strong><code>rest_api</code> + same USGS GeoJSON URL</strong></div>
<div><span>Shape</span><strong><code>raw_response</code> bronze payload, same silver event model</strong></div>
<div><span>Result</span><strong>same medallion order and row-count expectations</strong></div>
</div>

<div className="adapter-binding-list">
<article className="adapter-binding-row">
<header>
<span>Databricks</span>
<h3>Unity Catalog and Delta</h3>
<p>Contract logic is declarative; native binding is catalog/schema/table plus a Delta table property.</p>
</header>
<dl>
<dt>Bronze target</dt>
<dd><code>workspace.cf_usgs_rest_bronze.b_usgs_earthquake_geojson</code></dd>
<dt>Silver target</dt>
<dd><code>workspace.cf_usgs_rest_silver.s_usgs_earthquake_events</code></dd>
<dt>Gold targets</dt>
<dd><code>workspace.cf_usgs_rest_gold.g_usgs_earthquake_daily_summary</code><code>workspace.cf_usgs_rest_gold.g_usgs_earthquake_magnitude_bands</code></dd>
<dt>Native hint</dt>
<dd><code>delta.enableChangeDataFeed: "true"</code></dd>
</dl>
</article>

<article className="adapter-binding-row">
<header>
<span>AWS</span>
<h3>Glue Catalog and Iceberg</h3>
<p>Contract logic is declarative; native binding adds Glue/Iceberg references and an S3 warehouse location.</p>
</header>
<dl>
<dt>Bronze target</dt>
<dd><code>contractforge.cf_usgs_rest_bronze.b_usgs_earthquake_geojson</code></dd>
<dt>Silver input</dt>
<dd><code>glue_catalog.contractforge_cf_usgs_rest_bronze.b_usgs_earthquake_geojson</code></dd>
<dt>Gold targets</dt>
<dd><code>contractforge.cf_usgs_rest_gold.g_usgs_earthquake_daily_summary</code><code>contractforge.cf_usgs_rest_gold.g_usgs_earthquake_magnitude_bands</code></dd>
<dt>Native hint</dt>
<dd><code>s3://.../warehouse/usgs-rest/</code></dd>
</dl>
</article>

<article className="adapter-binding-row">
<header>
<span>Snowflake</span>
<h3>Database schema and SQL</h3>
<p>The REST source is the same; native binding adds database objects, SQL text and external access.</p>
</header>
<dl>
<dt>Bronze target</dt>
<dd><code>CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_BRONZE</code></dd>
<dt>Silver target</dt>
<dd><code>CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_SILVER</code></dd>
<dt>Gold targets</dt>
<dd><code>CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_GOLD_DAILY</code><code>CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_REST_GOLD_BANDS</code></dd>
<dt>Runtime prerequisite</dt>
<dd><code>CF_USGS_REST_ACCESS</code></dd>
</dl>
</article>

<article className="adapter-binding-row">
<header>
<span>Fabric</span>
<h3>Lakehouse notebooks and Delta</h3>
<p>The same medallion intent runs through generated Fabric notebooks with Lakehouse tables and control-table evidence.</p>
</header>
<dl>
<dt>Bronze target</dt>
<dd><code>cf_usgs_rest_bronze.b_usgs_earthquake_geojson</code></dd>
<dt>Silver target</dt>
<dd><code>cf_usgs_rest_silver.s_usgs_earthquake_events</code></dd>
<dt>Gold targets</dt>
<dd><code>cf_usgs_rest_gold.g_usgs_earthquake_daily_summary</code><code>cf_usgs_rest_gold.g_usgs_earthquake_magnitude_bands</code></dd>
<dt>Runtime prerequisite</dt>
<dd><code>Fabric workspace + Lakehouse + notebook execution</code></dd>
</dl>
</article>

<article className="adapter-binding-row">
<header>
<span>GCP</span>
<h3>BigQuery and Workflows</h3>
<p>The same source and medallion outputs run through BigQuery tables, BigQuery SQL and the certified Workflows runner path.</p>
</header>
<dl>
<dt>Bronze target</dt>
<dd><code>contractforge_test.cf_usgs_rest_bronze.b_usgs_earthquake_geojson</code></dd>
<dt>Silver target</dt>
<dd><code>contractforge_test.cf_usgs_rest_silver.s_usgs_earthquake_events</code></dd>
<dt>Gold targets</dt>
<dd><code>contractforge_test.cf_usgs_rest_gold.g_usgs_earthquake_daily_summary</code><code>contractforge_test.cf_usgs_rest_gold.g_usgs_earthquake_magnitude_bands</code></dd>
<dt>Runtime prerequisite</dt>
<dd><code>BigQuery dataset + GCS artifacts + optional Workflows runner</code></dd>
</dl>
</article>
</div>

### Difference Ledger

| Concern | What stays the same | Native difference |
| --- | --- | --- |
| REST source | All adapters declare `source.type: rest_api`, `method: GET`, the same URL and the same raw response column. | Snowflake hosted procedure execution also needs the `CF_USGS_REST_ACCESS` external access integration; Fabric and GCP bind through their adapter-owned runtime surfaces. |
| Table binding | Each contract writes bronze, silver and gold layers with the same logical role. | Catalog, schema and table names follow each platform's naming model. |
| Layer references | Silver reads bronze; gold reads silver. | Fully qualified references differ between Unity Catalog, Glue Catalog/Iceberg, Snowflake database objects, Fabric Lakehouse tables and BigQuery datasets. |
| Silver transformation | The output event shape, filters, derived fields and deduplication rule are the same. | Databricks, AWS, Fabric and GCP use the declarative transform path; Snowflake uses native SQL text with `PARSE_JSON`, `LATERAL FLATTEN` and `QUALIFY`. |
| Storage hints | Storage configuration does not change business logic or quality semantics. | Databricks sets a Delta property; AWS sets an Iceberg warehouse path; Fabric uses Lakehouse storage; GCP binds BigQuery/GCS artifacts; this Snowflake contract has no storage extension. |

For authenticated REST, the same principle applies: the contract keeps the
logical source and request shape, while each adapter owns the native secret
binding. Snowflake uses `{{ secret:snowflake/<alias> }}` in the contract and
declares the alias under `parameters.snowflake.secrets` in the environment so
the hosted procedure can render a Snowflake `SECRETS = (...)` binding.

Recent real-source validation extended this pattern with a TMDB authenticated
REST project. AWS, Snowflake, Fabric and GCP completed bronze-to-gold execution
with deployed platform artifacts. Databricks completed the same bronze-to-gold
REST pattern with USGS; the TMDB endpoint was blocked by workspace DNS for
`api.themoviedb.org`, which is tracked as a platform administration issue rather
than a ContractForge semantic gap.

## Contract Parameter Snippets

Shared quality and write intent:

```yaml
mode: overwrite
schema_policy: additive_only
quality_rules:
  not_null: [earthquake_id, event_time, latitude, longitude]
  unique_key: [earthquake_id]
```

Databricks bronze binding:

```yaml
source:
  type: rest_api
  request:
    method: GET
    url: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
target:
  catalog: workspace
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
```

AWS bronze binding:

```yaml
source:
  type: rest_api
  request:
    method: GET
    url: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
target:
  catalog: contractforge
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
```

Snowflake bronze binding:

```yaml
source:
  type: rest_api
  request:
    method: GET
    url: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
target:
  catalog: CONTRACTFORGE_TEST_DB
  schema: PUBLIC
  table: CF_USGS_REST_BRONZE
```

Fabric bronze binding:

```yaml
source:
  type: rest_api
  request:
    method: GET
    url: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
target:
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
extensions:
  fabric:
    lakehouse: contractforge_test_lakehouse
```

GCP bronze binding:

```yaml
source:
  type: rest_api
  request:
    method: GET
    url: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson
target:
  catalog: contractforge-test
  schema: cf_usgs_rest_bronze
  table: b_usgs_earthquake_geojson
extensions:
  gcp:
    location: US
```
