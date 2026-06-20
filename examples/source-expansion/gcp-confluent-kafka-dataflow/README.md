# GCP Confluent Kafka Dataflow Source Promotion

This fixture validates the GCP Kafka streaming promotion path without embedding
credentials in contracts. The Confluent/Dataflow provider path has live evidence
for row ingestion, zero-DLQ reconciliation and no-input replay; broader streaming
operations remain review-scoped.

```powershell
contractforge-gcp source-promotion `
  examples/source-expansion/gcp-confluent-kafka-dataflow/contracts/01_confluent_kafka_available_now_orders.ingestion.yaml `
  --environment examples/source-expansion/gcp-confluent-kafka-dataflow/environments/gcp.environment.yaml `
  --execute `
  --readback `
  --report .tmp/gcp-confluent-kafka-dataflow-source-promotion.json
```
