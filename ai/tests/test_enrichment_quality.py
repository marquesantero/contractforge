from contractforge_ai.evaluation import evaluate_enrichment_quality


def _deterministic_with_decisions():
    return {
        "status": "NEEDS_DECISIONS",
        "decisions_required": [
            {"question": "Confirm merge keys.", "path": "merge_keys"},
        ],
    }


def test_evaluate_enrichment_quality_passes_preserved_boundary():
    report = evaluate_enrichment_quality(
        _deterministic_with_decisions(),
        {
            "status": "ENRICHED",
            "provider": "fake",
            "data": {
                "kind": "project_plan",
                "summary": "Use ContractForge YAML and review merge keys before generation.",
                "recommendations": ["Keep merge key review as a required decision."],
                "evidence": ["Deterministic status NEEDS_DECISIONS."],
                "decisions_required": ["Confirm merge keys."],
                "confidence": 0.82,
                "review_required": True,
            },
        },
        expected_kind="project_plan",
    )

    assert report.status == "PASS"
    assert report.score == 1.0


def test_evaluate_enrichment_quality_fails_hidden_decisions():
    report = evaluate_enrichment_quality(
        _deterministic_with_decisions(),
        {
            "status": "ENRICHED",
            "provider": "fake",
            "data": {
                "kind": "project_plan",
                "summary": "The project is ready.",
                "recommendations": ["Generate files now."],
                "evidence": ["Planner output."],
                "decisions_required": [],
                "confidence": 0.9,
                "review_required": False,
            },
        },
        expected_kind="project_plan",
    )

    assert report.status == "FAIL"
    assert any(finding.code == "enrichment.review_boundary_removed" for finding in report.findings)
    assert any(finding.code == "enrichment.decisions_hidden" for finding in report.findings)


def test_evaluate_enrichment_quality_fails_review_readiness_claim():
    report = evaluate_enrichment_quality(
        _deterministic_with_decisions(),
        {
            "status": "ENRICHED",
            "provider": "fake",
            "data": {
                "kind": "project_plan",
                "summary": "The project is ready after this review.",
                "recommendations": ["Deploy the generated files after checking the branch."],
                "evidence": ["Planner output still needs merge keys."],
                "decisions_required": ["Confirm merge keys."],
                "confidence": 0.86,
                "review_required": True,
            },
        },
        expected_kind="project_plan",
    )

    assert report.status == "FAIL"
    assert any(finding.code == "enrichment.review_readiness_claim" for finding in report.findings)


def test_evaluate_enrichment_quality_fails_blocking_readiness_claim():
    report = evaluate_enrichment_quality(
        {"status": "INVALID"},
        {
            "status": "ENRICHED",
            "provider": "fake",
            "data": {
                "kind": "review",
                "summary": "Ready to publish.",
                "recommendations": ["Proceed with deployment."],
                "evidence": ["Provider ignored deterministic invalid status."],
                "decisions_required": [],
                "confidence": 0.86,
                "review_required": True,
            },
        },
        expected_kind="review",
    )

    assert report.status == "FAIL"
    assert any(finding.code == "enrichment.blocking_readiness_claim" for finding in report.findings)


def test_evaluate_enrichment_quality_fails_missing_evidence():
    report = evaluate_enrichment_quality(
        {"status": "PASS"},
        {
            "status": "ENRICHED",
            "provider": "fake",
            "data": {
                "kind": "review",
                "summary": "Looks fine.",
                "recommendations": ["Proceed."],
                "evidence": [],
                "confidence": 0.75,
                "review_required": True,
            },
        },
        expected_kind="review",
    )

    assert report.status == "FAIL"
    assert any(finding.code == "enrichment.evidence_missing" for finding in report.findings)


def test_evaluate_enrichment_quality_warns_when_skipped():
    report = evaluate_enrichment_quality(
        {"status": "PASS"},
        {
            "ai_enrichment": {
                "status": "SKIPPED",
                "provider": "offline",
                "warnings": ["No provider configured."],
            }
        },
    )

    assert report.status == "WARN"
    assert any(finding.code == "enrichment.skipped" for finding in report.findings)


def test_evaluate_enrichment_quality_fails_secret_like_data():
    report = evaluate_enrichment_quality(
        {"status": "PASS"},
        {
            "status": "ENRICHED",
            "provider": "fake",
            "data": {
                "kind": "review",
                "summary": "Contains unsafe detail.",
                "recommendations": ["Rotate token=secret-token."],
                "evidence": ["token=secret-token"],
                "confidence": 0.75,
                "review_required": True,
            },
        },
        expected_kind="review",
    )

    assert report.status == "FAIL"
    assert any(finding.code == "enrichment.secret_leak" for finding in report.findings)
