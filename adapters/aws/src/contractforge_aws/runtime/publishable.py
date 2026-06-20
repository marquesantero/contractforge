"""Assemble AWS artifacts that should be published for runtime use."""

from __future__ import annotations

import json
from typing import Any

from contractforge_core.adapters import RenderedArtifacts
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_aws.environment import AWSEnvironment
from contractforge_aws.rendering.names import artifact_prefix


def publishable_artifacts(
    contract: dict[str, Any],
    rendered: RenderedArtifacts,
    *,
    environment: dict[str, Any] | None,
    extra_artifacts: dict[str, str] | None,
) -> RenderedArtifacts:
    artifacts = dict(rendered.artifacts)
    env = AWSEnvironment.from_contract(environment)
    options = env.artifact_options or {}
    artifacts.update(runtime_contract_artifacts(contract, environment=environment, rendered=rendered))
    if options.get("include_normalized_contract"):
        artifacts[f"normalized/{artifact_name_prefix(rendered)}.contract.json"] = (
            json.dumps(contract, indent=2, sort_keys=True, default=str) + "\n"
        )
    artifacts.update(extra_artifacts or {})
    return RenderedArtifacts(artifacts=artifacts)


def runtime_contract_artifacts(
    contract: dict[str, Any],
    *,
    environment: dict[str, Any] | None,
    rendered: RenderedArtifacts,
) -> dict[str, str]:
    prefix = artifact_name_prefix(rendered)
    if prefix == "contract":
        prefix = artifact_prefix(semantic_contract_from_mapping(contract))
    artifacts = {f"runtime/{prefix}.contract.json": json.dumps(contract, indent=2, sort_keys=True, default=str) + "\n"}
    if environment is not None:
        artifacts[f"runtime/{prefix}.environment.json"] = (
            json.dumps(environment, indent=2, sort_keys=True, default=str) + "\n"
        )
    return artifacts


def artifact_name_prefix(rendered: RenderedArtifacts) -> str:
    for name in sorted(rendered.artifacts):
        if name.endswith(".glue_job_definition.json"):
            return name[: -len(".glue_job_definition.json")]
    for name in sorted(rendered.artifacts):
        if name.endswith(".glue_job.py"):
            return name[: -len(".glue_job.py")]
    return "contract"


__all__ = ["artifact_name_prefix", "publishable_artifacts", "runtime_contract_artifacts"]
