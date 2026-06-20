from __future__ import annotations

import json
import yaml
from pathlib import Path

from contractforge_core.contracts import load_contract_bundle
from contractforge_fabric import plan_fabric_contract, render_fabric_contract


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples" / "stable-surface" / "fabric"


def _project() -> dict[str, object]:
    return yaml.safe_load((PROJECT / "project.yaml").read_text(encoding="utf-8"))


def test_fabric_stable_surface_project_declares_expected_gate_counts() -> None:
    project = _project()
    steps = project["execution_order"]

    assert len(steps) == 16
    assert [step["expected_result"] for step in steps].count("succeeded") == 16
    assert project["stable_surface"]["expected_success_steps"] == 14
    assert project["stable_surface"]["expected_job_failed_steps"] == 0
    assert project["stable_surface"]["expected_evidence_failed_steps"] == 2
    assert steps[-1]["name"] == "evidence_probe"
    assert "quality_abort_failure" in steps[-1]["depends_on"]
    assert "strict_schema_failure" in steps[-1]["depends_on"]
    assert "governance_review_evidence" in steps[-1]["depends_on"]


def test_fabric_stable_surface_contracts_plan_and_render_notebooks() -> None:
    project = _project()
    environment = yaml.safe_load((PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    for step in project["execution_order"]:
        path = PROJECT / step["contracts"]["fabric"]
        contract = load_contract_bundle(path.with_name(path.name.removesuffix(".ingestion.yaml"))).contract
        planning = plan_fabric_contract(contract, environment=environment)
        expected_status = "REVIEW_REQUIRED" if step["name"] == "governance_review_evidence" else "SUPPORTED_WITH_WARNINGS"
        assert planning.status == expected_status, step["name"]
        assert not planning.blockers, step["name"]
        artifacts = render_fabric_contract(contract, environment=environment).artifacts
        notebook_artifacts = [name for name in artifacts if name.endswith(".fabric.notebook.py")]
        assert len(notebook_artifacts) == 1, step["name"]
        compile(artifacts[notebook_artifacts[0]], notebook_artifacts[0], "exec")


def test_fabric_stable_surface_uses_contract_only_sql_sources() -> None:
    project = _project()
    for step in project["execution_order"]:
        path = PROJECT / step["contracts"]["fabric"]
        contract = load_contract_bundle(path.with_name(path.name.removesuffix(".ingestion.yaml"))).contract
        assert contract["source"]["type"] == "sql"
        assert "query" in contract["source"]


def test_fabric_stable_surface_evidence_probe_checks_control_tables() -> None:
    probe = load_contract_bundle(PROJECT / "contracts" / "16_evidence_probe").contract
    query = probe["source"]["query"]

    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_errors" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert "contractforge.ctrl_ingestion_lineage" in query
    assert "contractforge.ctrl_ingestion_explain" in query
    assert "contractforge.ctrl_ingestion_state" in query
    assert "contractforge.ctrl_ingestion_operations" in query
    assert "contractforge.ctrl_ingestion_annotations" in query
    assert "contractforge.ctrl_ingestion_access" in query
    assert probe["quality_rules"]["min_rows"] == 12


def test_fabric_stable_surface_evidence_manifest_matches_project() -> None:
    project = _project()
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-stable-surface-evidence.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["project"] == "examples/stable-surface/fabric/project.yaml"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["expected_control_table_failed_runs"] == 2
    assert manifest["result_summary"]["evidence_probe_result"] == "SUCCEEDED"
    assert manifest["result_summary"]["evidence_probe_checks"] == 12
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert "hash_diff_upsert" in manifest["coverage"]["write_modes"]
    assert "quality_abort" in manifest["coverage"]["failure_path_evidence"]
    assert "ctrl_ingestion_state" in manifest["coverage"]["control_table_probe"]
    assert "governance_review_evidence" in {step["name"] for step in manifest["steps"]}
    assert manifest["coverage"]["governance_review_evidence"] == ["operations", "annotations", "access"]
    assert "ctrl_ingestion_access" in manifest["coverage"]["control_table_probe"]
