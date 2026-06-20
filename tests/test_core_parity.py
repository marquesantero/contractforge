from contractforge_core.parity import ParityMetricExpectation, WriteEngineParityScenario


def test_core_parity_metric_expectation_serializes_optional_notes() -> None:
    assert ParityMetricExpectation("rows_inserted", "must match").as_dict() == {
        "metric": "rows_inserted",
        "expectation": "must match",
    }


def test_core_write_engine_parity_scenario_serializes_lists() -> None:
    scenario = WriteEngineParityScenario(
        scenario_id="s1",
        title="Scenario",
        write_mode="scd1_upsert",
        candidate_engine="engine",
        expectation="must_match",
        runtime_targets=("runtime",),
        required_capabilities=("merge",),
        required_contract_fields=("merge_keys",),
        expected_semantics=("one current row",),
        metric_expectations=(ParityMetricExpectation("rows_updated", "must match", "after dedupe"),),
        blockers_to_record=("none",),
    )

    payload = scenario.as_dict()

    assert payload["runtime_targets"] == ["runtime"]
    assert payload["metric_expectations"] == [
        {"metric": "rows_updated", "expectation": "must match", "notes": "after dedupe"}
    ]
