"""CLI entry point for the minimal AWS Glue/Iceberg smoke test."""

from __future__ import annotations

import argparse
import json
import sys

from contractforge_aws.smoke.models import DEFAULT_DPU_HOUR_USD, SmokeConfig, smoke_contract, validate_cost_ceiling
from contractforge_aws.smoke.runner import dry_run_payload, execute_smoke


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-aws-smoke-minimal")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--role-name", default="ContractForgeGlueSmokeRole")
    parser.add_argument("--job-name", default="cf-aws-smoke-orders-overwrite")
    parser.add_argument("--max-estimated-cost-usd", type=float, required=True)
    parser.add_argument("--dpu-hour-usd", type=float, default=DEFAULT_DPU_HOUR_USD)
    parser.add_argument("--execute", action="store_true", help="Actually publish/register/start the Glue job.")
    parser.add_argument("--wait", action="store_true", help="Wait for Glue job completion when --execute is used.")
    args = parser.parse_args(argv)

    config = SmokeConfig(
        account_id=args.account_id,
        region=args.region,
        bucket=args.bucket,
        role_name=args.role_name,
        job_name=args.job_name,
        max_estimated_cost_usd=args.max_estimated_cost_usd,
        dpu_hour_usd=args.dpu_hour_usd,
    )
    validate_cost_ceiling(config)
    payload = execute_smoke(config, wait=args.wait) if args.execute else dry_run_payload(config, execute=False)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


__all__ = ["main", "smoke_contract"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
