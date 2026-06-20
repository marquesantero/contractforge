import json

from contractforge_ai.evaluation import evaluate_provider
from contractforge_ai.providers import GenerationOptions, ProviderExecutionError
from contractforge_ai.providers.offline import OfflineProvider


class SchemaAwareProvider:
    name = "fake"

    def __init__(self):
        self.requests = []

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        self.requests.append({"prompt": prompt, "system": system, "options": options})
        kind = options.response_schema["properties"]["kind"]["const"]
        return json.dumps(
            {
                "kind": kind,
                "summary": f"{kind} summary grounded in deterministic evidence.",
                "recommendations": ["Preserve the deterministic review boundary."],
                "evidence": ["The deterministic input contains reviewable evidence."],
                "assumptions": ["This is a provider evaluation fixture."],
                "decisions_required": ["Review generated output before production use."],
                "confidence": 0.82,
                "review_required": True,
            }
        )


class InvalidProvider:
    name = "fake"

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        del prompt, system, options
        return '{"kind": "review"}'


class ErrorProvider:
    name = "fake"

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        del prompt, system, options
        raise ProviderExecutionError("provider unavailable")


def test_evaluate_provider_passes_schema_aware_provider():
    provider = SchemaAwareProvider()

    report = evaluate_provider(provider, prompts=["review.enrichment.v1", "project.plan.enrichment.v1"])

    assert report.status == "PASS"
    assert report.provider == "fake"
    assert report.capability is None
    assert len(report.prompt_results) == 2
    assert all(result.structured_output_status == "PASS" for result in report.prompt_results)
    assert all(result.enrichment_quality_status == "PASS" for result in report.prompt_results)
    assert provider.requests[0]["options"].response_schema_name == "review_enrichment_v1"


def test_evaluate_provider_reports_structured_output_failures():
    report = evaluate_provider(InvalidProvider(), prompts=["review.enrichment.v1"])

    assert report.status == "FAIL"
    assert report.prompt_results[0].status == "FAIL"
    assert report.prompt_results[0].structured_output_status == "FAIL"
    assert any(finding.code == "structured_output.required_missing" for finding in report.prompt_results[0].findings)


def test_evaluate_provider_reports_execution_errors():
    report = evaluate_provider(ErrorProvider(), prompts=["review.enrichment.v1"])

    assert report.status == "FAIL"
    assert report.prompt_results[0].status == "FAIL"
    assert report.prompt_results[0].findings[0].code == "provider.execution_failed"
    assert "provider unavailable" in report.prompt_results[0].findings[0].message


def test_evaluate_provider_skips_offline_provider():
    report = evaluate_provider(OfflineProvider())

    assert report.status == "SKIPPED"
    assert report.provider == "offline"
    assert report.capability["name"] == "offline"
    assert report.prompt_results[0].findings[0].code == "provider.offline"
