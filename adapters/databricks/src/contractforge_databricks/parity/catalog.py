"""Query helpers for the Databricks parity catalog."""

from __future__ import annotations

from typing import Any

from contractforge_core.parity import WriteEngineParityScenario
from contractforge_databricks.parity.scenarios import WRITE_ENGINE_PARITY_SCENARIOS


def list_write_engine_parity_scenarios() -> list[str]:
    return sorted(scenario.scenario_id for scenario in WRITE_ENGINE_PARITY_SCENARIOS)


def get_write_engine_parity_scenario(scenario_id: str) -> WriteEngineParityScenario:
    for scenario in WRITE_ENGINE_PARITY_SCENARIOS:
        if scenario.scenario_id == scenario_id:
            return scenario
    raise ValueError(
        f"Write-engine parity scenario not found: {scenario_id}. "
        f"Valid scenarios: {list_write_engine_parity_scenarios()}"
    )


def scenarios_for_engine(engine: str) -> list[WriteEngineParityScenario]:
    return [scenario for scenario in WRITE_ENGINE_PARITY_SCENARIOS if scenario.candidate_engine == engine]


def scenarios_for_mode(mode: str) -> list[WriteEngineParityScenario]:
    return [scenario for scenario in WRITE_ENGINE_PARITY_SCENARIOS if scenario.write_mode == mode]


def build_write_engine_parity_plan(
    *,
    engine: str | None = None,
    mode: str | None = None,
    runtime: str | None = None,
) -> dict[str, Any]:
    scenarios = list(WRITE_ENGINE_PARITY_SCENARIOS)
    if engine:
        scenarios = [scenario for scenario in scenarios if scenario.candidate_engine == engine]
    if mode:
        scenarios = [scenario for scenario in scenarios if scenario.write_mode == mode]
    if runtime:
        scenarios = [scenario for scenario in scenarios if runtime in scenario.runtime_targets]

    expectation_counts: dict[str, int] = {}
    for scenario in scenarios:
        expectation_counts[scenario.expectation] = expectation_counts.get(scenario.expectation, 0) + 1

    return {
        "kind": "write_engine_parity_plan",
        "engine": engine,
        "mode": mode,
        "runtime": runtime,
        "scenario_count": len(scenarios),
        "expectation_counts": expectation_counts,
        "scenarios": [scenario.as_dict() for scenario in scenarios],
    }
