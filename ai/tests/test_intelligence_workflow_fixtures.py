import json
from pathlib import Path

from contractforge_ai.intelligence import TaskRouteRequest, critique_output, route_task
from contractforge_ai.observability import analyze_control_tables
from contractforge_ai.planning import ProjectPlannerRequest, plan_project_from_intent
from contractforge_ai.validation import validate_model_artifact

FIXTURES = Path(__file__).parent / "fixtures" / "intelligence"


def test_workflow_fixture_project_planning_keeps_required_decisions():
    case = _case("project_planning_incomplete_hash_diff")

    result = plan_project_from_intent(
        ProjectPlannerRequest(intent=case["intent"], schema_path=case["schema_path"])
    )

    assert result.status == case["expected"]["status"]
    assert result.intent.connector == case["expected"]["connector"]
    assert any(decision.path == case["expected"]["decision_path"] for decision in result.decisions_required)
    assert result.traceability.evidence


def test_workflow_fixture_control_table_incident_has_expected_findings():
    case = _case("control_table_incident")

    result = analyze_control_tables(case["evidence"])

    assert result.status == case["expected"]["status"]
    actual_codes = {finding.code for finding in result.findings}
    assert set(case["expected"]["finding_codes"]).issubset(actual_codes)
    assert result.recommendations
    assert result.follow_up_queries
    assert result.traceability.evidence


def test_workflow_fixture_invalid_provider_output_is_not_ready():
    case = _case("provider_output_invalid")

    validation = validate_model_artifact(case["output"], prompt_name=case["prompt"])
    critique = critique_output(case["output"], validation=validation)

    assert validation.status == case["expected"]["validation_status"]
    assert critique.status == case["expected"]["critique_status"]
    assert not validation.ready
    assert not critique.ready


def test_workflow_fixture_routes_shape_intent():
    case = _case("route_shape_intent")

    result = route_task(TaskRouteRequest(intent=case["intent"]))

    assert result.task == case["expected"]["task"]
    assert result.confidence >= case["expected"]["confidence_min"]
    assert result.provider_routing["selected"] is not None


def _case(name: str):
    return json.loads((FIXTURES / "workflow_cases.json").read_text(encoding="utf-8"))[name]
