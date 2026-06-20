from contractforge_ai.models import Finding, ReviewResult
from contractforge_ai.reviewers.output import review_to_markdown, should_fail_review


def _review_result() -> ReviewResult:
    return ReviewResult(
        status="WARN",
        risk="high",
        contract_path="contracts/orders.yaml",
        summary="WARN: 1 finding.",
        findings=[
            Finding(
                code="write.keys.nullable",
                severity="high",
                title="Merge keys are not protected",
                detail="order_id is not covered by not_null.",
                recommendation="Add order_id to quality_rules.not_null.",
                path="quality_rules.not_null",
            )
        ],
    )


def test_review_to_markdown_renders_pr_friendly_report():
    markdown = review_to_markdown(_review_result())

    assert "## ContractForge AI Review" in markdown
    assert "| Severity | Code | Location | Recommendation |" in markdown
    assert "`write.keys.nullable`" in markdown
    assert "Add order_id to quality_rules.not_null." in markdown


def test_should_fail_review_by_severity():
    result = _review_result()

    assert should_fail_review(result, fail_on="high") is True
    assert should_fail_review(result, fail_on="critical") is False
    assert should_fail_review(result, fail_on="none") is False


def test_should_fail_review_by_code():
    result = _review_result()

    assert should_fail_review(result, fail_on="none", fail_on_codes=["write.keys.nullable"]) is True
    assert should_fail_review(result, fail_on="none", fail_on_codes=["other.code"]) is False
