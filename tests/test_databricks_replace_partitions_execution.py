from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.execution import execute_replace_partitions, render_replace_partitions_sql


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_render_replace_partitions_sql_uses_databricks_replace_where() -> None:
    statement = render_replace_partitions_sql(
        target_table="main.silver.orders",
        source_view="prepared_orders",
        predicate="`dt` IN ('2026-01-01')",
    )

    assert statement == (
        "INSERT INTO TABLE `main`.`silver`.`orders` BY NAME\n"
        "REPLACE WHERE `dt` IN ('2026-01-01')\n"
        "SELECT * FROM `prepared_orders`"
    )


def test_execute_replace_partitions_uses_injected_runner() -> None:
    runner = FakeRunner()
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "scd1_upsert",
            "merge_keys": ["order_id"],
        }
    )

    outcome = execute_replace_partitions(
        runner=runner,
        contract=contract,
        source_view="prepared_orders",
        predicate="`dt` IN ('2026-01-01')",
    )

    assert outcome.operation == "delta_replace_partitions"
    assert runner.statements == [outcome.sql]
