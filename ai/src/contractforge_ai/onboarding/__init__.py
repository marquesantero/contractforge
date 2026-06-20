"""Onboarding profiles and environment discovery."""

from contractforge_ai.onboarding.agent_assets import AgentInstructionRequest, generate_agent_instruction_plan
from contractforge_ai.onboarding.discovery import EnvironmentReport, discover_environment
from contractforge_ai.onboarding.init import OnboardingInitRequest, build_onboarding_plan
from contractforge_ai.onboarding.profiles import (
    IntegrationProfile,
    IntegrationProfileName,
    ProfileValidationReport,
    get_integration_profile,
    list_integration_profiles,
)

__all__ = [
    "AgentInstructionRequest",
    "EnvironmentReport",
    "IntegrationProfile",
    "IntegrationProfileName",
    "OnboardingInitRequest",
    "ProfileValidationReport",
    "build_onboarding_plan",
    "discover_environment",
    "generate_agent_instruction_plan",
    "get_integration_profile",
    "list_integration_profiles",
]
