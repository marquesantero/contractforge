"""Platform-neutral execution result models."""

from contractforge_core.execution.results import ExecutionOutcome, ExecutionStatus
from contractforge_core.execution.strategy import WriteStrategy
from contractforge_core.execution.write_modes import canonical_custom_write_mode, write_strategy_label
from contractforge_core.execution.windows import (
    ChildWindowPlan,
    ExecutionWindow,
    build_child_window_plan,
    build_time_windows,
    combine_filter,
    summarize_window_results,
)

__all__ = [
    "ChildWindowPlan",
    "ExecutionOutcome",
    "ExecutionStatus",
    "ExecutionWindow",
    "WriteStrategy",
    "build_child_window_plan",
    "build_time_windows",
    "canonical_custom_write_mode",
    "combine_filter",
    "write_strategy_label",
    "summarize_window_results",
]
