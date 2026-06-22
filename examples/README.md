# ContractForge Examples

Runnable and reference projects that show ContractForge contracts in practice.
Each example is a self-contained folder with its own `README.md`.

New to the project? Start with
[real-world/usgs-earthquake-rest-medallion](real-world/usgs-earthquake-rest-medallion/README.md),
which proves the same ingestion intent across Databricks, AWS, Snowflake,
Fabric and GCP. When adding a new source, use
[source-expansion](source-expansion/) as a template and follow
[docs/specs/source-portability.md](../docs/specs/source-portability.md).

## Real-world projects

End-to-end medallion and failure-path projects on real data.

- [usgs-earthquake-rest-medallion](real-world/usgs-earthquake-rest-medallion/README.md) — REST GeoJSON bronze-to-gold proving the same intent on all five adapters.
- [s3-file-medallion](real-world/s3-file-medallion/README.md) — AWS Glue/Iceberg file ingestion from S3 CSV with bookmarks and control-table evidence.
- [supabase-jdbc-medallion](real-world/supabase-jdbc-medallion/README.md) — JDBC medallion ingestion from a Supabase/Postgres source.
- [aws-incremental-files](real-world/aws-incremental-files/README.md) — AWS Glue incremental file ingestion.
- [aws-eventhubs-kafka-available-now](real-world/aws-eventhubs-kafka-available-now/README.md) — AWS ingestion from Azure Event Hubs (Kafka) in available-now batch mode.
- [databricks-confluent-kafka-available-now](real-world/databricks-confluent-kafka-available-now/README.md) — Databricks ingestion from Confluent Kafka in available-now mode.
- [aws-failure-paths](real-world/aws-failure-paths/README.md) — contract-only negative tests for failed-run evidence, error evidence and redaction.

## Source expansion

Focused projects that each validate one source type, mostly on Microsoft Fabric
and GCP. Browse [source-expansion/](source-expansion/) for the full set; the
families are:

- **Storage shortcuts** — OneLake, ADLS Gen2, Azure Blob, GCS, Amazon S3, S3-compatible and Iceberg-table shortcuts.
- **Authenticated HTTP / REST** — API key, Basic, Bearer and OAuth variants.
- **Databases (JDBC)** — PostgreSQL and SQL Server.
- **Streaming (Kafka)** — Confluent and Event Hubs in available-now mode.
- **Files & text** — Lakehouse file formats, text, and HTTP CSV/JSON/text sources.
- **GCP** — BigQuery JDBC medallion, Dataflow Kafka and HTTP binary file ingestion.

## Benchmarks

Production benchmark fixtures for advanced write behavior.

- [hash-diff-production](benchmarks/hash-diff-production/README.md) — hash-diff upsert production benchmark.
- [advanced-write-production](benchmarks/advanced-write-production/README.md) — advanced write-mode production fixtures.

## Stable surface

- [fabric](stable-surface/fabric/README.md) — Fabric stable-surface evidence example.

---

See the [documentation index](../docs/README.md) for guides and specs, and
[CONTRIBUTING.md](../CONTRIBUTING.md) for how to add an example.
