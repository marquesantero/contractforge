"""GCP deployment artifact helpers."""

from importlib import import_module
from typing import Any

from contractforge_gcp.deployment.manifest import render_gcp_deployment_manifest
from contractforge_gcp.deployment.workflows import (
    GCPWorkflowOperation,
    GCPWorkflowReadbackTarget,
    render_gcp_workflows_cleanup_plan,
    render_gcp_workflows_evidence_readback_plan,
    render_gcp_workflows_execution_plan,
    render_gcp_workflows_runner_manifest,
    render_gcp_workflows_runner_yaml,
    workflow_name,
)
from contractforge_gcp.deployment.workflows_runtime import run_gcp_workflows_orchestration

__all__ = [
    "GCPProjectDeployment",
    "GCPProjectDeploymentStep",
    "GCPWorkflowOperation",
    "GCPWorkflowReadbackTarget",
    "deploy_gcp_project",
    "project_deployment_json",
    "render_gcp_deployment_manifest",
    "render_gcp_project_deployment_manifest",
    "render_gcp_workflows_cleanup_plan",
    "render_gcp_workflows_evidence_readback_plan",
    "render_gcp_workflows_execution_plan",
    "render_gcp_workflows_runner_manifest",
    "render_gcp_workflows_runner_yaml",
    "run_gcp_workflows_orchestration",
    "workflow_name",
]


def __getattr__(name: str) -> Any:
    if name in {
        "GCPProjectDeployment",
        "GCPProjectDeploymentStep",
        "deploy_gcp_project",
        "project_deployment_json",
        "render_gcp_project_deployment_manifest",
    }:
        project = import_module("contractforge_gcp.deployment.project")
        return getattr(project, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
