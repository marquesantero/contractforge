import json

import pytest

from contractforge_snowflake import cli as cli_module
from contractforge_snowflake.cli import main as snowflake_cli_main
from contractforge_snowflake.smoke.models import SnowflakeSmokeConfig, failure_contracts
from contractforge_snowflake.smoke.runner import execute_failure_smoke


def test_snowflake_failure_smoke_contracts_cover_missing_source_and_quality_abort() -> None:
    config = SnowflakeSmokeConfig(database="DB")

    contracts = failure_contracts(config)

    assert list(contracts) == ["missing_source", "quality_abort", "strict_schema"]
    assert contracts["missing_source"]["source"]["table"] == "DB.PUBLIC.CF_SMOKE_MISSING_SOURCE"
    assert contracts["quality_abort"]["quality_rules"] == {"min_rows": 10}
    assert contracts["strict_schema"]["schema_policy"] == "strict"


def test_snowflake_cli_failure_smoke_dry_run_does_not_connect(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli_module, "_connect", lambda _options: pytest.fail("dry-run should not connect"))

    exit_code = snowflake_cli_main(["smoke-failure-paths", "--database", "DB", "--schema", "PUBLIC"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["status"] == "DRY_RUN"
    assert set(output["contracts"]) == {"missing_source", "quality_abort", "strict_schema"}
    assert output["environment"]["evidence"]["create_database"] is False


def test_snowflake_cli_failure_smoke_execute_requires_cleanup(tmp_path) -> None:
    options = tmp_path / "connect.yaml"
    options.write_text("account: IW11590\nuser: CFINGESTSVC\n", encoding="utf-8")

    with pytest.raises(ValueError, match="--execute-cleanup"):
        snowflake_cli_main(["smoke-failure-paths", "--connect-options", str(options), "--execute"])


def test_snowflake_failure_smoke_runner_treats_expected_failures_as_success(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contractforge_snowflake.smoke import runner as runner_module

    session = _SmokeSession()
    config = SnowflakeSmokeConfig(database="DB", output_dir=tmp_path)

    def fake_run_snowflake_contract(**kwargs):
        contract_uri = str(kwargs["contract_uri"])
        if "missing_source" in contract_uri:
            raise RuntimeError("Object does not exist: token=secret")
        if "quality_abort" in contract_uri:
            raise RuntimeError("Snowflake quality rule failed: min_rows")
        if "strict_schema" in contract_uri:
            raise RuntimeError("Snowflake strict schema policy violation")
        return {"status": "SUCCESS"}

    monkeypatch.setattr(runner_module, "run_snowflake_contract", fake_run_snowflake_contract)

    summary = execute_failure_smoke(config, session=session, execute_cleanup=True)

    assert summary["status"] == "SUCCESS"
    assert summary["runs"]["missing_source"]["ok"] is True
    assert "token=***REDACTED***" in summary["runs"]["missing_source"]["error"]
    assert "secret" not in summary["runs"]["missing_source"]["error"]
    assert summary["runs"]["quality_abort"]["ok"] is True
    assert summary["runs"]["strict_schema"]["ok"] is True
    assert (tmp_path / "summary.json").exists()


class _SmokeSession:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def sql(self, command: str):
        self.commands.append(command)
        rows = [(2,)] if command.startswith("SELECT COUNT(*)") else []
        return _SmokeResult(rows)


class _SmokeResult:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows
