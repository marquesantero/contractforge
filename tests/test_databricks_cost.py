import pytest

from contractforge_databricks.cost import CostModel, build_operational_cost_report, render_operational_cost_query


def test_render_operational_cost_query_groups_and_estimates_cost() -> None:
    query = render_operational_cost_query(
        catalog="main",
        schema="ops",
        group_by=["target_table", "layer", "mode", "runtime_type", "source_connector", "criticality"],
        cost_model=CostModel(dbu_per_hour=2.5, currency_per_dbu=0.55, currency="USD"),
        include_failed=False,
    )

    assert "FROM `main`.`ops`.`ctrl_ingestion_runs`" in query
    assert "`target_table`" in query
    assert "`layer`" in query
    assert "`runtime_type`" in query
    assert "`source_connector`" in query
    assert "get_json_object(operations_json, '$.metadata.criticality')" in query
    assert "get_json_object(operations_json, '$.criticality')" in query
    assert "SUM(rows_quarantined) AS rows_quarantined" in query
    assert "SUM(read_seconds) AS read_seconds" in query
    assert "get_json_object(stage_durations_json, '$.schema')" in query
    assert "SUM(preflight_seconds) AS preflight_seconds" in query
    assert "SUM(maintenance_seconds) AS maintenance_seconds" in query
    assert "estimated_cost_per_million_rows" in query
    assert "1.375" in query
    assert "AND status = 'SUCCESS'" in query


def test_render_operational_cost_query_without_cost_model_keeps_cost_null() -> None:
    query = render_operational_cost_query()

    assert "NULL AS estimated_hourly_rate" in query
    assert "estimated_from_evidence_runs" in query


def test_render_operational_cost_query_rejects_invalid_group_by() -> None:
    with pytest.raises(ValueError, match="unknown group_by"):
        render_operational_cost_query(group_by=["target_table", "secret"])


def test_build_operational_cost_report_query_only() -> None:
    report = build_operational_cost_report(cost_model=CostModel(dbu_per_hour=1.0, currency_per_dbu=0.6))

    assert report["status"] == "QUERY_ONLY"
    assert report["limit"] == 100
    assert report["cost_model"]["hourly_rate"] == 0.6
    assert "query" in report
    assert report["rows"] == []


def test_build_operational_cost_report_executes_with_injected_runner() -> None:
    class Row:
        def asDict(self, recursive: bool = True) -> dict[str, object]:
            return {"target_table": "main.silver.orders", "runs": 2}

    class Result:
        def collect(self) -> list[Row]:
            return [Row()]

    class Runner:
        def __init__(self) -> None:
            self.statements: list[str] = []

        def sql(self, statement: str) -> Result:
            self.statements.append(statement)
            return Result()

    runner = Runner()
    report = build_operational_cost_report(query_only=False, runner=runner, limit=7)

    assert report["status"] == "SUCCESS"
    assert report["rows"] == [{"target_table": "main.silver.orders", "runs": 2}]
    assert runner.statements[0].endswith("LIMIT 7")


def test_build_operational_cost_report_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="limit"):
        build_operational_cost_report(query_only=False, runner=object(), limit=0)
