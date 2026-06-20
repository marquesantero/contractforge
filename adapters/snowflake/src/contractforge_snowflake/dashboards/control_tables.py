"""Snowflake dashboard artifacts over canonical ContractForge control tables."""

from __future__ import annotations

import json

from contractforge_core.reporting import DashboardQuery
from contractforge_snowflake.naming import quote_multipart_identifier


def control_dashboard_queries(*, database: str = "CONTRACTFORGE", schema: str = "CF_EVIDENCE", lookback_days: int = 7) -> tuple[DashboardQuery, ...]:
    tables = _tables(database, schema)
    days = int(lookback_days)
    return (
        _q("q01_executive_kpis", "Control Tower", "kpi_card_strip", f"""
            SELECT COUNT(*) AS total_runs,
                   SUM(IFF(status = 'SUCCESS', 1, 0)) AS successful_runs,
                   SUM(IFF(status = 'FAILED', 1, 0)) AS failed_runs,
                   ROUND(100.0 * SUM(IFF(status = 'SUCCESS', 1, 0)) / NULLIF(COUNT(*), 0), 2) AS success_rate_pct,
                   COUNT(DISTINCT target_table) AS active_targets,
                   SUM(COALESCE(rows_read, 0)) AS rows_read,
                   SUM(COALESCE(rows_written, 0)) AS rows_written,
                   SUM(COALESCE(rows_quarantined, 0)) AS rows_quarantined
            FROM {tables['runs']} WHERE run_date >= DATEADD(day, -{days}, CURRENT_DATE())"""),
        _q("q02_status_trend", "Run Health Trend", "stacked_area", f"""
            SELECT run_date, layer, status, COUNT(*) AS runs, SUM(COALESCE(rows_written, 0)) AS rows_written
            FROM {tables['runs']} WHERE run_date >= DATEADD(day, -{days}, CURRENT_DATE())
            GROUP BY run_date, layer, status ORDER BY run_date, layer, status"""),
        _q("q03_latest_target_health", "Target Health Radar", "table_with_conditional_formatting", f"""
            WITH ranked AS (
              SELECT *, ROW_NUMBER() OVER (PARTITION BY target_table ORDER BY run_ts_utc DESC, finished_at_utc DESC) AS rn
              FROM {tables['runs']} WHERE run_date >= DATEADD(day, -{days}, CURRENT_DATE())
            )
            SELECT target_table, layer, mode, status, quality_status, rows_read, rows_written,
                   rows_quarantined, duration_seconds, finished_at_utc, runtime_type, error_message
            FROM ranked WHERE rn = 1 ORDER BY status, target_table"""),
        _q("q04_recent_failures", "Latest Incidents", "table", f"""
            SELECT e.error_ts_utc, e.target_table, r.layer, e.mode, e.error_type, e.error_message, r.run_id
            FROM {tables['errors']} e LEFT JOIN {tables['runs']} r ON e.run_id = r.run_id
            WHERE e.error_date >= DATEADD(day, -{days}, CURRENT_DATE()) ORDER BY e.error_ts_utc DESC"""),
        _q("q05_target_reliability", "Target Reliability Matrix", "heatmap_or_table", f"""
            SELECT target_table, layer, mode, COUNT(*) AS runs,
                   SUM(IFF(status = 'FAILED', 1, 0)) AS failed_runs,
                   ROUND(100.0 * SUM(IFF(status = 'SUCCESS', 1, 0)) / NULLIF(COUNT(*), 0), 2) AS success_rate_pct
            FROM {tables['runs']} WHERE run_date >= DATEADD(day, -{days}, CURRENT_DATE())
            GROUP BY target_table, layer, mode ORDER BY failed_runs DESC, success_rate_pct ASC"""),
        _q("q06_sla_freshness", "Freshness SLA Board", "table_with_status_colors", f"""
            WITH latest_success AS (
              SELECT target_table, MAX(finished_at_utc) AS last_success_at_utc FROM {tables['runs']} WHERE status = 'SUCCESS' GROUP BY target_table
            ), ops AS (
              SELECT *, ROW_NUMBER() OVER (PARTITION BY target_table ORDER BY recorded_at_utc DESC) AS rn FROM {tables['operations']}
            )
            SELECT o.target_table, o.criticality, o.expected_frequency, o.freshness_sla_minutes, s.last_success_at_utc,
                   CASE WHEN s.last_success_at_utc IS NULL THEN 'NO_SUCCESS'
                        WHEN o.freshness_sla_minutes IS NULL THEN 'NO_SLA'
                        WHEN DATEDIFF(minute, s.last_success_at_utc, CURRENT_TIMESTAMP()) > o.freshness_sla_minutes THEN 'BREACHED'
                        ELSE 'OK' END AS freshness_status, o.runbook_url
            FROM ops o LEFT JOIN latest_success s ON o.target_table = s.target_table WHERE o.rn = 1"""),
        _q("q07_failure_taxonomy", "Failure Taxonomy", "horizontal_bar", f"""
            SELECT COALESCE(error_type, 'unknown') AS error_type, COUNT(*) AS failures, COUNT(DISTINCT target_table) AS affected_targets
            FROM {tables['errors']} WHERE error_date >= DATEADD(day, -{days}, CURRENT_DATE())
            GROUP BY COALESCE(error_type, 'unknown') ORDER BY failures DESC"""),
        _q("q08_quality_summary", "Quality Outcomes", "stacked_bar", f"SELECT status, severity, COUNT(*) AS rule_evaluations, SUM(failed_count) AS failed_count FROM {tables['quality']} GROUP BY status, severity"),
        _q("q09_quarantine_hotspots", "Quarantine Drilldown", "table", f"SELECT target_table, rule_name, COUNT(*) AS quarantined_records FROM {tables['quarantine']} GROUP BY target_table, rule_name ORDER BY quarantined_records DESC"),
        _q("q10_cost_signals", "Cost Signals", "table", f"SELECT run_id, target_table, signal_name, signal_value, captured_at_utc FROM {tables['cost']} WHERE captured_at_utc >= DATEADD(day, -{days}, CURRENT_TIMESTAMP()) ORDER BY captured_at_utc DESC"),
        _q("q11_state_watermarks", "State and Watermarks", "table", f"SELECT target_table, watermark_column, watermark_value, last_status, last_success_at_utc, last_run_id, last_updated_at_utc FROM {tables['state']} ORDER BY last_updated_at_utc DESC"),
        _q("q12_governance_artifacts", "Governance Artifacts", "table", f"""
            SELECT COALESCE(s.target_table, a.target_table, x.target_table) AS target_table,
                   s.schema_change_events, a.annotation_events, x.access_events
            FROM (SELECT target_table, COUNT(*) AS schema_change_events FROM {tables['schema_changes']} GROUP BY target_table) s
            FULL OUTER JOIN (SELECT target_table, COUNT(*) AS annotation_events FROM {tables['annotations']} GROUP BY target_table) a ON s.target_table = a.target_table
            FULL OUTER JOIN (SELECT target_table, COUNT(*) AS access_events FROM {tables['access']} GROUP BY target_table) x ON COALESCE(s.target_table, a.target_table) = x.target_table"""),
    )


