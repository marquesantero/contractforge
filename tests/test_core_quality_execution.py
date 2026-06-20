from contractforge_core.execution import ExecutionOutcome
from contractforge_core.quality import (
    QualityRuleResult,
    quality_policy_status,
    quality_status,
    quarantinable_results,
)


def test_core_quality_status_and_quarantine_selection() -> None:
    results = (
        QualityRuleResult("warn_rule", "WARNED", failed_count=1, severity="warn"),
        QualityRuleResult("quarantine_rule", "FAILED", failed_count=2, severity="quarantine"),
    )

    assert quality_status(()) == "NOT_CONFIGURED"
    assert quality_status((QualityRuleResult("ok", "PASSED"),)) == "PASSED"
    assert quality_status((results[0],)) == "WARNED"
    assert quality_status(results) == "FAILED"
    assert quarantinable_results(results) == (results[1],)


def test_quality_policy_status_reports_quarantined_under_quarantine_policy() -> None:
    quarantine_failures = (
        QualityRuleResult("warn_rule", "WARNED", failed_count=1, severity="warn"),
        QualityRuleResult("quar_rule", "FAILED", failed_count=2, severity="quarantine"),
    )

    # Under the quarantine policy the offending rows were removed cleanly.
    assert quality_policy_status(quarantine_failures, on_quality_fail="quarantine") == "QUARANTINED"
    # Under the fail policy the run would have aborted; surface FAILED to keep dashboards loud.
    assert quality_policy_status(quarantine_failures, on_quality_fail="fail") == "FAILED"
    # An abort-severity failure is never quarantinable, even under quarantine policy.
    abort_failures = quarantine_failures + (
        QualityRuleResult("abort_rule", "FAILED", failed_count=1, severity="abort"),
    )
    assert quality_policy_status(abort_failures, on_quality_fail="quarantine") == "FAILED"
    # PASSED / WARNED short-circuit the policy lookup.
    assert quality_policy_status((QualityRuleResult("ok", "PASSED"),), on_quality_fail="quarantine") == "PASSED"
    assert (
        quality_policy_status(
            (QualityRuleResult("warn_only", "WARNED", failed_count=1, severity="warn"),),
            on_quality_fail="quarantine",
        )
        == "WARNED"
    )


def test_core_execution_outcome_is_platform_neutral() -> None:
    outcome = ExecutionOutcome(
        status="SUCCESS",
        operation="merge",
        target="catalog.schema.table",
        metrics={"rows_written": 10},
    )

    assert outcome.status == "SUCCESS"
    assert outcome.metrics["rows_written"] == 10
