from __future__ import annotations

import json
from pathlib import Path

from contractforge_snowflake.cli import main as snowflake_cli_main


ROOT = Path(__file__).resolve().parents[1]


def test_snowflake_cli_stabilization_report_is_explicit_about_final_boundaries(capsys) -> None:
    assert snowflake_cli_main(["stabilization-report"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["adapter"] == "contractforge-snowflake"
    assert payload["subtarget"] == "snowflake_sql_warehouse"
    assert payload["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert payload["supported_surface_ready"] is True
    assert payload["stable_final"] is True
    assert payload["stability_criteria"] == "docs/specs/snowflake-ga-criteria.md"
    assert payload["waiver_registry"] == "docs/specs/snowflake-ga-waivers.md"
    assert payload["evidence_manifest"] == "docs/reports/snowflake-stable-surface-evidence.json"
    assert {item["code"] for item in payload["accepted_review_boundaries"]} == {
        "SNOWFLAKE_HASH_DIFF_PERFORMANCE_UNVALIDATED",
        "SNOWFLAKE_ACCESS_POLICY_ACCOUNT_FEATURE_BLOCKED",
        "SNOWFLAKE_CONTINUOUS_INGESTION_REVIEW",
        "SNOWFLAKE_SCD2_REVIEW",
    }
    assert {"name": "snowflake_smoke_task_graph", "status": "PASS"} in payload["real_validation_projects"]
    assert {"name": "snowflake_hashdiff_production_benchmark", "status": "PASS"} in payload["real_validation_projects"]
    scd2 = next(item for item in payload["accepted_review_boundaries"] if item["code"] == "SNOWFLAKE_SCD2_REVIEW")
    assert scd2["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    access_policy = next(
        item
        for item in payload["accepted_review_boundaries"]
        if item["code"] == "SNOWFLAKE_ACCESS_POLICY_ACCOUNT_FEATURE_BLOCKED"
    )
    assert access_policy["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert payload["next_promotion_gates"] == []
    continuous = next(
        item for item in payload["accepted_review_boundaries"] if item["code"] == "SNOWFLAKE_CONTINUOUS_INGESTION_REVIEW"
    )
    assert continuous["decision"] == "EXCLUDED_FROM_STABLE_FINAL"


def test_snowflake_cli_stabilization_report_strict_final_passes_for_documented_scope(capsys) -> None:
    assert snowflake_cli_main(["stabilization-report", "--strict-final"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["stable_final"] is True


def test_snowflake_docs_define_stable_surface_gate_and_waivers() -> None:
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    adapter_doc = (ROOT / "docs" / "adapters" / "snowflake.md").read_text(encoding="utf-8")
    criteria = (ROOT / "docs" / "specs" / "snowflake-ga-criteria.md").read_text(encoding="utf-8")
    waivers = (ROOT / "docs" / "specs" / "snowflake-ga-waivers.md").read_text(encoding="utf-8")

    assert "specs/snowflake-ga-criteria.md" in index
    assert "specs/snowflake-ga-waivers.md" in index
    assert "../specs/snowflake-ga-criteria.md" in adapter_doc
    assert "STABLE_SUPPORTED_SURFACE" in criteria
    assert "stable_final = true" in criteria
    assert "No waivers are currently recorded." in waivers


def test_snowflake_stable_surface_evidence_manifest_is_complete() -> None:
    manifest = json.loads((ROOT / "docs" / "reports" / "snowflake-stable-surface-evidence.json").read_text(encoding="utf-8"))

    assert manifest["kind"] == "contractforge_snowflake_stable_surface_evidence"
    assert manifest["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert manifest["supported_surface_ready"] is True
    assert manifest["stable_final"] is True
    assert manifest["stability_criteria"] == "docs/specs/snowflake-ga-criteria.md"
    assert manifest["waiver_registry"] == "docs/specs/snowflake-ga-waivers.md"
    assert {item["name"] for item in manifest["real_validation_projects"]} >= {
        "snowflake_smoke_minimal",
        "snowflake_smoke_failure_paths",
        "snowflake_smoke_stage_publish",
        "snowflake_smoke_procedure",
        "snowflake_smoke_task_graph",
        "snowflake_usgs_rest_medallion",
        "snowflake_hashdiff_production_benchmark",
    }
    assert {boundary["code"] for boundary in manifest["accepted_review_boundaries"]} >= {
        "SNOWFLAKE_ACCESS_POLICY_ACCOUNT_FEATURE_BLOCKED",
        "SNOWFLAKE_CONTINUOUS_INGESTION_REVIEW",
        "SNOWFLAKE_SCD2_REVIEW",
    }
    access_policy = next(
        boundary
        for boundary in manifest["accepted_review_boundaries"]
        if boundary["code"] == "SNOWFLAKE_ACCESS_POLICY_ACCOUNT_FEATURE_BLOCKED"
    )
    assert access_policy["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    continuous = next(
        boundary
        for boundary in manifest["accepted_review_boundaries"]
        if boundary["code"] == "SNOWFLAKE_CONTINUOUS_INGESTION_REVIEW"
    )
    assert continuous["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert set(manifest["same_contract_e2e"]["platforms"]) == {"databricks", "aws", "snowflake"}
