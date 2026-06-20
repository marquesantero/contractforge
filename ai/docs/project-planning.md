# Natural-Language Project Planning

`plan-project` converts a plain-language ingestion scenario into a structured, reviewable project plan. It does not write files, deploy resources or call a model provider. The command extracts deterministic signals, lists missing decisions and recommends one or more generated-project targets.

Use it before `generate-project` when the user knows the scenario but has not yet translated it into exact ContractForge parameters.

## Basic Usage

```bash
contractforge-ai plan-project \
  --intent "Create a silver ingestion from s3a://landing/orders into main.silver.orders using hash_diff_upsert." \
  --schema schemas/orders.json \
  --format markdown
```

The result includes:

- Parsed connector, source, target, layer and write mode.
- Recommended project targets such as `contractforge-yaml`, `databricks-dab`, `contractforge-python`, `dbt` or `classic-pyspark`.
- Platform hints such as AWS or Databricks when the intent names a platform or platform service.
- Ready-to-review `generate-project` commands.
- Missing fields and required decisions.
- Evidence, assumptions and confidence.

## Optional Provider Enrichment

The deterministic planner is the source of truth. When a provider is configured, `--with-ai` can attach advisory enrichment to the same result:

```bash
contractforge-ai plan-project \
  --intent "Create a silver ingestion from s3a://landing/orders into main.silver.orders using hash_diff_upsert." \
  --schema schemas/orders.json \
  --with-ai \
  --provider databricks \
  --format json
```

Provider output is accepted only when it matches the registered structured-output schema. Invalid model output is reported as a failed enrichment and the deterministic planner result remains available.

The enrichment is intended for wording, prioritization and implementation notes. It must not remove missing decisions, mark drafts as production-ready or write files.

`plan-project --with-ai` does not generate files and does not mutate the project specification. Use it when the user wants a planning report. Use `guided-project --with-ai` when provider-backed inference should happen before scaffold generation.

## Intent Files

For longer scenarios, store the request in a file:

```text
Build a Databricks Asset Bundle for a bronze ingestion from
https://example.com/orders.csv into main.bronze.b_orders.
Use schema profile schemas/orders.json and keep output reviewable.
```

```bash
contractforge-ai plan-project \
  --intent-file intent.txt \
  --schema schemas/orders.json \
  --format json
```

## Defaults

Use defaults when users omit environment-specific values:

```bash
contractforge-ai plan-project \
  --intent "Ingest customer data from an API into the lakehouse." \
  --default-catalog main \
  --default-schema bronze \
  --default-layer bronze
```

Defaults reduce noise but do not hide uncertainty. If the source path, target table or schema profile is missing, the output remains `NEEDS_DECISIONS`.

## Preferred Target

Force one recommendation target when the user already knows the delivery style:

```bash
contractforge-ai plan-project \
  --intent "Build a gold overwrite table from Snowflake SALES.ORDERS to analytics.gold.g_orders." \
  --schema schemas/orders.json \
  --preferred-target dbt
```

Supported targets:

| Target | When to use |
| --- | --- |
| `contractforge-yaml` | Default contract-first project with separated ingestion, annotations and operations files. |
| `contractforge-python` | Thin Python entry point for core validation plus explicit adapter planning/execution actions. |
| `databricks-dab` | Deployable Databricks Asset Bundle job structure. |
| `aws-glue-iceberg` | AWS Glue Spark and Iceberg project structure using the AWS adapter runtime. |
| `dbt` | Downstream analytics teams that own dbt models and tests. |
| `classic-pyspark` | Migration comparison from notebook-first PySpark code. |

Storage and table-format terms are connector evidence, not platform preference. For example, `s3://...` selects the `s3` connector but does not by itself mean AWS is the requested runtime, and `iceberg` does not by itself force the AWS adapter.

