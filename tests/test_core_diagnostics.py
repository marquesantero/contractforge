from contractforge_core.diagnostics import ExplainPlanRecord


def test_core_explain_plan_record() -> None:
    record = ExplainPlanRecord(
        run_id="run-1",
        target_table="main.silver.orders",
        source_name="source",
        mode="scd1_upsert",
        explain_format="formatted",
        plan_text="plan",
    )

    assert record.run_id == "run-1"
    assert record.plan_text == "plan"
