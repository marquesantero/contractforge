from pathlib import Path

from contractforge_ai.context import build_knowledge_index
from contractforge_ai.intelligence import TaskRouteRequest, route_task


def test_route_task_selects_project_synthesis_with_context(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "projects.md").write_text(
        """
# Project generation

Context-aware generated projects must keep required decisions visible.
Databricks Asset Bundle output is useful after keys and runtime dependencies are reviewed.
""".strip(),
        encoding="utf-8",
    )
    index = build_knowledge_index([docs], root=tmp_path)

    report = route_task(
        TaskRouteRequest(
            intent="Create a complete project scaffold from a context package and generated project.",
            knowledge_index=index,
        )
    )

    assert report.task == "project_synthesis"
    assert report.prompt_name == "project.synthesis.enrichment.v1"
    assert report.provider_task == "project_planning"
    assert report.context_results
    assert report.provider_routing["selected"]["structured_output_strategy"] == "strict_schema"


def test_route_task_uses_explicit_hint_and_low_context_warning(tmp_path: Path):
    index = build_knowledge_index([tmp_path], root=tmp_path)

    report = route_task(
        TaskRouteRequest(
            intent="The user asks a vague question.",
            task_hint="observability_analysis",
            knowledge_index=index,
        )
    )

    assert report.task == "observability_analysis"
    assert report.confidence == 0.95
    assert "Explicit task hint" in report.reasons[0]
    assert any("no relevant context" in warning for warning in report.warnings)


def test_route_task_defaults_to_project_planning_for_unclear_intent():
    report = route_task(TaskRouteRequest(intent="Help me with this."))

    assert report.task == "project_planning"
    assert report.confidence == 0.35
    assert report.warnings


def test_route_task_can_prefer_http_only_for_low_risk_metadata():
    report = route_task(
        TaskRouteRequest(
            intent="Suggest annotations and quality rules for an orders schema.",
            prefer_http_only=True,
        )
    )

    assert report.task == "metadata_suggestion"
    assert report.provider_routing["selected"]["databricks_dependency_mode"] == "http_only"


def test_route_task_keeps_strict_schema_for_project_planning_when_http_only_preferred():
    report = route_task(
        TaskRouteRequest(
            intent="Generate a complete AWS Glue project scaffold for orders.",
            prefer_http_only=True,
        )
    )

    assert report.task == "project_planning"
    assert report.provider_routing["selected"]["structured_output_strategy"] == "strict_schema"
    assert report.provider_routing["selected"]["databricks_dependency_mode"] != "http_only"
