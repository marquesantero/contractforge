from contractforge_ai.observability import analyze_control_tables, load_control_table_evidence


def test_analyze_control_tables_summarizes_operational_risk():
    evidence = {
        "scope": {"target_table": "main.silver.orders", "window": "last 7 days"},
        "runs": [
            {"run_id": "1", "status": "SUCCESS", "target_table": "main.silver.orders", "duration_seconds": 10, "rows_written": 100},
            {"run_id": "2", "status": "FAILED", "target_table": "main.silver.orders", "duration_seconds": 12, "rows_written": 0},
            {"run_id": "3", "status": "FAILED", "target_table": "main.silver.orders", "duration_seconds": 40, "rows_written": 0},
        ],
        "errors": [{"run_id": "2", "error_message": "Permission denied while reading source"}],
        "quality": [{"run_id": "3", "rule_name": "not_null", "status": "FAILED", "failed_count": 5}],
        "schema_changes": [{"run_id": "3", "change_type": "ADD_COLUMN"}],
    }

    result = analyze_control_tables(evidence)

    assert result.status == "FAIL"
    assert result.risk == "high"
    assert result.metrics["runs_total"] == 3
    assert result.metrics["runs_failed"] == 2
    assert result.metrics["error_categories"] == {"auth": 1}
    assert any(finding.code == "observability.failure_rate.high" for finding in result.findings)
    assert any(finding.code == "observability.quality.failures" for finding in result.findings)
    assert any(finding.code == "observability.schema.drift" for finding in result.findings)
    assert result.follow_up_queries
    assert result.traceability.evidence[0].value["runs"] == 3
    assert result.traceability.evidence[0].source == "evidence_model"


def test_analyze_control_tables_detects_duration_outlier():
    evidence = {
        "runs": [
            {"run_id": "1", "status": "SUCCESS", "target_table": "t", "duration_seconds": 10},
            {"run_id": "2", "status": "SUCCESS", "target_table": "t", "duration_seconds": 11},
            {"run_id": "3", "status": "SUCCESS", "target_table": "t", "duration_seconds": 40},
        ]
    }

    result = analyze_control_tables(evidence)

    assert any(finding.code == "observability.duration.outlier" for finding in result.findings)


def test_analyze_control_tables_detects_partial_collection():
    result = analyze_control_tables({"collection_errors": [{"kind": "quality", "error_message": "missing table"}]})

    assert result.status == "WARN"
    assert any(finding.code == "observability.collection.partial" for finding in result.findings)


def test_load_control_table_evidence_redacts_secrets():
    package = load_control_table_evidence(
        {
            "runs": [{"run_id": "1", "source_options": {"password": "secret"}}],
        }
    )

    assert package.runs[0]["source_options"]["password"] == "[REDACTED]"


def test_analyze_control_tables_detects_recurring_failure_clusters_and_network_errors():
    evidence = {
        "runs": [
            {
                "run_id": "1",
                "status": "FAILED",
                "target_table": "main.bronze.orders",
                "source_connector": "s3",
                "runtime_type": "serverless",
            },
            {
                "run_id": "2",
                "status": "FAILED",
                "target_table": "main.bronze.orders",
                "source_connector": "s3",
                "runtime_type": "serverless",
            },
            {
                "run_id": "3",
                "status": "FAILED",
                "target_table": "main.bronze.orders",
                "source_connector": "s3",
                "runtime_type": "classic",
            },
        ],
        "errors": [
            {"run_id": "1", "error_message": "Temporary failure in DNS resolution"},
            {"run_id": "2", "error_message": "Network egress timeout"},
        ],
    }

    result = analyze_control_tables(evidence)

    assert result.metrics["failure_clusters"]["main.bronze.orders|s3|serverless"] == 2
    assert result.metrics["runtimes"] == ["classic", "serverless"]
    assert any(finding.code == "observability.failure.cluster.recurring" for finding in result.findings)
    assert any(finding.code == "observability.error.network_recurring" for finding in result.findings)
    assert any(finding.code == "observability.runtime.mixed_failures" for finding in result.findings)


def test_analyze_control_tables_detects_freshness_sla_breach():
    result = analyze_control_tables(
        {
            "operations": [
                {
                    "target_table": "main.gold.daily_orders",
                    "freshness_sla_minutes": 180,
                    "minutes_since_last_success": 420,
                }
            ]
        }
    )

    assert result.status == "FAIL"
    assert any(finding.code == "observability.freshness.sla_breach" for finding in result.findings)


