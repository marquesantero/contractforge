import pytest

from contractforge_databricks.quality import (
    clear_quality_rule_registry,
    evaluate_custom_quality_rules,
    get_quality_rule,
    is_abort_only_failure,
    list_quality_rules,
    register_quality_rule,
    unregister_quality_rule,
)


def setup_function() -> None:
    clear_quality_rule_registry()


def teardown_function() -> None:
    clear_quality_rule_registry()


def test_register_and_evaluate_custom_quality_rule() -> None:
    def evaluator(df, rule_name, config):
        assert df == {"rows": 10}
        assert rule_name == "business_rule"
        assert config["threshold"] == 5
        return {"failed_count": 2, "details": {"threshold": 5}, "message": "too many bad rows"}

    register_quality_rule("threshold_check", evaluator)

    results = evaluate_custom_quality_rules(
        {"rows": 10},
        {"business_rule": {"type": "threshold_check", "threshold": 5, "severity": "quarantine"}},
    )

    assert len(results) == 1
    assert results[0].rule_name == "custom:business_rule"
    assert results[0].status == "FAILED"
    assert results[0].failed_count == 2
    assert results[0].severity == "quarantine"
    assert results[0].details == {"name": "business_rule", "type": "threshold_check", "threshold": 5}


def test_custom_quality_rule_warn_status() -> None:
    register_quality_rule("warning_check", lambda df, name, config: {"failed_count": 1})

    results = evaluate_custom_quality_rules(
        object(),
        {"warning_rule": {"type": "warning_check", "severity": "warn"}},
    )

    assert results[0].status == "WARNED"
    assert results[0].severity == "warn"


def test_custom_quality_rule_rejects_unregistered_type() -> None:
    with pytest.raises(ValueError, match="unregistered"):
        evaluate_custom_quality_rules(object(), {"x": {"type": "missing"}})


def test_register_quality_rule_requires_overwrite_for_existing_type() -> None:
    register_quality_rule("same", lambda df, name, config: {"failed_count": 0})

    with pytest.raises(ValueError, match="already registered"):
        register_quality_rule("same", lambda df, name, config: {"failed_count": 1})

    register_quality_rule("same", lambda df, name, config: {"failed_count": 1}, overwrite=True)
    assert evaluate_custom_quality_rules(object(), {"x": {"type": "same"}})[0].failed_count == 1


def test_quality_rule_registry_exposes_get_list_and_unregister() -> None:
    evaluator = lambda df, name, config: {"failed_count": 0}

    register_quality_rule("business_check", evaluator)

    assert get_quality_rule("business_check") is evaluator
    assert list_quality_rules() == ("business_check",)

    unregister_quality_rule("business_check")

    assert get_quality_rule("business_check") is None
    assert list_quality_rules() == ()


def test_is_abort_only_failure_matches_contractforge_names() -> None:
    assert is_abort_only_failure("required_columns") is True
    assert is_abort_only_failure("unique_key") is True
    assert is_abort_only_failure("min_rows") is True
    assert is_abort_only_failure("not_null:id") is False
