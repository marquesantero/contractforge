from __future__ import annotations

import json
from pathlib import Path

import yaml

from contractforge_gcp import render_gcp_contract


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "examples" / "benchmarks" / "advanced-write-production"
REQUIRED_CASES = {
    "historical_initial_load",
    "historical_no_change_replay",
    "historical_changed_row_wave",
    "historical_delete_expression",
    "historical_late_arriving_reject",
    "snapshot_initial_load",
    "snapshot_no_change_replay",
    "snapshot_changed_and_tombstone_wave",
    "snapshot_tombstone_replay",
    "snapshot_reactivation_wave",
}


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_advanced_write_production_project_references_existing_gcp_artifacts() -> None:
    project = _yaml(BENCHMARK / "project.yaml")

    assert set(project["environments"]) == {"gcp"}
    assert (BENCHMARK / project["environments"]["gcp"]).is_file()
    assert project["validation"]["maturity_gates"]["gcp"] == "GCP-BQ-12C5"
    assert set(project["validation"]["required_cases"]) == REQUIRED_CASES
    for step in project["execution_order"]:
        assert (BENCHMARK / step["contracts"]["gcp"]).is_file()


def test_advanced_write_production_report_points_to_project_and_cases() -> None:
    project = _yaml(BENCHMARK / "project.yaml")
    report = json.loads(
        (ROOT / "docs" / "reports" / "gcp-bigquery-advanced-write-production-benchmark.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["kind"] == "contractforge_gcp_advanced_write_production_benchmark"
    assert report["adapter"] == "contractforge-gcp"
    assert report["status"] == "PASS_WITH_REVIEW_BOUNDARY"
    assert report["benchmark_project"] == "examples/benchmarks/advanced-write-production/project.yaml"
    assert set(report["required_cases"]) == set(project["validation"]["required_cases"])
    assert {result["case"] for result in report["live_results"]} == REQUIRED_CASES
    assert report["evidence_readback"]["run_evidence_by_status"] == {"FAILED": 1, "SUCCEEDED": 9}

    historical_changed = next(result for result in report["live_results"] if result["case"] == "historical_changed_row_wave")
    snapshot_tombstone = next(result for result in report["live_results"] if result["case"] == "snapshot_changed_and_tombstone_wave")
    snapshot_reactivate = next(result for result in report["live_results"] if result["case"] == "snapshot_reactivation_wave")

    assert historical_changed["inserted_rows"] == 250
    assert snapshot_tombstone["updated_rows"] == 10000
    assert snapshot_reactivate["updated_rows"] == 100


def test_gcp_advanced_write_production_contracts_render_review_required_sql() -> None:
    environment = _yaml(BENCHMARK / "environments" / "gcp.environment.yaml")
    historical = _yaml(BENCHMARK / "contracts" / "gcp" / "customers_historical.ingestion.yaml")
    snapshot = _yaml(BENCHMARK / "contracts" / "gcp" / "customers_snapshot.ingestion.yaml")

    historical_artifacts = render_gcp_contract(historical, environment=environment).artifacts
    snapshot_artifacts = render_gcp_contract(snapshot, environment=environment).artifacts
    historical_prefix = "gcp-project-redacted_contractforge_gcp_advanced_prod_customers_historical_target"
    snapshot_prefix = "gcp-project-redacted_contractforge_gcp_advanced_prod_customers_snapshot_target"
    historical_review = json.loads(historical_artifacts[f"{historical_prefix}.gcp.advanced_write_mode_review.json"])
    snapshot_review = json.loads(snapshot_artifacts[f"{snapshot_prefix}.gcp.advanced_write_mode_review.json"])
    historical_sql = historical_artifacts[f"{historical_prefix}.gcp.write.sql"]
    snapshot_sql = snapshot_artifacts[f"{snapshot_prefix}.gcp.write.sql"]

    assert historical_review["status"] == "PLANNED_REVIEW_REQUIRED"
    assert historical_review["mode"] == {"alias": "historical", "canonical": "scd2_historical"}
    assert historical_review["historical"]["late_arriving_policy"] == "reject"
    assert historical_review["historical"]["apply_as_deletes"] == "status = 'DELETE'"
    assert "CONTRACTFORGE_LATE_ARRIVING_HISTORICAL" in historical_sql
    assert "WHERE NOT S.apply_as_delete" in historical_sql

    assert snapshot_review["status"] == "PLANNED_REVIEW_REQUIRED"
    assert snapshot_review["mode"] == {"alias": "snapshot_reconcile_soft_delete", "canonical": "snapshot_soft_delete"}
    assert snapshot_review["blockers"] == []
    assert "WHEN NOT MATCHED BY SOURCE AND T.is_active = TRUE THEN" in snapshot_sql
    assert "UPDATE SET is_active = FALSE" in snapshot_sql
