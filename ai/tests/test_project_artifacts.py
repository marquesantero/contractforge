from pathlib import Path

import pytest

from contractforge_ai.models import Assumption, EvidenceItem, RequiredDecision, Traceability
from contractforge_ai.projects import DecisionReport, ProjectArtifact, ProjectPlan, load_project_plan, write_project_plan


def _plan() -> ProjectPlan:
    return ProjectPlan(
        name="orders",
        target="contractforge-yaml",
        artifacts=[
            ProjectArtifact(
                path="contracts/bronze/orders.ingestion.yaml",
                kind="contract",
                content="mode: scd0_append\n",
                description="Bronze ingestion contract.",
            ),
            ProjectArtifact(
                path="README.md",
                kind="markdown",
                content="# Orders\n",
            ),
        ],
        report=DecisionReport(
            title="Orders project",
            summary="Generated project scaffold.",
            assumptions=[Assumption(statement="Source schema was inferred from supplied metadata.", confidence=0.7)],
            decisions_required=[
                RequiredDecision(
                    question="Confirm target catalog",
                    reason="Catalog naming is environment-specific.",
                    path="target.catalog",
                )
            ],
        ),
        traceability=Traceability(
            confidence=0.8,
            evidence=[EvidenceItem(source="schema", reason="Schema metadata supplied by user.")],
            review_required=True,
        ),
    )


def test_project_plan_serializes_without_file_content_by_default():
    payload = _plan().to_dict()

    assert payload["name"] == "orders"
    assert payload["artifacts"][0]["path"] == "contracts/bronze/orders.ingestion.yaml"
    assert "content" not in payload["artifacts"][0]
    assert payload["report"]["decisions_required"][0]["path"] == "target.catalog"


def test_project_plan_can_include_content_for_debug_output():
    payload = _plan().to_dict(include_content=True)

    assert payload["artifacts"][0]["content"] == "mode: scd0_append\n"


def test_project_plan_rejects_duplicate_paths():
    with pytest.raises(ValueError, match="Duplicate artifact path"):
        ProjectPlan(
            name="bad",
            target="contractforge-yaml",
            artifacts=[
                ProjectArtifact(path="README.md", content="a"),
                ProjectArtifact(path="README.md", content="b"),
            ],
            report=DecisionReport(title="Bad", summary="Duplicate path."),
        )


def test_project_artifact_rejects_path_traversal():
    with pytest.raises(ValueError, match="relative"):
        ProjectArtifact(path="../outside.md", content="x")


def test_write_project_plan_creates_files(tmp_path: Path):
    result = write_project_plan(_plan(), tmp_path)

    assert [item.status for item in result] == ["created", "created", "created"]
    assert (tmp_path / "contracts/bronze/orders.ingestion.yaml").read_text(encoding="utf-8") == "mode: scd0_append\n"
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "# Orders\n"
    assert (tmp_path / "PROJECT_REVIEW.html").exists()


def test_write_project_plan_creates_rich_project_review_html(tmp_path: Path):
    write_project_plan(_plan(), tmp_path)

    review = (tmp_path / "PROJECT_REVIEW.html").read_text(encoding="utf-8")

    assert '<section class="hero">' in review
    assert '<section class="grid">' in review
    assert "Generated Project" in review
    assert "Recommended Next Actions" in review
    assert "Decisions Required Before Use" in review
    assert "Traceability Evidence" in review
    assert "Generated Artifacts" in review
    assert "Consolidated Project Plan" in review


def test_write_project_plan_skips_existing_files_without_force(tmp_path: Path):
    (tmp_path / "README.md").write_text("existing\n", encoding="utf-8")

    result = write_project_plan(_plan(), tmp_path)

    readme = next(item for item in result if item.path == "README.md")
    assert readme.status == "skipped"
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "existing\n"


def test_write_project_plan_overwrites_only_with_force(tmp_path: Path):
    (tmp_path / "README.md").write_text("existing\n", encoding="utf-8")

    result = write_project_plan(_plan(), tmp_path, force=True)

    readme = next(item for item in result if item.path == "README.md")
    assert readme.status == "overwritten"
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "# Orders\n"


def test_write_project_plan_dry_run_does_not_touch_files(tmp_path: Path):
    result = write_project_plan(_plan(), tmp_path, dry_run=True)

    assert [item.status for item in result] == ["created", "created", "created"]
    assert not (tmp_path / "README.md").exists()


def test_project_plan_markdown_contains_artifacts_and_decisions():
    markdown = _plan().to_markdown()

    assert "# Project Plan: orders" in markdown
    assert "`contracts/bronze/orders.ingestion.yaml`" in markdown
    assert "Confirm target catalog" in markdown


def test_load_project_plan_from_yaml(tmp_path: Path):
    source = tmp_path / "plan.yaml"
    source.write_text(
        """
name: orders
target: contractforge-yaml
artifacts:
  - path: README.md
    kind: markdown
    content: "# Orders\\n"
report:
  title: Orders project
  summary: Generated project scaffold.
  decisions_required:
    - question: Confirm target catalog
      reason: Catalog naming is environment-specific.
      path: target.catalog
traceability:
  confidence: 0.8
  review_required: true
""",
        encoding="utf-8",
    )

    plan = load_project_plan(source)

    assert plan.name == "orders"
    assert plan.artifacts[0].content == "# Orders\n"
    assert plan.report.decisions_required[0].path == "target.catalog"
