"""Render a Databricks/AWS/Snowflake/Fabric portability report for parity scenarios."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from contractforge_aws import plan_aws_contract, render_aws_contract
from contractforge_databricks import plan_databricks_contract, render_databricks_contract
from contractforge_fabric import plan_fabric_contract, render_fabric_contract
from contractforge_snowflake import plan_snowflake_contract, render_snowflake_contract

from tools.platform_parity.contracts import (
    ParityScenario,
    platform_delta,
    platform_parity_scenarios,
    portability_signature,
    scenario_by_name,
)


@dataclass(frozen=True)
class PlatformParityResult:
    scenario: str
    databricks_status: str
    aws_status: str
    snowflake_status: str
    fabric_status: str
    portable_signature_equal: bool
    databricks_artifacts: tuple[str, ...]
    aws_artifacts: tuple[str, ...]
    snowflake_artifacts: tuple[str, ...]
    fabric_artifacts: tuple[str, ...]
    databricks_delta: dict[str, Any]
    aws_delta: dict[str, Any]
    snowflake_delta: dict[str, Any]
    fabric_delta: dict[str, Any]


def parity_result(scenario: ParityScenario) -> PlatformParityResult:
    databricks_contract = scenario.contract_for("databricks")
    aws_contract = scenario.contract_for("aws")
    snowflake_contract = scenario.contract_for("snowflake")
    fabric_contract = scenario.contract_for("fabric")
    databricks_plan = plan_databricks_contract(
        databricks_contract,
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
        environment=scenario.environment_for("databricks"),
    )
    aws_plan = plan_aws_contract(aws_contract, environment=scenario.environment_for("aws"))
    snowflake_plan = plan_snowflake_contract(
        snowflake_contract,
        environment=scenario.environment_for("snowflake"),
    )
    fabric_plan = plan_fabric_contract(
        fabric_contract,
        environment=scenario.environment_for("fabric"),
    )
    databricks_artifacts = render_databricks_contract(
        databricks_contract,
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
        environment=scenario.environment_for("databricks"),
    ).artifacts
    aws_artifacts = render_aws_contract(aws_contract, environment=scenario.environment_for("aws")).artifacts
    snowflake_artifacts = render_snowflake_contract(
        snowflake_contract,
        environment=scenario.environment_for("snowflake"),
    ).artifacts
    fabric_artifacts = render_fabric_contract(
        fabric_contract,
        environment=scenario.environment_for("fabric"),
    ).artifacts
    portable_signature = portability_signature(databricks_contract)
    return PlatformParityResult(
        scenario=scenario.name,
        databricks_status=str(databricks_plan.status),
        aws_status=str(aws_plan.status),
        snowflake_status=str(snowflake_plan.status),
        fabric_status=str(fabric_plan.status),
        portable_signature_equal=(
            portable_signature == portability_signature(aws_contract)
            and portable_signature == portability_signature(snowflake_contract)
            and portable_signature == portability_signature(fabric_contract)
        ),
        databricks_artifacts=tuple(sorted(databricks_artifacts)),
        aws_artifacts=tuple(sorted(aws_artifacts)),
        snowflake_artifacts=tuple(sorted(snowflake_artifacts)),
        fabric_artifacts=tuple(sorted(fabric_artifacts)),
        databricks_delta=platform_delta(databricks_contract),
        aws_delta=platform_delta(aws_contract),
        snowflake_delta=platform_delta(snowflake_contract),
        fabric_delta=platform_delta(fabric_contract),
    )


def build_report(names: tuple[str, ...] = ()) -> dict[str, Any]:
    scenarios = tuple(scenario_by_name(name) for name in names) if names else platform_parity_scenarios()
    results = [parity_result(scenario) for scenario in scenarios]
    return {
        "kind": "contractforge_platform_parity_report",
        "scenario_count": len(results),
        "results": [asdict(result) for result in results],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-platform-parity")
    parser.add_argument("scenario", nargs="*", help="Optional scenario name(s). Defaults to all scenarios.")
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)
    print(json.dumps(build_report(tuple(args.scenario)), indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