def render_control_dashboard_sql(*, database: str = "CONTRACTFORGE", schema: str = "CF_EVIDENCE", lookback_days: int = 7) -> str:
    blocks = ["-- ContractForge Operations Command Center", "-- Snowflake dashboard queries"]
    for query in control_dashboard_queries(database=database, schema=schema, lookback_days=lookback_days):
        blocks.extend(["", f"-- {query.name}", f"-- Visualization: {query.visualization}", _clean_sql(query.sql) + ";"])
    return "\n".join(blocks) + "\n"


def control_dashboard_blueprint(*, database: str = "CONTRACTFORGE", schema: str = "CF_EVIDENCE", lookback_days: int = 7) -> dict[str, object]:
    queries = control_dashboard_queries(database=database, schema=schema, lookback_days=lookback_days)
    return {
        "title": "ContractForge Operations Command Center",
        "data_source": {"database": database, "schema": schema, "lookback_days": lookback_days},
        "pages": {
            "overview": ["q01_executive_kpis", "q02_status_trend", "q03_latest_target_health", "q04_recent_failures"],
            "reliability": ["q06_sla_freshness", "q05_target_reliability", "q07_failure_taxonomy"],
            "quality": ["q08_quality_summary", "q09_quarantine_hotspots"],
            "cost_state": ["q10_cost_signals", "q11_state_watermarks"],
            "governance": ["q12_governance_artifacts"],
        },
        "queries": [query.__dict__ for query in queries],
    }


def render_control_dashboard_artifacts(*, database: str = "CONTRACTFORGE", schema: str = "CF_EVIDENCE", lookback_days: int = 7) -> dict[str, str]:
    return {
        "control_tables_dashboard.sql": render_control_dashboard_sql(database=database, schema=schema, lookback_days=lookback_days),
        "control_tables_dashboard_blueprint.json": json.dumps(
            control_dashboard_blueprint(database=database, schema=schema, lookback_days=lookback_days),
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }


def _tables(database: str, schema: str) -> dict[str, str]:
    names = (
        "runs",
        "errors",
        "quality",
        "quarantine",
        "schema_changes",
        "annotations",
        "access",
        "operations",
        "cost",
        "state",
    )
    table_names = {
        "runs": "ctrl_ingestion_runs",
        "errors": "ctrl_ingestion_errors",
        "quality": "ctrl_ingestion_quality",
        "quarantine": "ctrl_ingestion_quarantine",
        "schema_changes": "ctrl_ingestion_schema_changes",
        "annotations": "ctrl_ingestion_annotations",
        "access": "ctrl_ingestion_access",
        "operations": "ctrl_ingestion_operations",
        "cost": "ctrl_ingestion_cost",
        "state": "ctrl_ingestion_state",
    }
    return {name: quote_multipart_identifier(f"{database}.{schema}.{table_names[name]}") for name in names}


def _q(name: str, title: str, visualization: str, sql: str) -> DashboardQuery:
    return DashboardQuery(name=name, title=title, visualization=visualization, sql=_clean_sql(sql))


def _clean_sql(sql: str) -> str:
    lines = [line.strip() for line in sql.strip().splitlines()]
    return "\n".join(line for line in lines if line)
