"""Databricks dashboard artifacts over ContractForge control tables."""

from __future__ import annotations

from contractforge_core.reporting import DashboardQuery
from contractforge_databricks.sql import quote_table_name


def control_dashboard_queries(*, catalog: str = "main", schema: str = "ops", lookback_days: int = 7) -> tuple[DashboardQuery, ...]:
    t = _tables(catalog, schema)
    days = int(lookback_days)
    return (
        _q("q01_executive_kpis", "Control Tower", "kpi_card_strip", f"""
            SELECT count(*) AS total_runs,
                   sum(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) AS successful_runs,
                   sum(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_runs,
                   round(100.0 * sum(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) / nullif(count(*), 0), 2) AS success_rate_pct,
                   count(DISTINCT target_table) AS active_targets,
                   sum(coalesce(rows_read, 0)) AS rows_read,
                   sum(coalesce(rows_written, 0)) AS rows_written,
                   sum(coalesce(rows_quarantined, 0)) AS rows_quarantined
            FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days})"""),
        _q("q02_status_trend", "Run Health Trend", "stacked_area", f"""
            SELECT run_date, layer, status, count(*) AS runs, sum(coalesce(rows_written, 0)) AS rows_written
            FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days})
            GROUP BY run_date, layer, status ORDER BY run_date, layer, status"""),
        _q("q03_latest_target_health", "Target Health Radar", "table_with_conditional_formatting", f"""
            WITH ranked AS (
              SELECT *, row_number() OVER (PARTITION BY target_table ORDER BY run_ts_utc DESC, finished_at_utc DESC) AS rn
              FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days})
            )
            SELECT target_table, layer, mode, status, quality_status, rows_read, rows_written,
                   rows_quarantined, duration_seconds, finished_at_utc, runtime_type, error_message
            FROM ranked WHERE rn = 1 ORDER BY status, target_table"""),
        _q("q04_recent_failures", "Latest Incidents", "table", f"""
            SELECT e.error_ts_utc, e.target_table, r.layer, e.mode, e.error_type, e.error_message, r.run_id
            FROM {t['errors']} e LEFT JOIN {t['runs']} r ON e.run_id = r.run_id
            WHERE e.error_date >= date_sub(current_date(), {days}) ORDER BY e.error_ts_utc DESC"""),
        _q("q05_target_reliability", "Target Reliability Matrix", "heatmap_or_table", f"""
            SELECT target_table, layer, mode, count(*) AS runs,
                   sum(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed_runs,
                   round(100.0 * sum(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) / nullif(count(*), 0), 2) AS success_rate_pct
            FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days})
            GROUP BY target_table, layer, mode ORDER BY failed_runs DESC, success_rate_pct ASC"""),
        _q("q06_sla_freshness", "Freshness SLA Board", "table_with_status_colors", f"""
            WITH latest_success AS (
              SELECT target_table, max(finished_at_utc) AS last_success_at_utc FROM {t['runs']} WHERE status = 'SUCCESS' GROUP BY target_table
            ), ops AS (
              SELECT *, row_number() OVER (PARTITION BY target_table ORDER BY recorded_at_utc DESC) AS rn FROM {t['operations']}
            )
            SELECT o.target_table, o.criticality, o.expected_frequency, o.freshness_sla_minutes, s.last_success_at_utc,
                   CASE WHEN s.last_success_at_utc IS NULL THEN 'NO_SUCCESS'
                        WHEN o.freshness_sla_minutes IS NULL THEN 'NO_SLA'
                        WHEN (unix_timestamp(current_timestamp()) - unix_timestamp(s.last_success_at_utc)) / 60 > o.freshness_sla_minutes THEN 'BREACHED'
                        ELSE 'OK' END AS freshness_status, o.runbook_url
            FROM ops o LEFT JOIN latest_success s ON o.target_table = s.target_table WHERE o.rn = 1"""),
        _q("q07_failure_taxonomy", "Failure Taxonomy", "horizontal_bar", f"""
            SELECT coalesce(error_type, 'unknown') AS error_type, count(*) AS failures, count(DISTINCT target_table) AS affected_targets
            FROM {t['errors']} WHERE error_date >= date_sub(current_date(), {days})
            GROUP BY coalesce(error_type, 'unknown') ORDER BY failures DESC"""),
        _q("q08_error_drilldown", "Error Drilldown", "table", f"SELECT * FROM {t['errors']} WHERE error_date >= date_sub(current_date(), {days}) ORDER BY error_ts_utc DESC"),
        _q("q09_duration_percentiles", "Duration Percentiles by Mode", "grouped_bar", f"""
            SELECT layer, mode, count(*) AS successful_runs, round(avg(duration_seconds), 2) AS avg_duration_seconds,
                   round(percentile_approx(duration_seconds, 0.95), 2) AS p95_duration_seconds
            FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days}) AND status = 'SUCCESS'
            GROUP BY layer, mode ORDER BY p95_duration_seconds DESC"""),
        _q("q10_stage_duration_breakdown", "Stage Bottlenecks", "stacked_bar", f"SELECT run_id, target_table, stage_durations_json FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days}) AND status = 'SUCCESS'"),
        _q("q11_throughput_by_target", "Throughput by Target", "scatter_or_table", f"""
            SELECT target_table, layer, mode, sum(rows_written) AS rows_written,
                   round(sum(rows_written) / nullif(sum(duration_seconds), 0), 2) AS rows_written_per_second
            FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days}) AND status = 'SUCCESS'
            GROUP BY target_table, layer, mode ORDER BY rows_written_per_second ASC NULLS LAST"""),
        _q("q12_slowest_runs", "Slowest Successful Runs", "table", f"SELECT run_ts_utc, target_table, mode, duration_seconds, rows_written, run_id FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days}) AND status = 'SUCCESS' ORDER BY duration_seconds DESC LIMIT 50"),
        _q("q13_quality_summary", "Quality Outcomes", "stacked_bar", f"SELECT status, severity, count(*) AS rule_evaluations, sum(failed_count) AS failed_count FROM {t['quality']} GROUP BY status, severity"),
        _q("q14_quality_rules_hotspots", "Rule Hotspots", "horizontal_bar", f"SELECT target_table, rule_name, status, sum(failed_count) AS failed_count FROM {t['quality']} GROUP BY target_table, rule_name, status ORDER BY failed_count DESC"),
        _q("q15_quarantine_hotspots", "Quarantine Drilldown", "table", f"SELECT target_table, rule_name, count(*) AS quarantined_records FROM {t['quarantine']} GROUP BY target_table, rule_name ORDER BY quarantined_records DESC"),
        _q("q16_effective_rows", "Useful Rows vs Quarantine", "stacked_bar", f"SELECT target_table, sum(rows_read) AS rows_read, sum(rows_written) AS rows_written, sum(rows_quarantined) AS rows_quarantined FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days}) GROUP BY target_table"),
        _q("q17_stream_kpis", "Stream Control Tower", "kpi_card_strip", f"SELECT count(*) AS stream_runs, sum(batches_processed) AS batches_processed, sum(total_rows_written) AS total_rows_written FROM {t['streams']} WHERE started_at_utc >= current_timestamp() - INTERVAL {days} DAYS"),
        _q("q18_stream_runs", "Stream Runs", "table", f"SELECT stream_run_id, target_table, source_type, trigger, status, batches_processed, total_rows_written, started_at_utc, ended_at_utc FROM {t['streams']} ORDER BY started_at_utc DESC"),
        _q("q19_stream_child_reconciliation", "Parent/Child Reconciliation", "table_with_status_colors", f"SELECT stream_run_id, target_table, status, batches_processed, total_rows_read, total_rows_written FROM {t['streams']} ORDER BY started_at_utc DESC"),
        _q("q20_connector_runtime_matrix", "Connector and Runtime Matrix", "grouped_bar_or_heatmap", f"SELECT source_connector, source_provider, source_format, runtime_type, count(*) AS runs FROM {t['runs']} WHERE run_date >= date_sub(current_date(), {days}) GROUP BY source_connector, source_provider, source_format, runtime_type"),
        _q("q21_operations_coverage", "Operations Coverage", "table_with_completeness_score", f"SELECT target_table, criticality, expected_frequency, freshness_sla_minutes, runbook_url, status FROM {t['operations']}"),
        _q("q22_governance_artifacts", "Governance Artifacts", "table", f"""
            SELECT coalesce(s.target_table, a.target_table, x.target_table) AS target_table,
                   s.schema_change_events, a.annotation_events, x.access_events
            FROM (SELECT target_table, count(*) AS schema_change_events FROM {t['schema_changes']} GROUP BY target_table) s
            FULL OUTER JOIN (SELECT target_table, count(*) AS annotation_events FROM {t['annotations']} GROUP BY target_table) a ON s.target_table = a.target_table
            FULL OUTER JOIN (SELECT target_table, count(*) AS access_events FROM {t['access']} GROUP BY target_table) x ON coalesce(s.target_table, a.target_table) = x.target_table"""),
    )


