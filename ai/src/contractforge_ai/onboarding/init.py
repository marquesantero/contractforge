"""Onboarding project plan generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import yaml

from contractforge_ai.models import Assumption, RequiredDecision, Traceability
from contractforge_ai.onboarding.discovery import EnvironmentReport, discover_environment
from contractforge_ai.onboarding.provider_credentials import provider_credentials
from contractforge_ai.onboarding.profiles import IntegrationProfileName, get_integration_profile
from contractforge_ai.projects import DecisionReport, ProjectArtifact, ProjectPlan

ProviderMode = Literal["deterministic", "provider-enriched"]


@dataclass(frozen=True)
class OnboardingInitRequest:
    """Inputs for generating onboarding configuration artifacts."""

    profile: str = "local-cli"
    provider_mode: ProviderMode = "deterministic"
    provider: str | None = None
    model: str | None = None
    catalog: str | None = None
    ctrl_schema: str | None = None
    workspace_profile: str | None = None
    instruction_path: str | None = None
    tool_boundary: str | None = None

    def profile_config(self) -> dict[str, Any]:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "catalog": self.catalog,
            "ctrl_schema": self.ctrl_schema,
            "workspace_profile": self.workspace_profile,
            "instruction_path": self.instruction_path,
            "tool_boundary": self.tool_boundary,
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}


def build_onboarding_plan(
    request: OnboardingInitRequest,
    *,
    environment: EnvironmentReport | None = None,
) -> ProjectPlan:
    """Build a safe onboarding plan without writing files."""

    profile = get_integration_profile(request.profile)
    env_report = environment or discover_environment()
    profile_validation = profile.validate_config(request.profile_config())
    config = _config_payload(request, profile.name)
    warnings = list(env_report.warnings) + list(profile_validation.warnings)
    if profile_validation.missing_required:
        warnings.append(f"Missing required profile config: {', '.join(profile_validation.missing_required)}.")
    if request.provider_mode == "provider-enriched" and not request.provider:
        warnings.append("Provider-enriched mode was selected but no provider was configured.")
    if request.provider and not request.model:
        warnings.append("A provider was configured without an explicit model.")

    report = DecisionReport(
        title="ContractForge AI Onboarding Report",
        summary=f"Generated onboarding configuration for the `{profile.name}` integration profile.",
        assumptions=[
            Assumption(
                statement="Generated files are setup drafts and must be reviewed before being used in shared automation.",
                confidence=0.95,
                review_required=True,
            ),
            Assumption(
                statement="Secret values are provided through environment variables, Databricks secrets or CI secret stores.",
                confidence=0.95,
                review_required=False,
            ),
        ],
        decisions_required=_decisions_required(request, profile.name, profile_validation.missing_required),
        warnings=warnings,
    )
    artifacts = [
        ProjectArtifact(
            path="contractforge-ai.yaml",
            kind="config",
            description="ContractForge AI onboarding configuration.",
            content=yaml.safe_dump(config, sort_keys=False),
        ),
        ProjectArtifact(
            path="SETUP_REPORT.md",
            kind="markdown",
            description="Reviewable onboarding report.",
            content=_setup_report_markdown(
                request=request,
                profile_name=profile.name,
                profile_description=profile.description,
                config=config,
                environment=env_report,
                report=report,
            ),
        ),
    ]
    return ProjectPlan(
        name=f"contractforge-ai-{profile.name}-onboarding",
        target="contractforge-ai-onboarding",
        artifacts=artifacts,
        report=report,
        traceability=Traceability(
            confidence=0.9,
            assumptions=report.assumptions,
            decisions_required=report.decisions_required,
            review_required=bool(report.decisions_required),
        ),
    )


def _config_payload(request: OnboardingInitRequest, profile_name: IntegrationProfileName) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "profile": profile_name,
        "mode": request.provider_mode,
        "validation": {
            "deterministic_first": True,
            "redact_secrets": True,
            "review_required": True,
        },
    }
    if request.provider_mode == "provider-enriched" or request.provider or request.model:
        payload["provider"] = {
            "name": request.provider,
            "model": request.model,
            "credentials": provider_credentials(request.provider),
        }
    databricks = {
        "catalog": request.catalog,
        "ctrl_schema": request.ctrl_schema,
        "workspace_profile": request.workspace_profile,
    }
    if any(value for value in databricks.values()):
        payload["databricks"] = {key: value for key, value in databricks.items() if value}
    agent = {
        "instruction_path": request.instruction_path,
        "tool_boundary": request.tool_boundary,
    }
    if any(value for value in agent.values()):
        payload["agent"] = {key: value for key, value in agent.items() if value}
    return payload


def _decisions_required(
    request: OnboardingInitRequest,
    profile_name: IntegrationProfileName,
    missing_required: list[str],
) -> list[RequiredDecision]:
    decisions = [
        RequiredDecision(
            question=f"Confirm the `{profile_name}` integration profile is the intended execution context",
            reason="Profile choice controls unsupported capabilities and recommended commands",
            path="profile",
            options=["confirm", "choose another profile"],
        )
    ]
    for key in missing_required:
        decisions.append(
            RequiredDecision(
                question=f"Provide `{key}` for the `{profile_name}` profile",
                reason="The selected profile marks this setting as required",
                path=key,
            )
        )
    if request.provider_mode == "provider-enriched":
        decisions.append(
            RequiredDecision(
                question="Confirm provider-enriched output is allowed for this environment",
                reason="Model providers receive redacted context but still introduce an external dependency",
                path="mode",
                options=["deterministic", "provider-enriched"],
            )
        )
    return decisions


def _setup_report_markdown(
    *,
    request: OnboardingInitRequest,
    profile_name: IntegrationProfileName,
    profile_description: str,
    config: dict[str, Any],
    environment: EnvironmentReport,
    report: DecisionReport,
) -> str:
    lines = [
        "# ContractForge AI Onboarding Report",
        "",
        f"- Profile: `{profile_name}`",
        f"- Profile description: {profile_description}",
        f"- Mode: `{request.provider_mode}`",
        "",
        "## Generated Files",
        "",
        "- `contractforge-ai.yaml`: setup configuration without secret values.",
        "- `SETUP_REPORT.md`: review evidence, warnings and required decisions.",
        "",
        "## Configuration Preview",
        "",
        "```yaml",
        yaml.safe_dump(config, sort_keys=False).rstrip(),
        "```",
        "",
        "## Environment",
        "",
        f"- Python: `{environment.python_version}`",
        f"- Platform: `{environment.platform}`",
        "",
        "### Packages",
        "",
    ]
    for group_name, packages in environment.to_dict()["package_groups"].items():
        lines.append(f"#### {group_name.replace('_', ' ').title()}")
        lines.extend([f"- `{name}`: {'available' if available else 'missing'}" for name, available in packages.items()])
        lines.append("")
    lines.extend(["", "### Commands", ""])
    lines.extend([f"- `{name}`: {'available' if available else 'missing'}" for name, available in environment.commands.items()])
    if environment.databricks:
        lines.extend(["", "### Databricks", ""])
        lines.extend([f"- `{key}`: `{value}`" for key, value in environment.databricks.items()])
    if environment.provider_environment:
        lines.extend(["", "### Provider Environment", ""])
        for key, value in environment.provider_environment.items():
            state = "configured" if value.get("configured") else "missing"
            lines.append(f"- `{key}`: {state}")
    lines.extend(["", report.to_markdown().rstrip(), ""])
    return "\n".join(lines)
