# Databricks Confluent Kafka Available-Now

This example validates Confluent Cloud Kafka ingestion through the Databricks adapter contract runtime. The notebook calls `ingest_databricks_bundle()` against the split contract files; it does not hand-code Spark source or target logic.

Runtime requirements:
- Databricks secret scope `contractforge-secrets`
- Secrets `confluent-kafka-api-key` and `confluent-kafka-api-secret`
- Unity Catalog volume `workspace.cf_databricks_kafka_smoke.kafka_smoke` for checkpoints
- Job environment dependencies for `contractforge-core` and `contractforge-databricks`
