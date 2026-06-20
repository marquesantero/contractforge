from contractforge_ai.models import Assumption, EvidenceItem, RequiredDecision, Traceability, confidence_level


def test_confidence_level_buckets_are_stable():
    assert confidence_level(0.81) == "high"
    assert confidence_level(0.55) == "medium"
    assert confidence_level(0.54) == "low"


def test_traceability_serializes_evidence_assumptions_and_decisions():
    traceability = Traceability(
        confidence=0.72,
        evidence=[
            EvidenceItem(
                source="schema",
                path="columns.customer_id",
                reason="Column is marked nullable=false.",
                value=False,
                confidence=0.92,
            )
        ],
        assumptions=[
            Assumption(
                statement="First not_null column may be the merge key.",
                confidence=0.60,
                review_required=True,
            )
        ],
        decisions_required=[
            RequiredDecision(
                question="Confirm merge_keys",
                reason="Merge keys are business decisions.",
                path="merge_keys",
                options=["customer_id", "order_id"],
            )
        ],
    )

    payload = traceability.to_dict()

    assert payload["confidence_level"] == "medium"
    assert payload["review_required"] is True
    assert payload["evidence"][0]["source"] == "schema"
    assert payload["assumptions"][0]["confidence_level"] == "medium"
    assert payload["decisions_required"][0]["options"] == ["customer_id", "order_id"]


def test_traceability_markdown_is_human_readable():
    traceability = Traceability(
        confidence=0.90,
        evidence=[EvidenceItem(source="contract", path="target.table", reason="Target table exists.")],
    )

    markdown = traceability.to_markdown()

    assert "## Traceability" in markdown
    assert "Confidence: **high**" in markdown
    assert "**contract** `target.table`" in markdown
