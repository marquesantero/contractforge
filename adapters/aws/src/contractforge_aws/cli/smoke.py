"""AWS CLI command for the manual cost-gated smoke runner."""

from __future__ import annotations

import argparse

from contractforge_aws.smoke.kafka_provider_matrix import main as smoke_kafka_provider_matrix_main
from contractforge_aws.smoke.lakeformation import main as smoke_lakeformation_main
from contractforge_aws.smoke.minimal import main as smoke_minimal_main


def add_smoke_subparsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    canonical = subparsers.add_parser("smoke", help="Run or dry-run the cost-gated AWS Glue/Iceberg smoke test.")
    _add_minimal_smoke_args(canonical)

    smoke = subparsers.add_parser("smoke-minimal", help="Run or dry-run the cost-gated AWS Glue/Iceberg smoke test.")
    _add_minimal_smoke_args(smoke)

    lf = subparsers.add_parser(
        "smoke-lakeformation-consumer-matrix",
        help="Run or dry-run the AWS Lake Formation consumer-matrix preflight.",
    )
    lf.add_argument("--account-id", required=True)
    lf.add_argument("--region", default="us-east-1")
    lf.add_argument("--database", required=True)
    lf.add_argument("--table", required=True)
    lf.add_argument("--consumer-principal")
    lf.add_argument("--athena-workgroup", default="primary")
    lf.add_argument("--athena-output-location")
    lf.add_argument("--validate-athena-reads", action="store_true")
    lf.add_argument("--athena-allowed-role-arn")
    lf.add_argument("--athena-denied-role-arn")
    lf.add_argument("--validate-glue-reads", action="store_true")
    lf.add_argument("--glue-script-s3-uri")
    lf.add_argument("--glue-allowed-role-arn")
    lf.add_argument("--glue-denied-role-arn")
    lf.add_argument("--glue-temp-dir")
    lf.add_argument("--glue-warehouse-s3-uri")
    lf.add_argument("--execute", action="store_true")

    kafka = subparsers.add_parser(
        "smoke-kafka-provider-matrix",
        help="Run or dry-run the AWS Kafka provider-matrix preflight.",
    )
    kafka.add_argument("--account-id", required=True)
    kafka.add_argument("--region", default="us-east-1")
    kafka.add_argument("--msk-cluster-arn")
    kafka.add_argument("--confluent-bootstrap-servers")
    kafka.add_argument("--confluent-secret-arn")
    kafka.add_argument("--execute", action="store_true")


def _add_minimal_smoke_args(smoke: argparse.ArgumentParser) -> None:
    smoke.add_argument("--account-id", required=True)
    smoke.add_argument("--region", default="us-east-1")
    smoke.add_argument("--bucket", required=True)
    smoke.add_argument("--role-name", default="ContractForgeGlueSmokeRole")
    smoke.add_argument("--job-name", default="cf-aws-smoke-orders-overwrite")
    smoke.add_argument("--max-estimated-cost-usd", type=float, required=True)
    smoke.add_argument("--dpu-hour-usd", type=float, default=0.44)
    smoke.add_argument("--execute", action="store_true")
    smoke.add_argument("--wait", action="store_true")


def handle_smoke_command(args: argparse.Namespace) -> int | None:
    if args.command == "smoke-kafka-provider-matrix":
        smoke_args = ["--account-id", args.account_id, "--region", args.region]
        if args.msk_cluster_arn:
            smoke_args.extend(("--msk-cluster-arn", args.msk_cluster_arn))
        if args.confluent_bootstrap_servers:
            smoke_args.extend(("--confluent-bootstrap-servers", args.confluent_bootstrap_servers))
        if args.confluent_secret_arn:
            smoke_args.extend(("--confluent-secret-arn", args.confluent_secret_arn))
        if args.execute:
            smoke_args.append("--execute")
        return smoke_kafka_provider_matrix_main(smoke_args)
    if args.command == "smoke-lakeformation-consumer-matrix":
        smoke_args = [
            "--account-id",
            args.account_id,
            "--region",
            args.region,
            "--database",
            args.database,
            "--table",
            args.table,
            "--athena-workgroup",
            args.athena_workgroup,
        ]
        if args.consumer_principal:
            smoke_args.extend(("--consumer-principal", args.consumer_principal))
        if args.athena_output_location:
            smoke_args.extend(("--athena-output-location", args.athena_output_location))
        if args.validate_athena_reads:
            smoke_args.append("--validate-athena-reads")
        if args.athena_allowed_role_arn:
            smoke_args.extend(("--athena-allowed-role-arn", args.athena_allowed_role_arn))
        if args.athena_denied_role_arn:
            smoke_args.extend(("--athena-denied-role-arn", args.athena_denied_role_arn))
        if args.validate_glue_reads:
            smoke_args.append("--validate-glue-reads")
        if args.glue_script_s3_uri:
            smoke_args.extend(("--glue-script-s3-uri", args.glue_script_s3_uri))
        if args.glue_allowed_role_arn:
            smoke_args.extend(("--glue-allowed-role-arn", args.glue_allowed_role_arn))
        if args.glue_denied_role_arn:
            smoke_args.extend(("--glue-denied-role-arn", args.glue_denied_role_arn))
        if args.glue_temp_dir:
            smoke_args.extend(("--glue-temp-dir", args.glue_temp_dir))
        if args.glue_warehouse_s3_uri:
            smoke_args.extend(("--glue-warehouse-s3-uri", args.glue_warehouse_s3_uri))
        if args.execute:
            smoke_args.append("--execute")
        return smoke_lakeformation_main(smoke_args)
    if args.command not in {"smoke", "smoke-minimal"}:
        return None
    smoke_args = [
        "--account-id",
        args.account_id,
        "--region",
        args.region,
        "--bucket",
        args.bucket,
        "--role-name",
        args.role_name,
        "--job-name",
        args.job_name,
        "--max-estimated-cost-usd",
        str(args.max_estimated_cost_usd),
        "--dpu-hour-usd",
        str(args.dpu_hour_usd),
    ]
    if args.execute:
        smoke_args.append("--execute")
    if args.wait:
        smoke_args.append("--wait")
    return smoke_minimal_main(smoke_args)