When the intent clearly names AWS Glue, Athena or Lake Formation, the planner avoids recommending a Databricks Asset Bundle unless Databricks is also explicitly mentioned. When the intent clearly names Databricks, Unity Catalog, Asset Bundles or Auto Loader, the planner avoids recommending AWS unless AWS is also explicitly mentioned. If no platform is named and the connector is supported by multiple adapters, the planner can recommend multiple adapter paths so the user can choose without changing contract intent.

## Review Boundary

The planner is intentionally conservative:

- It does not invent missing connector, source, schema or target values.
- It does not write generated project files.
- It does not call provider-backed enrichment unless `--with-ai` is explicitly used.
- Merge-based modes still require explicit key review.
- Ambiguous scenarios produce `RequiredDecision` entries instead of hidden assumptions.

After review, copy the recommended `generate-project` command and fill any placeholders:

```bash
contractforge-ai generate-project \
  --target contractforge-yaml \
  --schema schemas/orders.json \
  --project-name "Orders" \
  --connector s3 \
  --source-path s3a://landing/orders \
  --target-catalog main \
  --target-schema silver \
  --target-table orders \
  --layer silver \
  --mode hash_diff_upsert
```

## Guided Project Generation

Use `guided-project` when the same command should plan the scenario and generate the selected project scaffold.

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/orders.csv into main.bronze.b_orders." \
  --schema schemas/orders.json \
  --target databricks-dab \
  --output-dir ./generated/orders-dab
```

Add `--with-ai` when a configured provider should enrich the project specification before files are generated:

```bash
contractforge-ai guided-project \
  --intent "Create a bronze ingestion from https://example.com/events into main.bronze.b_events. The source returns nested JSON payloads." \
  --schema schemas/events.json \
  --target contractforge-yaml \
  --with-ai \
  --provider openai \
  --allow-review-required \
  --output-dir ./generated/events
```

The command follows the same deterministic planner rules:

- if the scenario is ready for review, it generates the project target;
- if required decisions remain open, it returns exit code `2` and does not write files;
- `--allow-review-required` writes a review scaffold with placeholders, `DECISIONS.md`, `RUNBOOK.md` and `VALIDATION.md`;
- `--dry-run` returns the planned artifact writes without touching the filesystem.

With `--with-ai`, ContractForge AI builds an enriched project specification before artifact generation. The provider can suggest supported technical fields such as source format, full ContractForge `transform` blocks, draft quality rules, annotations and operations metadata. Critical business decisions remain review-required even if the provider suggests values. Planner-controlled identity fields such as connector, source path, target, layer and mode cannot be silently overwritten by provider output; conflicting proposals are rejected and recorded in the provider proposal audit.

When those values are explicit in the user prompt, the deterministic planner can also carry them without waiting for provider inference. Examples include `operations.technical_owner`, `operations.criticality`, freshness SLA, `quality_rules.not_null`, `quality_rules.unique_key`, `quality_rules.accepted_values`, expression checks and Databricks DAB compute preference.

This keeps natural-language onboarding useful without hiding incomplete production decisions. Merge keys, hash-diff column policy, source completeness, ownership, SLA, PII policy and deployment settings still need explicit review when the planner or enriched spec marks them as unresolved.

## Connector Detection

The planner detects common connector signals from wording and URI schemes:

| Signal | Connector |
| --- | --- |
| `s3://`, `s3a://`, bucket wording | `s3` |
| `abfs://`, `abfss://`, ADLS or Azure Blob wording | `azure_blob` |
| `http://`, `https://` file URL | `http_file` |
| API, REST or endpoint wording | `rest_api` |
| JDBC, PostgreSQL, MySQL, SQL Server, RDS or Oracle database wording | `jdbc` |
| Snowflake wording | `snowflake` |
| BigQuery wording | `bigquery` |
| SharePoint, OneDrive or Graph wording | `sharepoint` |
| SFTP wording | `sftp` |
| Event Hubs or Kafka wording | `eventhubs` or `kafka` |

URI schemes take precedence over generic file-format words. For example, `https://example.com/orders.csv` is treated as `http_file`, not `files`.
