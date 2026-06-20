from contractforge_core.results import GovernanceApplyResult, OperationsRecordResult


def test_core_governance_apply_result_defaults() -> None:
    result = GovernanceApplyResult(status="NOT_CONFIGURED")

    assert result.applied == 0
    assert result.failed == 0
    assert result.sql_preview == ()


def test_core_governance_apply_result_can_carry_preview_and_errors() -> None:
    result = GovernanceApplyResult(status="WARNED", applied=1, failed=1, sql_preview=("grant select",), errors=("denied",))

    assert result.status == "WARNED"
    assert result.sql_preview == ("grant select",)
    assert result.errors == ("denied",)


def test_core_operations_record_result() -> None:
    result = OperationsRecordResult(status="FAILED", sql="insert", error="denied")

    assert result.status == "FAILED"
    assert result.sql == "insert"
    assert result.error == "denied"
