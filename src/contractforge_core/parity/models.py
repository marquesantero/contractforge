"""Platform-neutral parity catalog models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ParityExpectation = Literal["must_match", "intentional_difference", "unsupported"]


@dataclass(frozen=True)
class ParityMetricExpectation:
    metric: str
    expectation: str
    notes: str = ""

    def as_dict(self) -> dict[str, str]:
        payload = {"metric": self.metric, "expectation": self.expectation}
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True)
class WriteEngineParityScenario:
    scenario_id: str
    title: str
    write_mode: str
    candidate_engine: str
    expectation: ParityExpectation
    runtime_targets: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    required_contract_fields: tuple[str, ...]
    expected_semantics: tuple[str, ...]
    metric_expectations: tuple[ParityMetricExpectation, ...]
    blockers_to_record: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "write_mode": self.write_mode,
            "candidate_engine": self.candidate_engine,
            "expectation": self.expectation,
            "runtime_targets": list(self.runtime_targets),
            "required_capabilities": list(self.required_capabilities),
            "required_contract_fields": list(self.required_contract_fields),
            "expected_semantics": list(self.expected_semantics),
            "metric_expectations": [metric.as_dict() for metric in self.metric_expectations],
            "blockers_to_record": list(self.blockers_to_record),
            "notes": self.notes,
        }
