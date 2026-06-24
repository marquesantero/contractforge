from __future__ import annotations

import json
from pathlib import Path

import yaml

from contractforge_core.contracts import load_contract_bundle, semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter, render_databricks_project_bundle


PROJECT = Path("examples/real-world/databricks-movie-custom-transform")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_movie_custom_transform_example_contracts_are_valid() -> None:
    contracts = sorted(PROJECT.glob("contracts/databricks/**/*.ingestion.yaml"))

    assert {path.name for path in contracts} == {
        "bronze_movie_ratings.ingestion.yaml",
        "bronze_movie_titles.ingestion.yaml",
        "silver_movie_ratings.ingestion.yaml",
        "gold_movie_feature_summary.ingestion.yaml",
    }
    for path in contracts:
        semantic_contract_from_mapping(_load_yaml(path))
        bundle = load_contract_bundle(path)
        assert bundle.semantic.target.name


def test_movie_custom_transform_bundle_uses_native_notebook_pre_task() -> None:
    project = _load_yaml(PROJECT / "project.yaml")
    committed_bundle = _load_yaml(PROJECT / "databricks.yml")

    bundle = render_databricks_project_bundle(project)
    job = bundle["resources"]["jobs"]["movie_custom_transform"]
    tasks = {task["task_key"]: task for task in job["tasks"]}
    committed_job = committed_bundle["resources"]["jobs"]["movie_custom_transform"]
    committed_tasks = {task["task_key"]: task for task in committed_job["tasks"]}

    assert tasks["prepare_movie_features"]["notebook_task"]["notebook_path"] == "./notebooks/prepare_movie_features.py"
    assert tasks["prepare_movie_features"]["depends_on"] == [
        {"task_key": "silver_movie_ratings"},
        {"task_key": "bronze_movie_titles"},
    ]
    assert tasks["gold_movie_feature_summary"]["depends_on"] == [{"task_key": "prepare_movie_features"}]
    assert job["environments"][0]["spec"]["dependencies"] == ["contractforge-core", "contractforge-databricks"]
    assert committed_tasks["prepare_movie_features"]["depends_on"] == [
        {"task_key": "silver_movie_ratings"},
        {"task_key": "bronze_movie_titles"},
    ]
    assert committed_tasks["gold_movie_feature_summary"]["depends_on"] == [{"task_key": "prepare_movie_features"}]
    assert committed_job["environments"][0]["spec"]["dependencies"] == ["contractforge-core", "contractforge-databricks"]


def test_movie_custom_transform_gold_contract_renders_review_artifacts() -> None:
    contract = semantic_contract_from_mapping(
        _load_yaml(
            PROJECT
            / "contracts/databricks/gold/gold_movie_feature_summary/gold_movie_feature_summary.ingestion.yaml"
        )
    )
    adapter = DatabricksAdapter.from_evidence(
        target_table="workspace.cf_movie_gold.g_movie_feature_summary",
        runtime_type="serverless",
    )

    artifacts = adapter.render_contract(contract).artifacts

    review = json.loads(artifacts["gold_g_movie_feature_summary.custom_transform_review.json"])
    assert review["kind"] == "databricks_custom_transform_review_plan"
    assert review["inputs"] == [
        {"alias": "ratings", "table": "workspace.cf_movie_silver.s_movie_ratings"},
        {"alias": "movies", "table": "workspace.cf_movie_bronze.b_movie_titles"},
    ]
    assert review["custom_transform"]["name"] == "movie_genre_feature_engineering"
    bundle = artifacts["gold_g_movie_feature_summary.databricks.yml"]
    assert "task_key: prepare_movie_features" in bundle
    assert "notebook_path: ./notebooks/prepare_movie_features.py" in bundle
    assert "- task_key: prepare_movie_features" in bundle
