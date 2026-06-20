from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.operations import record_operations_contract


class RecordingRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


class FailingRunner:
    def sql(self, statement: str) -> None:
        raise RuntimeError("warehouse unavailable")


def test_record_operations_contract_writes_to_environment_evidence_table() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd0_append",
            "operations": {
                "operations": {
                    "criticality": "high",
                    "expected_frequency": "daily",
                    "alert_on_failure": True,
                    "owners": ["sales-ops"],
                },
            },
        }
    )
    runner = RecordingRunner()
    environment = DatabricksEnvironment(evidence_catalog="audit", evidence_schema="ops")

    result = record_operations_contract(
        runner=runner,
        contract=contract,
        environment=environment,
        run_id="run-42",
    )

    assert result.status == "RECORDED"
    assert len(runner.statements) == 1
    assert "INSERT INTO `audit`.`ops`.`ctrl_ingestion_operations`" in runner.statements[0]
    assert "'run-42'" in runner.statements[0]
    assert "'RECORDED'" in runner.statements[0]


def test_record_operations_contract_reports_runner_failure() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd0_append",
            "operations": {"operations": {"criticality": "medium"}},
        }
    )

    result = record_operations_contract(runner=FailingRunner(), contract=contract)

    assert result.status == "FAILED"
    assert result.sql is not None
    assert result.error == "warehouse unavailable"


def test_record_operations_contract_ignores_contract_without_operations_metadata() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd0_append",
        }
    )
    runner = RecordingRunner()

    result = record_operations_contract(runner=runner, contract=contract)

    assert result.status == "NOT_CONFIGURED"
    assert runner.statements == []
