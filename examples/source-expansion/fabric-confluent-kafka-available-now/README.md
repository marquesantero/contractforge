# Fabric Confluent Kafka Available-Now Source Smoke

This source-expansion project validates checkpointed `kafka_available_now`
catch-up on the Fabric adapter using Confluent Cloud Kafka and Azure Key Vault
SASL configuration.

The generated Fabric notebook reads Kafka with Spark Structured Streaming,
writes the available-now result to a Delta materialization path under the
contract checkpoint, then continues through the normal ContractForge batch
quality, write and evidence path.

Run locally against the configured Fabric workspace:

```powershell
$env:PYTHONPATH='adapters/fabric/src;src'
uv run python -m contractforge_fabric.cli smoke-project examples/source-expansion/fabric-confluent-kafka-available-now/project.yaml --environment-key fabric --max-attempts 35 --retry-after-seconds 30
```

