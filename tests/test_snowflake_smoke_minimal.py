import json

import pytest

from contractforge_snowflake import cli as cli_module
from contractforge_snowflake.cli import main as snowflake_cli_main
from contractforge_snowflake.smoke.models import SnowflakeSmokeConfig, cleanup_commands, setup_commands, smoke_contracts
from contractforge_snowflake.smoke.runner import execute_smoke


def test_snowflake_minimal_smoke_contracts_are_deterministic() -> None:
    config = SnowflakeSmokeConfig(
        database="DB",
        source_schema="RAW",
        target_schema="TGT",
        evidence_schema="AUDIT",
        table_prefix="CF_SMOKE_TEST",
    )

    first = smoke_contracts(config)
    second = smoke_contracts(config)

    assert first == second
    assert list(first) == ["orders_append", "orders_overwrite", "orders_quarantine", "customers_upsert", "customers_hash_diff"]
    assert first["orders_append"]["source"]["table"] == "DB.RAW.CF_SMOKE_TEST_ORDERS_SOURCE"
    assert first["orders_append"]["target"] == {
        "catalog": "DB",
        "schema": "TGT",
        "table": "CF_SMOKE_TEST_ORDERS_APPEND",
    }
    assert first["orders_overwrite"]["filter_expression"] == "AMOUNT >= 10"
    assert first["orders_overwrite"]["transform"]["derive"] == {
        "AMOUNT_BAND": "CASE WHEN AMOUNT >= 20 THEN 'HIGH' ELSE 'LOW' END"
    }
    assert first["orders_quarantine"]["quality_rules"] == {"not_null": ["ORDER_ID"]}
    assert first["customers_upsert"]["transform"]["deduplicate"]["keys"] == ["CUSTOMER_ID"]


def test_snowflake_minimal_smoke_setup_is_scoped_to_configured_schema_and_prefix() -> None:
    config = SnowflakeSmokeConfig(
        database="DB",
        source_schema="RAW",
        target_schema="TGT",
        evidence_schema="AUDIT",
        table_prefix="CF_SMOKE_TEST",
    )

    setup_sql = "\n".join(setup_commands(config))
    cleanup_sql = "\n".join(cleanup_commands(config))

    assert "CREATE DATABASE" not in setup_sql
    assert 'CREATE SCHEMA IF NOT EXISTS "DB"."RAW"' in setup_sql
    assert '"DB"."RAW"."CF_SMOKE_TEST_ORDERS_SOURCE"' in setup_sql
    assert '"DB"."TGT"."CF_SMOKE_TEST_CUSTOMERS_CURRENT"' in setup_sql
    assert 'DROP TABLE IF EXISTS "DB"."TGT"."CF_SMOKE_TEST_ORDERS_APPEND"' in cleanup_sql
    assert 'DROP TABLE IF EXISTS "DB"."AUDIT"."ctrl_ingestion_runs"' in cleanup_sql


def test_snowflake_minimal_smoke_rejects_unscoped_prefix() -> None:
    with pytest.raises(ValueError, match="table_prefix must start with CF_SMOKE"):
        SnowflakeSmokeConfig(table_prefix="ORDERS")


def test_snowflake_cli_smoke_minimal_dry_run_does_not_connect(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli_module, "_connect", lambda _options: pytest.fail("dry-run should not connect"))

    exit_code = snowflake_cli_main(["smoke-minimal", "--database", "DB", "--schema", "PUBLIC"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "DRY_RUN"
    assert output["config"]["database"] == "DB"
    assert output["environment"]["evidence"]["create_database"] is False
    assert output["environment"]["evidence"]["create_schema"] is False
    assert output["bootstrap_skips"] == [
        'CREATE DATABASE IF NOT EXISTS "DB"',
        'CREATE SCHEMA IF NOT EXISTS "DB"."PUBLIC"',
    ]
    assert output["contracts"]["orders_append"]["target"]["table"] == "CF_SMOKE_ORDERS_APPEND"


def test_snowflake_cli_smoke_minimal_execute_requires_cleanup(tmp_path) -> None:
    options = tmp_path / "connect.yaml"
    options.write_text("account: TEST_ACCOUNT\nuser: CFINGESTSVC\n", encoding="utf-8")

    with pytest.raises(ValueError, match="--execute-cleanup"):
        snowflake_cli_main(["smoke-minimal", "--connect-options", str(options), "--execute"])


def test_snowflake_minimal_smoke_runner_writes_summary(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contractforge_snowflake.smoke import runner as runner_module

    session = _SmokeSession()
    config = SnowflakeSmokeConfig(database="DB", output_dir=tmp_path)

    def fake_run_snowflake_contract(**kwargs):
        assert kwargs["session"] is session
        return {"status": "SUCCESS", "planning_status": "SUPPORTED", "run_id": "run-123"}

    monkeypatch.setattr(runner_module, "run_snowflake_contract", fake_run_snowflake_contract)

    summary = execute_smoke(config, session=session, execute_cleanup=True)

    persisted = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "SUCCESS"
    assert persisted["status"] == "SUCCESS"
    assert persisted["bootstrap_skips"] == [
        'CREATE DATABASE IF NOT EXISTS "DB"',
        'CREATE SCHEMA IF NOT EXISTS "DB"."PUBLIC"',
    ]
    assert set(summary["runs"]) == {"orders_append", "orders_overwrite", "orders_quarantine", "customers_upsert", "customers_hash_diff"}
    assert any(command.startswith("DROP TABLE IF EXISTS") for command in session.commands)
    last_count_index = max(index for index, command in enumerate(session.commands) if command.startswith("SELECT COUNT(*)"))
    last_drop_index = max(index for index, command in enumerate(session.commands) if command.startswith("DROP TABLE IF EXISTS"))
    assert last_drop_index > last_count_index


class _SmokeSession:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def sql(self, command: str):
        self.commands.append(command)
        rows = [(0,)] if command.startswith("SELECT COUNT(*)") else []
        return _SmokeResult(rows)


class _SmokeResult:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows

