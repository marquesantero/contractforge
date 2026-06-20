from contractforge_ai.intelligence import critique_output
from contractforge_ai.validation import validate_contract_artifact


def test_critique_passes_evidence_bound_output_with_ready_validation():
    validation = validate_contract_artifact(
        {
            "_metadata": {"draft": True, "review_required": True},
            "source": {"type": "connector", "connector": "files", "path": "/landing/orders"},
            "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
            "mode": "scd0_append",
            "operations": {"technical_owner": "data-engineering"},
        },
        use_contractforge=False,
    )

    report = critique_output(
        {
            "kind": "project_plan",
            "summary": "Reviewable draft for bronze file ingestion.",
            "recommendations": ["Run deterministic validation before deployment."],
            "evidence": ["Contract validation returned READY."],
            "assumptions": [],
            "decisions_required": [],
            "confidence": 0.82,
            "review_required": False,
        },
        validation=validation,
        context_results=[{"source_path": "docs/contracts.md"}],
    )

    assert report.status == "READY"
    assert report.ready is True
    assert report.confidence >= 0.8


def test_critique_downgrades_ready_claim_when_validation_is_invalid():
    validation = validate_contract_artifact({"mode": "scd1_hash_diff"}, use_contractforge=False)

    report = critique_output(
        {
            "kind": "project_plan",
            "summary": "This output is production-ready and safe to deploy.",
            "recommendations": ["Deploy it."],
            "evidence": ["The model says it is complete."],
            "decisions_required": [],
            "review_required": False,
        },
        validation=validation,
    )

    assert report.status == "INVALID"
    assert any(finding.code == "critique.validation_failure_hidden" for finding in report.findings)
    assert report.confidence <= 0.4


def test_critique_requires_decisions_for_low_evidence_output():
    report = critique_output(
        {
            "kind": "project_plan",
            "summary": "Use scd1_hash_diff for this project.",
            "recommendations": ["Add merge keys.", "Add watermarking.", "Use serverless."],
            "evidence": [],
            "decisions_required": ["Confirm merge keys."],
            "review_required": True,
        }
    )

    assert report.status == "NEEDS_DECISIONS"
    assert any(finding.code == "critique.evidence_coverage.low" for finding in report.findings)
    assert "Confirm merge keys." in report.decisions_required


def test_critique_detects_metadata_inside_shape_boundary():
    report = critique_output(
        {
            "kind": "shape",
            "summary": "Shape draft.",
            "shape": {"select": [{"source": "email", "target": "email", "pii": True}]},
            "evidence": ["Sample payload contains email."],
            "decisions_required": [],
            "review_required": True,
        }
    )

    assert report.status == "NEEDS_DECISIONS"
    assert any(finding.code == "critique.boundary.metadata_transform_mix" for finding in report.findings)