def render_control_dashboard_sql(*, catalog: str = "main", schema: str = "ops", lookback_days: int = 7) -> str:
    blocks = ["-- ContractForge Operations Command Center", "-- Databricks SQL dashboard queries"]
    for query in control_dashboard_queries(catalog=catalog, schema=schema, lookback_days=lookback_days):
        blocks.extend(["", f"-- {query.name}", f"-- Visualization: {query.visualization}", _clean_sql(query.sql) + ";"])
    return "\n".join(blocks) + "\n"


def control_dashboard_blueprint(*, catalog: str = "main", schema: str = "ops", lookback_days: int = 7) -> dict[str, object]:
    queries = control_dashboard_queries(catalog=catalog, schema=schema, lookback_days=lookback_days)
    return {
        "title": "ContractForge Operations Command Center",
        "data_source": {"catalog": catalog, "schema": schema, "lookback_days": lookback_days},
        "pages": {
            "overview": ["q01_executive_kpis", "q02_status_trend", "q03_latest_target_health", "q04_recent_failures"],
            "reliability": ["q06_sla_freshness", "q05_target_reliability", "q07_failure_taxonomy", "q08_error_drilldown"],
            "performance": ["q09_duration_percentiles", "q10_stage_duration_breakdown", "q11_throughput_by_target", "q12_slowest_runs"],
            "quality": ["q13_quality_summary", "q14_quality_rules_hotspots", "q16_effective_rows", "q15_quarantine_hotspots"],
            "streaming": ["q17_stream_kpis", "q19_stream_child_reconciliation", "q18_stream_runs"],
            "connectors_governance": ["q20_connector_runtime_matrix", "q21_operations_coverage", "q22_governance_artifacts"],
        },
        "queries": [query.__dict__ for query in queries],
    }


def render_control_dashboard_artifacts(*, catalog: str = "main", schema: str = "ops", lookback_days: int = 7) -> dict[str, str]:
    import json

    return {
        "control_tables_dashboard.sql": render_control_dashboard_sql(catalog=catalog, schema=schema, lookback_days=lookback_days),
        "control_tables_dashboard_blueprint.json": json.dumps(
            control_dashboard_blueprint(catalog=catalog, schema=schema, lookback_days=lookback_days),
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }


def _tables(catalog: str, schema: str) -> dict[str, str]:
    return {
        "runs": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_runs"),
        "errors": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_errors"),
        "quality": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_quality"),
        "quarantine": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_quarantine"),
        "schema_changes": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_schema_changes"),
        "streams": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_streams"),
        "annotations": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_annotations"),
        "access": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_access"),
        "operations": quote_table_name(f"{catalog}.{schema}.ctrl_ingestion_operations"),
    }


def _q(name: str, title: str, visualization: str, sql: str) -> DashboardQuery:
    return DashboardQuery(name=name, title=title, visualization=visualization, sql=_clean_sql(sql))


def _clean_sql(sql: str) -> str:
    lines = [line.strip() for line in sql.strip().splitlines()]
    return "\n".join(line for line in lines if line)
