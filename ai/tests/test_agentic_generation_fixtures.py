import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from contractforge_ai.agentic import IntentGenerationRequest, generate_from_intent

FIXTURES = Path(__file__).parent / "fixtures" / "agentic_generation_cases.json"


@pytest.mark.parametrize("case_name", sorted(json.loads(FIXTURES.read_text(encoding="utf-8"))))
def test_agentic_generation_fixture_cases(case_name: str, tmp_path: Path):
    case = _case(case_name)
    request = IntentGenerationRequest(
        prompt=case["prompt"],
        schema_path=_write_schema(tmp_path, case) if "schema" in case else None,
        project_root=_write_project(tmp_path, case) if "project" in case else None,
        default_catalog="main",
    )

    result = generate_from_intent(request)
    expected = case["expected"]

    assert result.status == expected["status"]
    assert result.layers == expected["layers"]
    if "policy_action" in expected:
        assert result.policy_result is not None
        assert result.policy_result.action == expected["policy_action"]
    if "shape_columns" in expected:
        assert result.transformation_plan is not None
        assert result.transformation_plan.shape_columns == expected["shape_columns"]
    if "decision_paths" in expected:
        decision_paths = _decision_paths(result.to_dict())
        assert set(expected["decision_paths"]).issubset(decision_paths)

    artifact_paths = _artifact_paths(result)
    assert set(expected.get("required_artifacts", [])).issubset(artifact_paths)
    assert artifact_paths.isdisjoint(expected.get("forbidden_artifacts", []))
    if result.project is not None:
        review = next((artifact.content for artifact in result.project.artifacts if artifact.path == "AI_REVIEW.html"), "")
        assert "ContractForge AI Generation Review" in review


def _case(name: str) -> dict[str, Any]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))[name]


def _write_schema(tmp_path: Path, case: dict[str, Any]) -> str:
    path = tmp_path / "schema_or_sample.json"
    path.write_text(json.dumps(case["schema"], indent=2), encoding="utf-8")
    return str(path)


def _write_project(tmp_path: Path, case: dict[str, Any]) -> str:
    project = tmp_path / "project"
    for relative_path, payload in case["project"]["files"].items():
        target = project / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return str(project)


def _artifact_paths(result: Any) -> set[str]:
    if result.project is None:
        return set()
    return {artifact.path for artifact in result.project.artifacts}


def _decision_paths(payload: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for node in _walk(payload):
        if isinstance(node, dict) and isinstance(node.get("path"), str):
            paths.add(node["path"])
    return paths


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
