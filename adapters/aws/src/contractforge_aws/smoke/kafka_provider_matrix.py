"""AWS Kafka provider-matrix smoke preflight."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from contractforge_aws.runtime.dependencies import require_boto3


@dataclass(frozen=True)
class KafkaProviderMatrixConfig:
    account_id: str
    region: str
    msk_cluster_arn: str | None = None
    confluent_bootstrap_servers: str | None = None
    confluent_secret_arn: str | None = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-aws smoke-kafka-provider-matrix")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--msk-cluster-arn")
    parser.add_argument("--confluent-bootstrap-servers")
    parser.add_argument("--confluent-secret-arn")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    config = KafkaProviderMatrixConfig(
        account_id=args.account_id,
        region=args.region,
        msk_cluster_arn=args.msk_cluster_arn,
        confluent_bootstrap_servers=args.confluent_bootstrap_servers,
        confluent_secret_arn=args.confluent_secret_arn,
    )
    payload = execute_preflight(config) if args.execute else dry_run_payload(config)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["status"] in {"DRY_RUN", "READY_TO_RUN", "PASS", "BLOCKED"} else 1


def dry_run_payload(config: KafkaProviderMatrixConfig) -> dict[str, Any]:
    return {"status": "DRY_RUN", "config": asdict(config), "required_cases": required_cases()}


def execute_preflight(config: KafkaProviderMatrixConfig) -> dict[str, Any]:
    boto3 = require_boto3()
    providers = {
        "event_hubs_kafka": _event_hubs_result(),
        "msk": _msk_result(boto3.client("kafka", region_name=config.region), config),
        "confluent_compatible": _confluent_result(config),
    }
    blockers = [blocker for result in providers.values() for blocker in result.get("blockers", [])]
    status = _overall_status(providers, blockers)
    return {
        "status": status,
        "config": asdict(config),
        "required_cases": required_cases(),
        "providers": providers,
        "blockers": blockers,
    }


def _overall_status(providers: dict[str, dict[str, Any]], blockers: list[str]) -> str:
    required_blockers = [
        blocker
        for provider_name, result in providers.items()
        if provider_name != "confluent_compatible"
        for blocker in result.get("blockers", [])
    ]
    if required_blockers:
        return "BLOCKED"
    if providers["msk"].get("status") == "READY_TO_RUN":
        return "READY_TO_RUN"
    return "PASS"


def required_cases() -> list[str]:
    return [
        "provider_available_now_glue_run",
        "checkpoint_progress_recorded",
        "no_input_rerun_records_zero_new_rows",
        "offset_or_position_semantics_recorded",
        "redacted_failure_evidence_recorded",
        "stream_evidence_and_cost_rows_recorded",
    ]


def _event_hubs_result() -> dict[str, Any]:
    return {
        "status": "PASS",
        "evidence": "examples/real-world/aws-eventhubs-kafka-available-now",
        "notes": [
            "Azure Event Hubs through Kafka protocol is already validated for Glue available-now streaming.",
            "Evidence includes checkpoint progression, no-input rerun, quarantine/target writes, cost and Athena audit.",
        ],
        "blockers": [],
    }


def _msk_result(kafka: Any, config: KafkaProviderMatrixConfig) -> dict[str, Any]:
    if config.msk_cluster_arn:
        try:
            return _msk_cluster_arn_result(kafka, config.msk_cluster_arn)
        except Exception as exc:  # pragma: no cover - live AWS diagnostic path
            return {
                "status": "BLOCKED",
                "cluster_arn": config.msk_cluster_arn,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "blockers": ["MSK cluster validation failed; verify the cluster ARN and AWS MSK API access."],
            }
    try:
        clusters = _list_msk_clusters(kafka)
    except Exception as exc:  # pragma: no cover - live AWS diagnostic path
        return {
            "status": "BLOCKED",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "blockers": ["MSK cluster discovery failed; provide --msk-cluster-arn or fix AWS MSK API access."],
        }
    if not clusters:
        return {"status": "BLOCKED", "clusters": [], "blockers": ["No MSK cluster was discovered in the target region."]}
    return {"status": "READY_TO_RUN", "clusters": clusters, "blockers": []}


def _msk_cluster_arn_result(kafka: Any, cluster_arn: str) -> dict[str, Any]:
    described = kafka.describe_cluster_v2(ClusterArn=cluster_arn).get("ClusterInfo", {})
    state = str(described.get("State") or "UNKNOWN")
    cluster_type = str(described.get("ClusterType") or "")
    if state != "ACTIVE":
        return {
            "status": "BLOCKED",
            "cluster_arn": cluster_arn,
            "cluster_name": described.get("ClusterName"),
            "cluster_type": cluster_type,
            "state": state,
            "blockers": [f"MSK cluster is {state}; wait until ACTIVE before live validation."],
        }
    brokers = kafka.get_bootstrap_brokers(ClusterArn=cluster_arn)
    bootstrap_brokers = {
        key: value
        for key, value in brokers.items()
        if key.startswith("BootstrapBrokerString") and value
    }
    return {
        "status": "READY_TO_RUN",
        "cluster_arn": cluster_arn,
        "cluster_name": described.get("ClusterName"),
        "cluster_type": cluster_type,
        "state": state,
        "bootstrap_brokers": bootstrap_brokers,
        "blockers": [],
    }


def _list_msk_clusters(kafka: Any) -> list[dict[str, Any]]:
    try:
        response = kafka.list_clusters_v2(MaxResults=100)
        return response.get("ClusterInfoList", [])
    except Exception:
        response = kafka.list_clusters(MaxResults=100)
        return response.get("ClusterInfoList", [])


def _confluent_result(config: KafkaProviderMatrixConfig) -> dict[str, Any]:
    if config.confluent_bootstrap_servers and config.confluent_secret_arn:
        return {
            "status": "READY_TO_RUN",
            "scope": "OPTIONAL_COMPATIBILITY",
            "bootstrap_servers": config.confluent_bootstrap_servers,
            "secret_arn": config.confluent_secret_arn,
            "blockers": [],
        }
    return {
        "status": "OPTIONAL_NOT_CONFIGURED",
        "scope": "OPTIONAL_COMPATIBILITY",
        "blockers": [],
        "notes": [
            "Confluent-compatible Kafka is tracked as optional provider compatibility; AWS Kafka maturity is validated with MSK."
        ],
    }


__all__ = ["KafkaProviderMatrixConfig", "dry_run_payload", "execute_preflight", "main", "required_cases"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
