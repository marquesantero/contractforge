from contractforge_core.quality import ABORT_ONLY_RULES, is_abort_only_failure


def test_core_quality_abort_only_semantics_are_platform_neutral() -> None:
    assert {"required_columns", "unique_key", "min_rows", "row_count_minimum"} <= ABORT_ONLY_RULES
    assert is_abort_only_failure("required_columns")
    assert is_abort_only_failure("row_count_minimum")
    assert is_abort_only_failure("not_null:id") is False
    assert is_abort_only_failure("accepted_values:status") is False
