from __future__ import annotations

import json
from pathlib import Path

import yaml

from contractforge_aws import render_aws_contract
from contractforge_gcp import render_gcp_contract
from contractforge_snowflake import deploy_snowflake_project, render_snowflake_contract


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "examples" / "benchmarks" / "hash-diff-production"
REQUIRED_CASES = {
    "initial_load",
    "no_change_replay",
    "changed_row_wave",
    "concurrent_or_overlap_guard",
    "duplicate_key_failure",
    "null_key_failure",
}


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_hashdiff_benchmark_project_references_existing_artifacts() -> None:
    project = _yaml(BENCHMARK / "project.yaml")
    step = project["execution_order"][0]

    assert set(project["environments"]) == {"aws", "gcp", "snowflake"}
    for relative in project["environments"].values():
        assert (BENCHMARK / relative).is_file()
    for relative in step["contracts"].values():
        assert (BENCHMARK / relative).is_file()
    for case in REQUIRED_CASES - {"concurrent_or_overlap_guard"}:
        assert (BENCHMARK / "data" / case / "customers.csv").is_file()
    assert (BENCHMARK / "snowflake" / "seed_tables.sql").is_file()
    assert set(project["validation"]["required_cases"]) == REQUIRED_CASES


def test_hashdiff_benchmark_manifests_point_to_project_and_cases() -> None:
    project = _yaml(BENCHMARK / "project.yaml")
    for report_name, adapter in (
        ("aws-hashdiff-production-benchmark.json", "contractforge-aws"),
        ("gcp-bigquery-hashdiff-production-benchmark.json", "contractforge-gcp"),
        ("snowflake-hashdiff-production-benchmark.json", "contractforge-snowflake"),
    ):
        manifest = json.loads((ROOT / "docs" / "reports" / report_name).read_text(encoding="utf-8"))

        assert manifest["adapter"] == adapter
        assert manifest["benchmark_project"] == "examples/benchmarks/hash-diff-production/project.yaml"
        assert set(manifest["required_cases"]) == set(project["validation"]["required_cases"])
        assert Path(ROOT / manifest["benchmark_contract"]).is_file()
        if adapter == "contractforge-aws":
            assert manifest["status"] == "PASS"
            assert {result["case"] for result in manifest["live_results"]} == REQUIRED_CASES
        elif adapter == "contractforge-gcp":
            assert manifest["status"] == "PASS_WITH_REVIEW_BOUNDARY"
            assert {result["case"] for result in manifest["live_results"]} == REQUIRED_CASES
            no_change = next(result for result in manifest["live_results"] if result["case"] == "no_change_replay")
            changed_wave = next(result for result in manifest["live_results"] if result["case"] == "changed_row_wave")
            overlap = next(result for result in manifest["live_results"] if result["case"] == "concurrent_or_overlap_guard")
            assert no_change["rows_inserted"] == 0
            assert no_change["rows_updated"] == 0
            assert changed_wave["rows_updated"] == 250
            assert overlap["first_run"]["rows_updated"] == 200
            assert overlap["second_run"]["rows_updated"] == 0
            assert overlap["target_verification"]["row_count"] == 10000
            assert overlap["target_verification"]["distinct_keys"] == 10000
        else:
            assert manifest["status"] == "PASS"
            assert {result["case"] for result in manifest["live_results"]} == REQUIRED_CASES
            assert manifest["cost_reconciliation"]["status"] == "RECORDED"
            no_change = next(result for result in manifest["live_results"] if result["case"] == "no_change_replay")
            changed_wave = next(result for result in manifest["live_results"] if result["case"] == "changed_row_wave")
            assert no_change["hash_diff_candidate_rows"] == 0
            assert changed_wave["hash_diff_candidate_rows"] == 2


def test_aws_hashdiff_benchmark_contract_renders_profile_and_report() -> None:
    contract = _yaml(BENCHMARK / "contracts" / "aws" / "customers_hashdiff.ingestion.yaml")
    environment = _yaml(BENCHMARK / "environments" / "aws.environment.yaml")

    rendered = render_aws_contract(contract, environment=environment).artifacts
    profile = json.loads(rendered["contractforge_cf_hashdiff_prod_silver_s_customers_hashdiff.performance_profile.json"])
    report_sql = rendered["contractforge_cf_hashdiff_prod_silver_s_customers_hashdiff.performance.sql"]

    assert profile["status"] == "benchmark_required"
    assert {case["name"] for case in profile["benchmark_cases"]} == REQUIRED_CASES
    assert "no_change_replay" in report_sql
    assert "changed_row_wave" in report_sql
    assert "contractforge_cf_hashdiff_prod_ops" in report_sql


def test_snowflake_hashdiff_benchmark_contract_and_project_render() -> None:
    contract = _yaml(BENCHMARK / "contracts" / "snowflake" / "customers_hashdiff.ingestion.yaml")
    environment = _yaml(BENCHMARK / "environments" / "snowflake.environment.yaml")

    rendered = render_snowflake_contract(contract, environment=environment).artifacts
    deployment = deploy_snowflake_project(BENCHMARK / "project.yaml", dry_run=True)

    assert any(name.endswith("CF_HASHDIFF_PROD_TARGET.contract.json") for name in rendered)
    assert "deployment/snowflake_task_graph.sql" in deployment.deployment_artifacts
    assert deployment.steps[0].name == "customers_hashdiff"


def test_gcp_hashdiff_benchmark_contract_renders_review_required_bundle() -> None:
    contract = _yaml(BENCHMARK / "contracts" / "gcp" / "customers_hashdiff.ingestion.yaml")
    environment = _yaml(BENCHMARK / "environments" / "gcp.environment.yaml")

    rendered = render_gcp_contract(contract, environment=environment).artifacts
    prefix = "gcp-project-redacted_contractforge_gcp_hashdiff_prod_customers_hashdiff_target"
    review = json.loads(rendered[f"{prefix}.gcp.advanced_write_mode_review.json"])
    deployment = json.loads(rendered[f"{prefix}.gcp.deployment_manifest.json"])
    write_sql = rendered[f"{prefix}.gcp.write.sql"]

    assert review["status"] == "PLANNED_REVIEW_REQUIRED"
    assert review["mode"] == {"alias": "hash_diff_upsert", "canonical": "scd1_hash_diff"}
    assert review["hash_diff"]["hash_input_columns"] == [
        "segment",
        "status",
        "balance",
        "updated_at",
        "payload_hash_noise",
    ]
    assert deployment["status"] == "review_required"
    assert deployment["execution_ready"] is False
    assert "CONTRACTFORGE_NULL_MERGE_KEY" in write_sql
    assert "CONTRACTFORGE_DUPLICATE_MERGE_KEYS" in write_sql
    assert "MERGE `gcp-project-redacted.contractforge_gcp_hashdiff_prod.customers_hashdiff_target`" in write_sql
