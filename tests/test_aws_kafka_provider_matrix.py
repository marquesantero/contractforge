"""AWS Kafka provider-matrix smoke tests."""

from __future__ import annotations

import json

from contractforge_aws.cli.__init__ import main
from contractforge_aws.smoke.kafka_provider_matrix import KafkaProviderMatrixConfig, execute_preflight


class _FakeBoto3:
    def __init__(self) -> None:
        self.kafka = _FakeKafka()

    def client(self, service: str, region_name: str | None = None) -> object:
        assert service == "kafka"
        return self.kafka


class _FakeKafka:
    state = "ACTIVE"

    def list_clusters_v2(self, **kwargs: dict) -> dict:
        return {"ClusterInfoList": []}

    def describe_cluster_v2(self, **kwargs: dict) -> dict:
        return {
            "ClusterInfo": {
                "ClusterArn": kwargs["ClusterArn"],
                "ClusterName": "cf-msk",
                "ClusterType": "SERVERLESS",
                "State": self.state,
            }
        }

    def get_bootstrap_brokers(self, **kwargs: dict) -> dict:
        return {"BootstrapBrokerStringSaslIam": "boot.example.kafka-serverless.us-east-1.amazonaws.com:9098"}


def test_kafka_provider_matrix_dry_run(capsys) -> None:
    assert main(["smoke-kafka-provider-matrix", "--account-id", "123456789012"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "DRY_RUN"
    assert payload["config"]["account_id"] == "123456789012"
    assert "checkpoint_progress_recorded" in payload["required_cases"]


def test_kafka_provider_matrix_blocks_missing_msk_but_not_optional_confluent(monkeypatch) -> None:
    import contractforge_aws.smoke.kafka_provider_matrix as matrix

    monkeypatch.setattr(matrix, "require_boto3", lambda: _FakeBoto3())

    payload = execute_preflight(KafkaProviderMatrixConfig(account_id="123456789012", region="us-east-1"))

    assert payload["status"] == "BLOCKED"
    assert payload["providers"]["event_hubs_kafka"]["status"] == "PASS"
    assert payload["providers"]["msk"]["status"] == "BLOCKED"
    assert payload["providers"]["confluent_compatible"]["status"] == "OPTIONAL_NOT_CONFIGURED"
    assert any("No MSK cluster" in item for item in payload["blockers"])


def test_kafka_provider_matrix_ready_when_provider_inputs_exist(monkeypatch) -> None:
    import contractforge_aws.smoke.kafka_provider_matrix as matrix

    monkeypatch.setattr(matrix, "require_boto3", lambda: _FakeBoto3())

    payload = execute_preflight(
        KafkaProviderMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            msk_cluster_arn="arn:aws:kafka:us-east-1:123456789012:cluster/cf/abc",
            confluent_bootstrap_servers="pkc.example.confluent.cloud:9092",
            confluent_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:confluent",
        )
    )

    assert payload["status"] == "READY_TO_RUN"
    assert payload["providers"]["msk"]["status"] == "READY_TO_RUN"
    assert payload["providers"]["msk"]["state"] == "ACTIVE"
    assert payload["providers"]["msk"]["bootstrap_brokers"]["BootstrapBrokerStringSaslIam"]
    assert payload["providers"]["confluent_compatible"]["status"] == "READY_TO_RUN"
    assert payload["providers"]["confluent_compatible"]["scope"] == "OPTIONAL_COMPATIBILITY"


def test_kafka_provider_matrix_blocks_msk_until_active(monkeypatch) -> None:
    import contractforge_aws.smoke.kafka_provider_matrix as matrix

    fake_boto3 = _FakeBoto3()
    fake_boto3.kafka.state = "CREATING"
    monkeypatch.setattr(matrix, "require_boto3", lambda: fake_boto3)

    payload = execute_preflight(
        KafkaProviderMatrixConfig(
            account_id="123456789012",
            region="us-east-1",
            msk_cluster_arn="arn:aws:kafka:us-east-1:123456789012:cluster/cf/abc",
            confluent_bootstrap_servers="pkc.example.confluent.cloud:9092",
            confluent_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:confluent",
        )
    )

    assert payload["status"] == "BLOCKED"
    assert payload["providers"]["msk"]["state"] == "CREATING"
    assert any("wait until ACTIVE" in blocker for blocker in payload["blockers"])
