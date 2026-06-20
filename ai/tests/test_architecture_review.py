from pathlib import Path

from contractforge_ai.reviewers.architecture import review_governed_architecture


def test_review_governed_architecture_detects_cfa_style_modules(tmp_path: Path):
    repo = tmp_path / "cfa_like"
    src = repo / "src" / "cfa"
    src.mkdir(parents=True)
    (src / "types.py").write_text("class StateSignature: pass\nclass SignatureConstraints: pass\n", encoding="utf-8")
    (src / "policy.py").write_text("class PolicyEngine: pass\nclass PolicyRule: pass\n", encoding="utf-8")
    (src / "audit.py").write_text("event_hash = previous_hash = ''\nclass AuditTrail: pass\n", encoding="utf-8")
    (src / "context.py").write_text("class ContextRegistry: pass\n", encoding="utf-8")
    (src / "planner.py").write_text("class ExecutionPlanner: pass\n", encoding="utf-8")

    review = review_governed_architecture(repo)

    assert review.detected_count >= 5
    assert review.score > 0.5
    assert any(finding.concept == "Tamper-evident audit trail" and finding.status == "detected" for finding in review.findings)


def test_review_governed_architecture_marks_missing_concepts(tmp_path: Path):
    repo = tmp_path / "plain"
    repo.mkdir()
    (repo / "README.md").write_text("# Plain Project\n", encoding="utf-8")

    review = review_governed_architecture(repo)

    assert review.detected_count == 0
    assert all(finding.status == "missing" for finding in review.findings)
