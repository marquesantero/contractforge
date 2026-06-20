from contractforge_core.execution import (
    ExecutionWindow,
    build_child_window_plan,
    build_time_windows,
    combine_filter,
    summarize_window_results,
)


def test_core_build_time_windows_from_iso_bounds() -> None:
    windows = build_time_windows("2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z", "1 day")

    assert len(windows) == 2
    assert windows[0].start == "2026-01-01 00:00:00"
    assert windows[0].end == "2026-01-02 00:00:00"
    assert windows[0].label == "2026-01-01T00:00:00__2026-01-02T00:00:00"


def test_core_build_child_window_plan_combines_filter_and_idempotency() -> None:
    child = build_child_window_plan(
        parent_run_id="parent-1",
        column="event_ts",
        window=ExecutionWindow("2026-01-01", "2026-01-02", "d1"),
        index=1,
        window_filter="event_ts >= '2026-01-01'",
        existing_filter="is_valid = true",
        base_idempotency_key="orders",
    )

    assert child.idempotency_key == "orders:window:d1"
    assert child.filter_expression == "(is_valid = true) AND event_ts >= '2026-01-01'"
    assert child.runtime_parameters["_contractforge_window_column"] == "event_ts"


def test_core_combine_filter_without_existing_filter() -> None:
    assert combine_filter(None, "x = 1") == "x = 1"


def test_core_summarize_window_results() -> None:
    summary = summarize_window_results(
        [
            {"status": "SUCCESS", "rows_read": 10, "rows_written": 8, "rows_quarantined": 2},
            {"status": "SKIPPED", "rows_read": 0, "rows_written": 0, "rows_quarantined": 0},
            {"status": "FAILED", "rows_read": 5, "rows_written": 0, "rows_quarantined": 1},
        ]
    )

    assert summary["status"] == "FAILED"
    assert summary["windows_total"] == 3
    assert summary["windows_succeeded"] == 2
    assert summary["rows_read"] == 15
