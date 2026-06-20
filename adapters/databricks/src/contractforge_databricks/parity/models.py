"""Compatibility exports for platform-neutral parity catalog models."""

from contractforge_core.parity import ParityExpectation, ParityMetricExpectation, WriteEngineParityScenario

RuntimeTarget = str

__all__ = ["ParityExpectation", "ParityMetricExpectation", "RuntimeTarget", "WriteEngineParityScenario"]
