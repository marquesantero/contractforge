# AWS Event Hubs Kafka Available-Now

This project validates ContractForge AWS available-now streaming against a real
Azure Event Hubs namespace using its Kafka-compatible endpoint.

It intentionally tests the cross-cloud connector boundary:

- Azure Event Hubs provides the Kafka endpoint and test events.
- AWS Secrets Manager stores the Event Hubs connection string.
- AWS Glue runs the generated ContractForge job.
- ContractForge evidence is written to Iceberg control tables.

## Resources

Current validation resources:

- Azure resource group: `rg-contractforge-stream-test`
- Event Hubs namespace: `cfstreameh0601135444`
- Event hub / Kafka topic: `cf-orders`
- AWS secret: `contractforge-eventhubs`, JSON key `connection_string`

## Commands

Dry-run and compile generated Glue Python:

```powershell
uv run contractforge-aws deploy-project examples/real-world/aws-eventhubs-kafka-available-now/project.yaml `
  --dry-run `
  --summary-only
```

Run the available-now streaming ingestion:

```powershell
uv run contractforge-aws deploy-project examples/real-world/aws-eventhubs-kafka-available-now/project.yaml `
  --run `
  --wait `
  --audit-evidence `
  --athena-output-location s3://contractforge-aws-smoke-000000000000-us-east-1/athena-results/ `
  --poll-interval-seconds 20 `
  --max-wait-seconds 1800
```

Record Glue DPU-second cost for an already completed run:

```powershell
uv run contractforge-aws record-glue-cost examples/real-world/aws-eventhubs-kafka-available-now/contracts/aws/bronze/bronze_eventhub_orders_stream/bronze_eventhub_orders_stream.ingestion.yaml `
  --environment examples/real-world/aws-eventhubs-kafka-available-now/environments/aws.environment.yaml `
  --job-name contractforge_contractforge_cf_eventhubs_stream_bronze_b_eventhub_orders_stream `
  --run-id <glue-run-id> `
  --athena-output-location s3://contractforge-aws-smoke-000000000000-us-east-1/athena-results/
```

## Cleanup

The Azure resources are deliberately isolated. Delete the resource group when
the streaming validation is no longer needed:

```powershell
az group delete --name rg-contractforge-stream-test --yes
```
