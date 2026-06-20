"""Cross-adapter parity scenarios for moving contracts between Databricks, AWS, Snowflake and Fabric."""

from __future__ import annotations

from pathlib import Path

import pytest

from contractforge_aws import plan_aws_contract, render_aws_contract
from contractforge_databricks import plan_databricks_contract, render_databricks_contract
from contractforge_fabric import plan_fabric_contract, render_fabric_contract
from contractforge_snowflake import plan_snowflake_contract, render_snowflake_contract
from tools.platform_parity.contracts import (
    platform_delta,
    platform_parity_scenarios,
    portability_signature,
)
from tools.platform_parity.data import records_for_scenario, write_jsonl_dataset
from tools.platform_parity.report import build_report


@pytest.mark.parametrize("scenario", platform_parity_scenarios(), ids=lambda item: item.name)
def test_platform_parity_contract_intent_is_identical_except_runtime_binding(scenario) -> None:
    databricks_contract = scenario.contract_for("databricks")
    aws_contract = scenario.contract_for("aws")
    snowflake_contract = scenario.contract_for("snowflake")
    fabric_contract = scenario.contract_for("fabric")

    assert portability_signature(databricks_contract) == portability_signature(aws_contract)
    assert portability_signature(databricks_contract) == portability_signature(snowflake_contract)
    assert portability_signature(databricks_contract) == portability_signature(fabric_contract)
    assert platform_delta(databricks_contract) != platform_delta(aws_contract)
    assert platform_delta(databricks_contract) != platform_delta(snowflake_contract)
    assert platform_delta(databricks_contract) != platform_delta(fabric_contract)
    assert platform_delta(aws_contract) != platform_delta(snowflake_contract)
    assert platform_delta(aws_contract) != platform_delta(fabric_contract)
    assert platform_delta(snowflake_contract) != platform_delta(fabric_contract)


@pytest.mark.parametrize("scenario", platform_parity_scenarios(), ids=lambda item: item.name)
def test_same_contract_semantics_plan_on_all_platforms(scenario) -> None:
    databricks_result = plan_databricks_contract(
        scenario.contract_for("databricks"),
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
        environment=scenario.environment_for("databricks"),
    )
    aws_result = plan_aws_contract(
        scenario.contract_for("aws"),
        environment=scenario.environment_for("aws"),
    )
    snowflake_result = plan_snowflake_contract(
        scenario.contract_for("snowflake"),
        environment=scenario.environment_for("snowflake"),
    )
    fabric_result = plan_fabric_contract(
        scenario.contract_for("fabric"),
        environment=scenario.environment_for("fabric"),
    )

    assert databricks_result.status == scenario.expected_databricks_status
    assert aws_result.status == scenario.expected_aws_status
    assert snowflake_result.status == scenario.expected_snowflake_status
    assert fabric_result.status == scenario.expected_fabric_status


@pytest.mark.parametrize("scenario", platform_parity_scenarios(), ids=lambda item: item.name)
def test_same_contract_semantics_render_expected_platform_artifacts(scenario) -> None:
    databricks_artifacts = render_databricks_contract(
        scenario.contract_for("databricks"),
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
        environment=scenario.environment_for("databricks"),
    ).artifacts
    aws_artifacts = render_aws_contract(
        scenario.contract_for("aws"),
        environment=scenario.environment_for("aws"),
    ).artifacts
    snowflake_artifacts = render_snowflake_contract(
        scenario.contract_for("snowflake"),
        environment=scenario.environment_for("snowflake"),
    ).artifacts
    fabric_artifacts = render_fabric_contract(
        scenario.contract_for("fabric"),
        environment=scenario.environment_for("fabric"),
    ).artifacts

    for suffix in scenario.required_databricks_artifact_suffixes:
        assert any(name.endswith(suffix) for name in databricks_artifacts), suffix
    for suffix in scenario.required_aws_artifact_suffixes:
        assert any(name.endswith(suffix) for name in aws_artifacts), suffix
    for suffix in scenario.required_snowflake_artifact_suffixes:
        assert any(name.endswith(suffix) for name in snowflake_artifacts), suffix
    for suffix in scenario.required_fabric_artifact_suffixes:
        assert any(name.endswith(suffix) for name in fabric_artifacts), suffix


def test_platform_parity_report_is_machine_readable() -> None:
    report = build_report()

    assert report["kind"] == "contractforge_platform_parity_report"
    assert report["scenario_count"] == len(platform_parity_scenarios())
    assert all(item["portable_signature_equal"] for item in report["results"])
    assert all("fabric_status" in item for item in report["results"])


@pytest.mark.parametrize("scenario", platform_parity_scenarios(), ids=lambda item: item.name)
def test_platform_parity_scenarios_have_real_smoke_records(scenario) -> None:
    records = records_for_scenario(scenario.name)

    assert records
    assert all(isinstance(record, dict) for record in records)


def test_platform_parity_data_writer_creates_jsonl_directories(tmp_path) -> None:
    written = write_jsonl_dataset(tmp_path)

    assert set(written) == {scenario.name for scenario in platform_parity_scenarios()}
    for path in written.values():
        body = (tmp_path / Path(path).relative_to(tmp_path)).read_text(encoding="utf-8")
        assert body.endswith("\n")
        assert body.splitlines()
