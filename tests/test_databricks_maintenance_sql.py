from contractforge_databricks.maintenance import (
    MaintenancePlan,
    build_control_retention_plan,
    execute_maintenance_plan,
    execute_control_retention_plan,
    render_alter_table_properties_sql,
    render_analyze_sql,
    render_optimize_sql,
    render_vacuum_sql,
)


class FakeRunner:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)


def test_render_optimize_sql_with_zorder() -> None:
    assert render_optimize_sql("main.silver.orders", zorder_columns=("order_id",)) == (
        "OPTIMIZE `main`.`silver`.`orders` ZORDER BY (`order_id`)"
    )


def test_render_vacuum_and_analyze_sql() -> None:
    assert render_vacuum_sql("main.silver.orders", retention_hours=168) == (
        "VACUUM `main`.`silver`.`orders` RETAIN 168 HOURS"
    )
    assert render_analyze_sql("main.silver.orders") == "ANALYZE TABLE `main`.`silver`.`orders` COMPUTE STATISTICS"


def test_render_alter_table_properties_sql() -> None:
    statement = render_alter_table_properties_sql(
        "main.silver.orders",
        {"delta.enableChangeDataFeed": "true"},
    )

    assert statement == (
        "ALTER TABLE `main`.`silver`.`orders` SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')"
    )


def test_execute_maintenance_plan_uses_runner() -> None:
    runner = FakeRunner()
    plan = MaintenancePlan(
        target_table="main.silver.orders",
        optimize=True,
        vacuum_retention_hours=168,
        analyze=True,
        delta_properties={"delta.enableChangeDataFeed": "true"},
    )

    statements = execute_maintenance_plan(runner, plan)

    assert runner.statements == list(statements)
    assert len(statements) == 4


def test_build_control_retention_plan_for_selected_targets() -> None:
    plan = build_control_retention_plan(
        catalog="ops",
        schema="audit",
        retention_days=30,
        vacuum=True,
        targets=("runs", "errors"),
    )

    assert [item["target"] for item in plan] == ["runs", "errors"]
    assert "DELETE FROM `ops`.`audit`.`ctrl_ingestion_runs`" in plan[0]["commands"][0]
    assert "`run_date` < date_sub(current_date(), 30)" in plan[0]["commands"][0]
    assert plan[0]["commands"][1] == "VACUUM `ops`.`audit`.`ctrl_ingestion_runs` RETAIN 168 HOURS"


def test_execute_control_retention_plan_uses_runner() -> None:
    runner = FakeRunner()
    plan = build_control_retention_plan(retention_days=7, targets=("locks",))

    executed = execute_control_retention_plan(runner, plan)

    assert runner.statements == list(executed)
    assert "ctrl_ingestion_locks" in executed[0]


def test_control_retention_plan_includes_cost_signals() -> None:
    plan = build_control_retention_plan(retention_days=14, targets=("cost",))

    assert plan[0]["target"] == "cost"
    assert "ctrl_ingestion_cost" in plan[0]["commands"][0]
    assert "captured_at_utc < current_timestamp() - INTERVAL 14 DAYS" in plan[0]["commands"][0]
