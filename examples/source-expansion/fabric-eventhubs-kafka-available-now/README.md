# Fabric Event Hubs Kafka Available-Now Source Smoke

This project is a focused `F11` source-expansion smoke for Azure Event Hubs
through its Kafka-compatible endpoint.

The contract uses `source.type: kafka_available_now` with
`source.system: azure_eventhubs`, Spark Structured Streaming
`trigger(availableNow=True)`, a declared checkpoint location and a Key Vault
JAAS placeholder. It validates the Event Hubs Kafka-compatible path, not Fabric
Real-Time/Eventstream routing.
