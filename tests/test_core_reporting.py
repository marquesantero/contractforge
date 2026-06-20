from contractforge_core.reporting import DashboardQuery


def test_core_dashboard_query_model() -> None:
    query = DashboardQuery(name="q01", title="Overview", visualization="table", sql="select 1")

    assert query.name == "q01"
    assert query.visualization == "table"
    assert query.sql == "select 1"
