"""Cost-gated AWS smoke runner tests."""

from __future__ import annotations

import json

import pytest

from contractforge_aws.smoke import runner
from contractforge_aws.smoke.minimal import main, smoke_contract
from contractforge_aws.smoke.models import SmokeConfig


def test_minimal_smoke_contract_uses_aws_iceberg_warehouse_extension() -> None:
    config = SmokeConfig(
        account_id="123456789012",
        region="us-east-1",
        bucket="contractforge-smoke",
        role_name="ContractForgeGlueSmokeRole",
        job_name="cf-smoke",
        max_estimated_cost_usd=1.0,
    )

    contract = smoke_contract(config)

    assert contract["source"]["path"] == "s3://contractforge-smoke/data/orders/"
    assert contract["mode"] == "scd0_overwrite"
    assert contract["extensions"]["aws"]["iceberg"]["warehouse"] == "s3://contractforge-smoke/warehouse/"


def test_minimal_smoke_dry_run_outputs_plan_without_aws_calls(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(
        [
            "--account-id",
            "123456789012",
            "--bucket",
            "contractforge-smoke",
            "--max-estimated-cost-usd",
            "1.0",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload["execute"] is False
    assert payload["estimated_max_cost_usd"] == 0.1467
    assert payload["contract"]["target"]["table"] == "orders_overwrite"


def test_minimal_smoke_rejects_cost_ceiling_below_timeout_estimate() -> None:
    with pytest.raises(ValueError, match="below the configured Glue timeout ceiling"):
        main(
            [
                "--account-id",
                "123456789012",
                "--bucket",
                "contractforge-smoke",
                "--max-estimated-cost-usd",
                "0.01",
            ]
        )


def test_minimal_smoke_wait_is_bounded_by_glue_timeout(monkeypatch) -> None:
    config = SmokeConfig(
        account_id="123456789012",
        region="us-east-1",
        bucket="contractforge-smoke",
        role_name="ContractForgeGlueSmokeRole",
        job_name="cf-smoke",
        max_estimated_cost_usd=1.0,
        timeout_minutes=10,
    )
    seen = {}

    def fake_wait(**kwargs):
        seen.update(kwargs)
        return {"state": "SUCCEEDED"}

    monkeypatch.setattr(runner, "wait_aws_glue_job_run", fake_wait)

    assert runner._wait_for_run(config, "jr-1", glue_client="glue") == {"state": "SUCCEEDED"}
    assert seen["job_name"] == "cf-smoke"
    assert seen["run_id"] == "jr-1"
    assert seen["poll_interval_seconds"] == 20.0
    assert seen["max_wait_seconds"] == 900
