from pathlib import Path

from contractforge_ai.models import Traceability
from contractforge_ai.projects import (
    DecisionReport,
    ProjectArtifact,
    ProjectPlan,
    generate_missing_sibling_contracts,
    plan_project_patches,
)


def _plan() -> ProjectPlan:
    return ProjectPlan(
        name="orders",
        target="contractforge-yaml",
        artifacts=[
            ProjectArtifact(
                path="contracts/bronze/b_orders.ingestion.yaml",
                kind="contract",
                description="Bronze ingestion contract.",
                content="target:\n  table: b_orders\n",
            ),
            ProjectArtifact(
                path="AI_REVIEW.html",
                kind="other",
                description="Review report.",
                content="<html>review</html>",
            ),
        ],
        report=DecisionReport(title="Orders", summary="Generated project."),
        traceability=Traceability(),
    )


def test_plan_project_patches_marks_missing_artifacts_as_create(tmp_path: Path):
    patch_plan = plan_project_patches(_plan(), tmp_path)

    assert patch_plan.creates == 2
    assert patch_plan.updates == 0
    assert patch_plan.conflicts == 0
    assert all(patch.action == "create" for patch in patch_plan.patches)
    assert patch_plan.to_dict()["creates"] == 2


def test_plan_project_patches_preserves_matching_artifacts(tmp_path: Path):
    target = tmp_path / "contracts" / "bronze"
    target.mkdir(parents=True)
    (target / "b_orders.ingestion.yaml").write_text("target:\n  table: b_orders\n", encoding="utf-8")

    patch_plan = plan_project_patches(_plan(), tmp_path)
    actions = {patch.path: patch.action for patch in patch_plan.patches}

    assert actions["contracts/bronze/b_orders.ingestion.yaml"] == "preserve"
    assert actions["AI_REVIEW.html"] == "create"
    assert patch_plan.preserves == 1


def test_plan_project_patches_conflicts_by_default_when_existing_content_differs(tmp_path: Path):
    target = tmp_path / "contracts" / "bronze"
    target.mkdir(parents=True)
    (target / "b_orders.ingestion.yaml").write_text("target:\n  table: changed\n", encoding="utf-8")

    patch_plan = plan_project_patches(_plan(), tmp_path)
    patch = next(item for item in patch_plan.patches if item.path == "contracts/bronze/b_orders.ingestion.yaml")

    assert patch.action == "conflict"
    assert patch.current_hash != patch.proposed_hash
    assert patch_plan.has_conflicts


def test_plan_project_patches_allows_updates_explicitly(tmp_path: Path):
    target = tmp_path / "contracts" / "bronze"
    target.mkdir(parents=True)
    (target / "b_orders.ingestion.yaml").write_text("target:\n  table: changed\n", encoding="utf-8")

    patch_plan = plan_project_patches(_plan(), tmp_path, allow_updates=True)
    patch = next(item for item in patch_plan.patches if item.path == "contracts/bronze/b_orders.ingestion.yaml")

    assert patch.action == "update"
    assert patch.writes_file


def test_plan_project_patches_can_force_review_report_conflicts(tmp_path: Path):
    (tmp_path / "AI_REVIEW.html").write_text("<html>old review</html>", encoding="utf-8")

    patch_plan = plan_project_patches(_plan(), tmp_path, allow_updates=True, conflict_on_review_artifacts=True)
    patch = next(item for item in patch_plan.patches if item.path == "AI_REVIEW.html")

    assert patch.action == "conflict"
    assert patch.reason.startswith("Review artifacts differ")


def test_generate_missing_sibling_contracts_creates_annotations_and_operations(tmp_path: Path):
    contracts_dir = tmp_path / "contracts" / "bronze"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "b_orders.ingestion.yaml").write_text(
        "\n".join(
            [
                "target:",
                "  catalog: main",
                "  schema: bronze",
                "  table: b_orders",
                "mode: scd0_append",
                "source:",
                "  connector: files",
                "  path: /landing/orders",
            ]
        ),
        encoding="utf-8",
    )

    sibling_plan = generate_missing_sibling_contracts(tmp_path)
    artifact_paths = {artifact.path for artifact in sibling_plan.artifacts}

    assert artifact_paths == {
        "contracts/bronze/b_orders.annotations.yaml",
        "contracts/bronze/b_orders.operations.yaml",
    }
    assert sibling_plan.patch_plan is not None
    assert sibling_plan.patch_plan.creates == 2
    assert sibling_plan.patch_plan.conflicts == 0
    assert "REVIEW_REQUIRED" in next(
        artifact.content for artifact in sibling_plan.artifacts if artifact.path.endswith(".operations.yaml")
    )


def test_generate_missing_sibling_contracts_skips_existing_siblings(tmp_path: Path):
    contracts_dir = tmp_path / "contracts" / "silver"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "s_orders.ingestion.yaml").write_text(
        "\n".join(
            [
                "target:",
                "  catalog: main",
                "  schema: silver",
                "  table: s_orders",
                "mode: scd1_hash_diff",
            ]
        ),
        encoding="utf-8",
    )
    (contracts_dir / "s_orders.annotations.yaml").write_text("table:\n  description: Orders\n", encoding="utf-8")

    sibling_plan = generate_missing_sibling_contracts(tmp_path)
    artifact_paths = [artifact.path for artifact in sibling_plan.artifacts]

    assert artifact_paths == ["contracts/silver/s_orders.operations.yaml"]
    assert sibling_plan.patch_plan is not None
    assert sibling_plan.patch_plan.creates == 1
