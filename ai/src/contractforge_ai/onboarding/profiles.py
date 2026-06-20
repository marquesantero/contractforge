"""Typed integration profiles for ContractForge AI onboarding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IntegrationProfileName = Literal[
    "local-cli",
    "github-actions",
    "databricks-notebook",
    "databricks-job",
    "agent-skill",
    "mcp",
]


@dataclass(frozen=True)
class IntegrationProfile:
    """A supported ContractForge AI usage profile."""

    name: IntegrationProfileName
    description: str
    required_config: list[str] = field(default_factory=list)
    optional_config: list[str] = field(default_factory=list)
    unsupported_capabilities: list[str] = field(default_factory=list)
    recommended_commands: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate_config(self, config: dict[str, Any]) -> ProfileValidationReport:
        missing = [key for key in self.required_config if not _has_value(config.get(key))]
        warnings = [
            f"Unsupported capability for {self.name}: {capability}"
            for capability in self.unsupported_capabilities
            if config.get(capability) is True
        ]
        return ProfileValidationReport(
            profile=self.name,
            status="PASS" if not missing and not warnings else "WARN",
            missing_required=missing,
            warnings=warnings,
            recommended_commands=self.recommended_commands,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required_config": self.required_config,
            "optional_config": self.optional_config,
            "unsupported_capabilities": self.unsupported_capabilities,
            "recommended_commands": self.recommended_commands,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ProfileValidationReport:
    """Validation result for an integration profile configuration."""

    profile: IntegrationProfileName
    status: Literal["PASS", "WARN"]
    missing_required: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommended_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "status": self.status,
            "missing_required": self.missing_required,
            "warnings": self.warnings,
            "recommended_commands": self.recommended_commands,
        }


PROFILES: dict[IntegrationProfileName, IntegrationProfile] = {
    "local-cli": IntegrationProfile(
        name="local-cli",
        description="Local deterministic review, explanation and project generation from a developer workstation.",
        optional_config=["provider", "model", "contractforge_package"],
        recommended_commands=[
            "contractforge-ai review <contract>",
            "contractforge-ai explain-run --input failed-run.json",
            "contractforge-ai generate-project --target contractforge-yaml ...",
        ],
        notes=["Does not require a model provider for deterministic workflows."],
    ),
    "github-actions": IntegrationProfile(
        name="github-actions",
        description="CI checks for contract review, generated artifacts and pull request feedback.",
        required_config=["fail_on"],
        optional_config=["report_format", "changed_files_only"],
        unsupported_capabilities=["interactive_prompts"],
        recommended_commands=["contractforge-ai review <contract> --fail-on high --format json"],
        notes=["Use deterministic checks as the default CI gate."],
    ),
    "databricks-notebook": IntegrationProfile(
        name="databricks-notebook",
        description="Notebook-friendly diagnostics and control-table evidence collection.",
        required_config=["catalog", "ctrl_schema"],
        optional_config=["provider", "model", "workspace_profile"],
        recommended_commands=["contractforge-ai explain-run --run-id <run_id> --catalog <catalog> --ctrl-schema <schema>"],
        notes=["Use Databricks secrets for provider credentials; never hardcode tokens in notebooks."],
    ),
    "databricks-job": IntegrationProfile(
        name="databricks-job",
        description="Runtime-safe execution inside Databricks jobs or Databricks Asset Bundles.",
        required_config=["catalog", "ctrl_schema"],
        optional_config=["bundle_target", "workspace_profile", "provider", "model"],
        unsupported_capabilities=["interactive_prompts"],
        recommended_commands=["databricks bundle run <job-name>", "contractforge-ai explain-run --run-id <run_id> --catalog <catalog>"],
        notes=["Prefer explicit config and non-interactive execution for jobs."],
    ),
    "agent-skill": IntegrationProfile(
        name="agent-skill",
        description="Instruction assets for coding assistants that work on ContractForge contracts and examples.",
        required_config=["instruction_path"],
        optional_config=["workspace_policy", "allowed_targets"],
        unsupported_capabilities=["direct_production_mutation"],
        recommended_commands=["contractforge-ai generate-project --format markdown ..."],
        notes=["Agent instructions must require deterministic validation before edits are treated as complete."],
    ),
    "mcp": IntegrationProfile(
        name="mcp",
        description="Future MCP/tool wrapper profile for safe contract review and generation services.",
        required_config=["tool_boundary"],
        optional_config=["read_only_mode", "allowed_roots"],
        unsupported_capabilities=["unreviewed_file_writes", "secret_resolution"],
        recommended_commands=[],
        notes=["MCP integration should expose reviewable tools, not unrestricted filesystem or production mutation."],
    ),
}


def list_integration_profiles() -> list[IntegrationProfile]:
    """Return supported integration profiles in stable order."""

    return [PROFILES[name] for name in sorted(PROFILES)]


def get_integration_profile(name: str) -> IntegrationProfile:
    """Return a supported integration profile by name."""

    try:
        return PROFILES[name]  # type: ignore[index]
    except KeyError as exc:
        allowed = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unsupported integration profile {name!r}. Expected one of: {allowed}.") from exc


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True
