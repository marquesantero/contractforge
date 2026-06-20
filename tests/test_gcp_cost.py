from __future__ import annotations

import json

import pytest

from contractforge_gcp import CostModel, build_operational_cost_report, render_operational_cost_query
from contractforge_gcp.cli import main as gcp_cli


def test_gcp_cost_query_groups_evidence_and_uses_operator_rates() -> None:
    query = render_operational_cost_query(
        project_id="test-project",
        dataset="contractforge_ops",
        group_by=("target_table", "contract_name", "statement_type"),
        cost_model=CostModel(bytes_processed_per_tib_rate=6.25, slot_hour_rate=0.04, currency="USD"),
        include_failed=False,
    )

    assert "FROM `test-project.contractforge_ops.contractforge_run_evidence`" in query
    assert "`target_table`" in query
    assert "`contract_name`" in query
    assert "`statement_type`" in query
    assert "AND status = 'SUCCEEDED'" in query
    assert "6.25 AS bytes_processed_per_tib_rate" in query
    assert "0.04 AS slot_hour_rate" in query
    assert "estimated_bytes_processed_cost" in query
    assert "estimated_slot_cost" in query
    assert "estimated_from_bigquery_job_evidence" in query


def test_gcp_cost_query_does_not_assume_rates() -> None:
    query = render_operational_cost_query()

    assert "NULL AS bytes_processed_per_tib_rate" in query
    assert "NULL AS slot_hour_rate" in query
    assert "estimated_total_cost" in query


def test_gcp_cost_query_rejects_unknown_grouping() -> None:
    with pytest.raises(ValueError, match="unknown group_by"):
        render_operational_cost_query(group_by=("target_table", "secret"))


def test_gcp_cost_report_is_query_only_by_default() -> None:
    report = build_operational_cost_report(
        project_id="test-project",
        cost_model=CostModel(bytes_processed_per_tib_rate=1.0),
    )

    assert report["status"] == "QUERY_ONLY"
    assert report["project_id"] == "test-project"
    assert report["cost_model"]["enabled"] is True
    assert report["rows"] == []
    assert "contractforge_run_evidence" in report["query"]


def test_gcp_cost_report_can_collect_rows_from_runner() -> None:
    class Runner:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def query(self, sql: str):
            self.queries.append(sql)
            return type("Result", (), {"result_rows": [{"target_table": "p.d.t", "runs": 2}]})()

    runner = Runner()
    report = build_operational_cost_report(query_only=False, runner=runner, limit=7)

    assert report["status"] == "SUCCESS"
    assert report["rows"] == [{"target_table": "p.d.t", "runs": 2}]
    assert runner.queries[0].endswith("LIMIT 7")


def test_gcp_cli_cost_report_uses_environment_defaults(tmp_path, capsys) -> None:
    environment = tmp_path / "environment.yaml"
    environment.write_text(
        """
parameters:
  gcp:
    project_id: test-project
    dataset: contractforge
evidence:
  dataset: contractforge_ops
""".strip(),
        encoding="utf-8",
    )

    rc = gcp_cli(
        [
            "cost-report",
            "--environment",
            str(environment),
            "--group-by",
            "target_table",
            "--bytes-processed-per-tib-rate",
            "6.25",
            "--success-only",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["project_id"] == "test-project"
    assert payload["dataset"] == "contractforge_ops"
    assert payload["group_by"] == ["target_table"]
    assert payload["include_failed"] is False
    assert payload["cost_model"]["bytes_processed_per_tib_rate"] == 6.25
