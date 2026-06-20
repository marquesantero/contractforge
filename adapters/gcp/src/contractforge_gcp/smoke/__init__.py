"""GCP adapter smoke workflows."""

from importlib import import_module
from typing import Any

from contractforge_gcp.smoke.workflow import (
    GCPContractSmokeResult,
    GCPSmokeOperation,
    run_gcp_contract_smoke,
    smoke_result_json,
)

__all__ = [
    "GCPContractSmokeResult",
    "GCPProjectSmokeResult",
    "GCPProjectSmokeStepResult",
    "GCPSmokeOperation",
    "project_smoke_result_json",
    "run_gcp_contract_smoke",
    "run_gcp_project_smoke",
    "smoke_result_json",
]


def __getattr__(name: str) -> Any:
    if name in {
        "GCPProjectSmokeResult",
        "GCPProjectSmokeStepResult",
        "project_smoke_result_json",
        "run_gcp_project_smoke",
    }:
        project = import_module("contractforge_gcp.smoke.project")
        return getattr(project, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
