"""Markdown review report renderer."""

from __future__ import annotations

from contractforge_core.planner import PlanningResult
from contractforge_core.security import redact_value
from contractforge_core.semantic import SemanticContract
from contractforge_databricks.capabilities.models import DatabricksCapabilities
from contractforge_databricks.contract_extensions import databricks_extensions
from contractforge_databricks.rendering.names import plan_title, target_full_name


def render_review_markdown(
    contract: SemanticContract,
    planning: PlanningResult,
    capabilities: DatabricksCapabilities,
) -> str:
    lines = [
        f"# {plan_title(planning.plan) if planning.plan else 'ContractForge Databricks planning review'}",
        "",
        f"- Status: `{planning.status}`",
        f"- Target: `{target_full_name(contract)}`",
        f"- Write mode: `{contract.write.mode}`",
        f"- Runtime kind: `{capabilities.runtime_kind}`",
        "",
        "## Plan Steps",
        "",
    ]
    if planning.plan:
        lines.extend(f"- `{step.name}`: {step.intent}" for step in planning.plan.steps)
    else:
        lines.append("- No executable abstract plan was produced.")

    if planning.blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker.code}`: {blocker.message}" for blocker in planning.blockers)

    if planning.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning.code}`: {warning.message}" for warning in planning.warnings)

    extensions = databricks_extensions(contract)
    if extensions:
        lines.extend(["", "## Databricks Extensions", ""])
        lines.extend(f"- `{name}`: `{redact_value(extensions[name])}`" for name in sorted(extensions))

    lines.extend(["", "## Databricks Capability Evidence", ""])
    for name, capability in sorted(capabilities.capabilities.items()):
        lines.append(f"- `{name}`: `{capability.status}` - {capability.reason}")
    return "\n".join(lines) + "\n"
