from __future__ import annotations

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.execution import (
    execute_append,
    execute_overwrite,
    render_append_sql,
    render_overwrite_sql,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def _contract(mode: str):
    return semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": mode,
        }
    )


def test_render_append_sql() -> None:
    statement = render_append_sql(target_table="main.bronze.orders", source_view="tmp.orders_src")

    assert statement == "INSERT INTO `main`.`bronze`.`orders`\nSELECT * FROM `tmp`.`orders_src`"


def test_render_overwrite_sql() -> None:
    statement = render_overwrite_sql(target_table="main.bronze.orders", source_view="tmp.orders_src")

    assert statement == "INSERT OVERWRITE TABLE `main`.`bronze`.`orders`\nSELECT * FROM `tmp`.`orders_src`"


def test_execute_append_uses_runner() -> None:
    runner = FakeRunner()

    outcome = execute_append(runner=runner, contract=_contract("scd0_append"), source_view="tmp.orders_src")

    assert outcome.operation == "delta_append"
    assert runner.statements == [outcome.sql]


def test_execute_overwrite_uses_runner() -> None:
    runner = FakeRunner()

    outcome = execute_overwrite(runner=runner, contract=_contract("scd0_overwrite"), source_view="tmp.orders_src")

    assert outcome.operation == "delta_overwrite"
    assert runner.statements == [outcome.sql]


def test_execute_append_rejects_other_modes() -> None:
    with pytest.raises(ValueError, match="only supports scd0_append"):
        execute_append(runner=FakeRunner(), contract=_contract("scd0_overwrite"), source_view="tmp.orders_src")

