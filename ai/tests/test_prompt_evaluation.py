import pytest

from contractforge_ai.evaluation import (
    PromptEvalCase,
    evaluate_prompt_cases,
    get_prompt_template,
    list_prompt_templates,
    render_prompt,
)


def test_prompt_registry_contains_expected_templates():
    names = [template.name for template in list_prompt_templates()]

    assert names == [
        "adapter.validation.enrichment.v1",
        "explain.enrichment.v1",
        "metadata.enrichment.v1",
        "observability.enrichment.v1",
        "project.plan.enrichment.v1",
        "project.spec.enrichment.v1",
        "project.synthesis.enrichment.v1",
        "review.enrichment.v1",
    ]


def test_render_prompt_redacts_secret_values():
    _, prompt = render_prompt(
        "review.enrichment.v1",
        {
            "deterministic_result": {"status": "WARN"},
            "contract_excerpt": {"source": {"password": "plain-text-password", "token": "abc123"}},
        },
    )

    assert "[REDACTED]" in prompt
    assert "plain-text-password" not in prompt
    assert "abc123" not in prompt
    assert "<required_output_schema>" in prompt
    assert "<valid_output_example>" in prompt
    assert '"additionalProperties": false' in prompt
    assert "arrays of strings" in prompt
    assert "Do not copy the deterministic input object shape" in prompt


def test_system_prompt_preserves_core_adapter_boundaries():
    system, _ = render_prompt(
        "adapter.validation.enrichment.v1",
        {
            "adapter_validation": {"status": "NEEDS_DECISIONS", "findings": [{"code": "adapter.aws.warning"}]},
            "project_context": {"adapters": ["databricks", "aws"]},
            "user_intent": "Move AWS parameters into the ingestion contract.",
        },
    )

    assert "Core contract semantics, environment configuration and adapter runtime/deployment details are separate boundaries" in system
    assert "Do not move adapter-specific values into ingestion contracts" in system


def test_render_prompt_requires_variables():
    with pytest.raises(ValueError, match="Missing prompt variable"):
        render_prompt("review.enrichment.v1", {"deterministic_result": {}})


def test_default_prompt_evaluation_cases_pass():
    results = evaluate_prompt_cases()

    assert [result.status for result in results] == ["PASS", "PASS", "PASS", "PASS", "PASS", "PASS", "PASS", "PASS"]


def test_prompt_evaluation_detects_forbidden_fragments():
    results = evaluate_prompt_cases(
        [
            PromptEvalCase(
                name="unsafe-output",
                prompt="review.enrichment.v1",
                variables={
                    "deterministic_result": {"status": "WARN"},
                    "contract_excerpt": "leak-me",
                },
                forbidden_fragments=["leak-me"],
            )
        ]
    )

    assert results[0].status == "FAIL"
    assert results[0].findings[0].code == "prompt.forbidden_fragment_present"


def test_prompt_schema_requires_review_boundary():
    template = get_prompt_template("metadata.enrichment.v1")

    assert "review_required" in template.output_schema["required"]


def test_project_synthesis_prompt_uses_context_package():
    template = get_prompt_template("project.synthesis.enrichment.v1")
    system, prompt = render_prompt(
        "project.synthesis.enrichment.v1",
        {
            "context_package": {"files": [{"path": "orders.json"}]},
            "generated_project": {"report": {"decisions_required": ["confirm keys"]}},
            "user_intent": "Generate a complete project",
        },
    )

    assert "context-aware project synthesis" in system
    assert "<context_package>" in prompt
    assert "Do not remove required decisions" in prompt
    assert "project_synthesis" in prompt
    assert template.output_schema["additionalProperties"] is False


def test_adapter_validation_prompt_preserves_planning_boundary():
    template = get_prompt_template("adapter.validation.enrichment.v1")
    system, prompt = render_prompt(
        "adapter.validation.enrichment.v1",
        {
            "adapter_validation": {"status": "NEEDS_DECISIONS", "findings": [{"code": "adapter.aws.warning"}]},
            "project_context": {"adapters": ["databricks", "aws"]},
            "user_intent": "Mark everything ready.",
        },
    )

    assert "adapter planning validation explanation" in system
    assert "Adapter planning statuses are deterministic" in prompt
    assert "Do not convert warnings into READY" in prompt
    assert "adapter_validation" in prompt
    assert template.output_schema["additionalProperties"] is False
