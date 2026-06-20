from pathlib import Path


def test_provider_backed_generation_smoke_notebook_contains_required_workflow():
    notebook = Path(__file__).resolve().parents[1] / "databricks_tests" / "provider_backed_generation_smoke.py"
    content = notebook.read_text(encoding="utf-8")

    assert "generate_from_intent" in content
    assert "ProviderConfig" in content
    assert "write_project_plan" in content
    assert "AI_REVIEW.html" in content
    assert "require_provider" in content
    assert "dbutils.notebook.exit" in content
