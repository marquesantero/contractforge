import json

from contractforge_ai.enrichment import EnrichmentResult
from contractforge_ai.observability import analyze_control_tables
from contractforge_ai.providers import GenerationOptions
from contractforge_ai.reports import (
    _compact_review_decision_rows,
    _code_if_path,
    render_markdown_report,
    render_operational_analysis_review,
)
from contractforge_ai.reports_translation import translate_report


class TranslationProvider:
    name = "fake"

    def __init__(self):
        self.requests: list[dict[str, object]] = []

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        self.requests.append({"prompt": prompt, "system": system, "options": options})
        payload = json.loads(prompt.rsplit("Translate the text values in this JSON payload:", 1)[-1])
        return json.dumps(
            {
                "translations": [
                    {"id": item["id"], "text": f"TRADUZIDO: {item['text']}"}
                    for item in payload["segments"]
                ]
            }
        )


def test_markdown_report_renders_self_contained_html():
    report = render_markdown_report("# Review\n\n- Status: `READY`\n", title="Review")

    assert report.markdown.startswith("# Review")
    assert "<!doctype html>" in report.html
    assert "<code>READY</code>" in report.html


def test_operational_report_includes_ai_guidance():
    analysis = analyze_control_tables(
        {
            "runs": [
                {
                    "run_id": "r1",
                    "target_table": "main.silver.orders",
                    "status": "FAILED",
                    "error_message": "Unauthorized access to external location.",
                }
            ]
        }
    )
    enrichment = EnrichmentResult(
        status="ENRICHED",
        prompt="observability.enrichment.v1",
        provider="openai",
        data={
            "summary": "Investigate serverless external location access.",
            "recommendations": ["Check Unity Catalog grants."],
            "evidence": ["The run failed with unauthorized access."],
            "confidence": 0.8,
            "review_required": True,
        },
    )

    report = render_operational_analysis_review(analysis, enrichment=enrichment)

    assert "AI Guidance" in report.markdown
    assert "Check Unity Catalog grants." in report.markdown
    assert "ContractForge AI Operational Review" in report.html
    assert '<section class="hero">' in report.html
    assert '<section class="grid">' in report.html
    assert "Operational Metrics" in report.html
    assert "Run Status Counts" in report.html
    assert "Findings" in report.html
    assert "AI Guidance" in report.html
    assert "Provider:" not in report.html
    assert "Check Unity Catalog grants." in report.html


def test_review_decision_rows_group_repeated_project_level_messages():
    rows = _compact_review_decision_rows(
        [
            "Project still has required decisions",
            "Project still has required decisions",
            "environments/fabric.environment.yaml.parameters.fabric: Project still has required decisions",
            "environments/fabric.environment.yaml.runtime: Project still has required decisions",
            "Project warning remains",
            "Project warning remains",
            "source.path: Review placeholder remains",
            "source.format: Review placeholder remains",
        ]
    )

    assert rows == [
        [
            "Project still has required decisions",
            4,
            "project; environments/fabric.environment.yaml.parameters.fabric; environments/fabric.environment.yaml.runtime",
        ],
        ["Project warning remains", 2, "project"],
        ["Review placeholder remains", 2, "source.path; source.format"],
    ]


def test_review_decision_rows_preserve_colons_in_non_scope_messages():
    rows = _compact_review_decision_rows(
        [
            "Review source URL: confirm credentials are not embedded",
            "Review source URL: confirm credentials are not embedded",
        ]
    )

    assert rows == [["Review source URL: confirm credentials are not embedded", 2, "project"]]


def test_code_if_path_does_not_wrap_scope_summaries_as_one_code_chip():
    assert _code_if_path("contracts/databricks/bronze.yaml") == "<code>contracts/databricks/bronze.yaml</code>"
    assert (
        _code_if_path("project; environments/fabric.environment.yaml.runtime")
        == "project; environments/fabric.environment.yaml.runtime"
    )


def test_report_translation_uses_provider_after_english_rendering():
    provider = TranslationProvider()
    report = render_markdown_report(
        "# Review\n\n- Status: `READY`\n\nNarrative sentence.\n\n| Value |\n| --- |\n| review_required |\n| total_amount |",
        title="Review",
    )

    translated = translate_report(report, language="pt-BR", provider=provider)

    assert "TRADUZIDO: Narrative sentence." in translated.markdown
    assert "TRADUZIDO: Narrative sentence." in translated.html
    assert "Status: `READY`" in translated.markdown
    assert "<code>READY</code>" in translated.html
    assert "TRADUZIDO: review_required" not in translated.html
    assert "TRADUZIDO: total_amount" not in translated.html
    assert "| review_required |" in translated.html
    assert "| total_amount |" in translated.html
    assert len(provider.requests) == 2
    assert "Target language: pt-BR" in provider.requests[0]["prompt"]
    assert "Translate only the provided narrative text segments" in provider.requests[0]["system"]
    assert "Return JSON only" in provider.requests[0]["system"]
    assert "Status: `READY`" not in provider.requests[0]["prompt"]


def test_report_translation_translates_narrative_with_inline_code():
    provider = TranslationProvider()
    report = render_markdown_report(
        (
            "# Review\n\n"
            "The target table is `main.silver.s_orders`, the source connector is `s3`, "
            "and the intended write mode is `scd1_hash_diff`.\n\n"
            "`main.silver.s_orders`\n"
        ),
        title="Review",
    )

    translated = translate_report(report, language="pt-BR", provider=provider)

    assert (
        "TRADUZIDO: The target table is `main.silver.s_orders`, the source connector is `s3`, "
        "and the intended write mode is `scd1_hash_diff`."
    ) in translated.markdown
    assert "`main.silver.s_orders`" in translated.markdown
    assert "TRADUZIDO: `main.silver.s_orders`" not in translated.markdown
