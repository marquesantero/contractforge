from contractforge_databricks.dashboards import (
    control_dashboard_blueprint,
    control_dashboard_queries,
    render_control_dashboard_artifacts,
    render_control_dashboard_sql,
)


def test_control_dashboard_exposes_query_catalog() -> None:
    queries = control_dashboard_queries(catalog="ops", schema="audit", lookback_days=14)
    names = {query.name for query in queries}

    assert len(queries) == 22
    assert "q01_executive_kpis" in names
    assert "q22_governance_artifacts" in names
    assert all(query.sql for query in queries)


def test_control_dashboard_sql_renders_databricks_control_tables() -> None:
    sql = render_control_dashboard_sql(catalog="ops", schema="audit", lookback_days=14)

    assert "-- q01_executive_kpis" in sql
    assert "-- q22_governance_artifacts" in sql
    assert "`ops`.`audit`.`ctrl_ingestion_runs`" in sql
    assert "`ops`.`audit`.`ctrl_ingestion_access`" in sql
    assert "date_sub(current_date(), 14)" in sql


def test_control_dashboard_blueprint_groups_pages() -> None:
    blueprint = control_dashboard_blueprint(catalog="ops", schema="audit", lookback_days=14)

    assert blueprint["title"] == "ContractForge Operations Command Center"
    assert blueprint["data_source"] == {"catalog": "ops", "schema": "audit", "lookback_days": 14}
    assert "q17_stream_kpis" in blueprint["pages"]["streaming"]
    assert "q22_governance_artifacts" in blueprint["pages"]["connectors_governance"]


def test_control_dashboard_artifacts_include_sql_and_blueprint() -> None:
    artifacts = render_control_dashboard_artifacts()

    assert set(artifacts) == {"control_tables_dashboard.sql", "control_tables_dashboard_blueprint.json"}
    assert "ContractForge Operations Command Center" in artifacts["control_tables_dashboard_blueprint.json"]