def test_load_control_table_evidence_accepts_full_core_table_names_for_databricks():
    package = load_control_table_evidence(
        {
            "scope": {
                "platform": "databricks",
                "catalog": "main",
                "ctrl_schema": "ops",
                "target_table": "main.bronze.orders",
            },
            "ctrl_ingestion_runs": [
                {"run_id": "1", "status": "SUCCESS", "target_table": "main.bronze.orders", "rows_written": 10}
            ],
            "ctrl_ingestion_quarantine": [
                {"run_id": "1", "target_table": "main.bronze.orders", "rule_name": "not_null"}
            ],
            "ctrl_ingestion_access": [
                {"run_id": "1", "target_table": "main.bronze.orders", "status": "FAILED", "access_type": "row_filter"}
            ],
            "ctrl_ingestion_annotations": [
                {"run_id": "1", "target_table": "main.bronze.orders", "status": "SUCCESS"}
            ],
            "ctrl_ingestion_cost": [
                {"run_id": "1", "target_table": "main.bronze.orders", "signal_name": "compute", "signal_value": 1.25}
            ],
            "ctrl_ingestion_state": [
                {"target_table": "main.bronze.orders", "last_status": "SUCCESS"}
            ],
        }
    )

    assert package.scope.platform == "databricks"
    assert len(package.runs) == 1
    assert len(package.quarantine) == 1
    assert len(package.access) == 1
    assert len(package.cost) == 1
    assert len(package.state) == 1


def test_analyze_databricks_evidence_reports_governance_and_cost_metrics():
    result = analyze_control_tables(
        {
            "scope": {
                "platform": "databricks",
                "catalog": "main",
                "ctrl_schema": "ops",
                "target_table": "main.bronze.orders",
            },
            "ctrl_ingestion_runs": [
                {"run_id": "1", "status": "SUCCESS", "target_table": "main.bronze.orders", "rows_written": 10}
            ],
            "ctrl_ingestion_access": [
                {"run_id": "1", "target_table": "main.bronze.orders", "status": "FAILED", "access_type": "mask"}
            ],
            "ctrl_ingestion_quality": [
                {"run_id": "1", "target_table": "main.bronze.orders", "rule_name": "not_null", "status": "PASSED"}
            ],
            "ctrl_ingestion_cost": [
                {"run_id": "1", "target_table": "main.bronze.orders", "signal_name": "compute", "signal_value": 2.5}
            ],
            "ctrl_ingestion_state": [
                {"target_table": "main.bronze.orders", "last_status": "SUCCESS"}
            ],
        }
    )

    assert result.metrics["platform"] == "databricks"
    assert result.metrics["cost_signals_total"] == 1
    assert result.metrics["estimated_cost_total"] == 2.5
    assert result.follow_up_queries[0].startswith("SELECT status, count(*) FROM main.ops.ctrl_ingestion_runs")
    assert any(finding.code == "observability.governance.access_failed" for finding in result.findings)


def test_analyze_aws_iceberg_evidence_uses_same_findings_model():
    result = analyze_control_tables(
        {
            "scope": {
                "platform": "aws",
                "evidence_store": "iceberg",
                "database": "contractforge_ops",
                "target_table": "glue_catalog.analytics.b_orders",
            },
            "aws_runs": [
                {
                    "run_id": "a",
                    "status": "SUCCESS",
                    "target_table": "glue_catalog.analytics.b_orders",
                    "source_connector": "postgres",
                    "runtime_type": "aws_glue_spark",
                    "rows_written": 100,
                }
            ],
            "aws_quality": [
                {
                    "run_id": "a",
                    "target_table": "glue_catalog.analytics.b_orders",
                    "rule_name": "accepted_values",
                    "status": "QUARANTINED",
                    "failed_count": 7,
                }
            ],
            "aws_lineage": [
                {
                    "run_id": "a",
                    "event_type": "COMPLETE",
                    "target_table": "glue_catalog.analytics.b_orders",
                }
            ],
            "aws_cost": [
                {
                    "run_id": "a",
                    "target_table": "glue_catalog.analytics.b_orders",
                    "signal_name": "glue_dpu_seconds",
                    "signal_value": 0.75,
                }
            ],
            "aws_state": [
                {"target_table": "glue_catalog.analytics.b_orders", "last_status": "FAILED"}
            ],
        }
    )

    assert result.metrics["platform"] == "aws"
    assert result.metrics["evidence_store"] == "iceberg"
    assert result.metrics["connectors"] == ["postgres"]
    assert result.metrics["runtimes"] == ["aws_glue_spark"]
    assert result.metrics["lineage_events_total"] == 1
    assert result.follow_up_queries[0].startswith(
        "SELECT status, count(*) FROM glue_catalog.contractforge_ops.ctrl_ingestion_runs"
    )
    assert any(finding.code == "observability.quality.quarantine" for finding in result.findings)
    assert any(finding.code == "observability.state.last_status_failed" for finding in result.findings)


def test_analyze_evidence_flags_missing_cost_and_partial_core_sections():
    result = analyze_control_tables(
        {
            "scope": {"platform": "aws", "evidence_store": "athena", "database": "contractforge_ops"},
            "runs": [{"run_id": "1", "status": "SUCCESS", "target_table": "t"}],
        }
    )

    assert result.status == "WARN"
    assert result.metrics["evidence_sections_present"] == ["runs"]
    assert {"errors", "quality", "state"} <= set(result.metrics["evidence_sections_missing"])
    assert any(finding.code == "observability.cost.missing" for finding in result.findings)
    assert any(finding.code == "observability.evidence.coverage_partial" for finding in result.findings)
