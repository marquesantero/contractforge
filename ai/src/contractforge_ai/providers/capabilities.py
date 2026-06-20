"""Provider capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ProviderStatus = Literal["implemented", "planned"]
ProviderPriority = Literal["primary", "secondary", "experimental"]
StructuredOutputStrategy = Literal[
    "none",
    "strict_schema",
    "json_mode_only",
    "endpoint_dependent",
    "tool_schema",
    "native_schema",
]
TransportMode = Literal["none", "http", "sdk", "platform_endpoint"]
DatabricksDependencyMode = Literal[
    "none",
    "http_only",
    "optional_sdk",
    "required_sdk",
    "platform_native",
    "endpoint_dependent",
]


class ProviderCapabilityError(ValueError):
    """Raised when provider capability metadata cannot be resolved."""


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declarative capability metadata for one model provider."""

    name: str
    display_name: str
    status: ProviderStatus
    priority: ProviderPriority
    structured_output_strategy: StructuredOutputStrategy
    transport_mode: TransportMode
    databricks_dependency_mode: DatabricksDependencyMode
    supports_openai_compatible_api: bool = False
    supports_json_mode: bool = False
    supports_strict_schema: bool = False
    supports_tool_schema: bool = False
    supports_native_schema: bool = False
    requires_extra_package: bool = False
    package_extra: str | None = None
    default_endpoint: str | None = None
    recommended_for: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def implemented(self) -> bool:
        return self.status == "implemented"

    @property
    def needs_local_validation(self) -> bool:
        return self.structured_output_strategy != "strict_schema"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "priority": self.priority,
            "structured_output_strategy": self.structured_output_strategy,
            "transport_mode": self.transport_mode,
            "databricks_dependency_mode": self.databricks_dependency_mode,
            "supports_openai_compatible_api": self.supports_openai_compatible_api,
            "supports_json_mode": self.supports_json_mode,
            "supports_strict_schema": self.supports_strict_schema,
            "supports_tool_schema": self.supports_tool_schema,
            "supports_native_schema": self.supports_native_schema,
            "requires_extra_package": self.requires_extra_package,
            "package_extra": self.package_extra,
            "default_endpoint": self.default_endpoint,
            "recommended_for": list(self.recommended_for),
            "needs_local_validation": self.needs_local_validation,
            "notes": list(self.notes),
        }


PROVIDER_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "offline": ProviderCapabilities(
        name="offline",
        display_name="Offline deterministic provider",
        status="implemented",
        priority="primary",
        structured_output_strategy="none",
        transport_mode="none",
        databricks_dependency_mode="none",
        recommended_for=("CI-safe deterministic workflows", "local validation without model access"),
        notes=("No model calls are performed. Deterministic output is returned without enrichment.",),
    ),
    "openai": ProviderCapabilities(
        name="openai",
        display_name="OpenAI",
        status="implemented",
        priority="primary",
        structured_output_strategy="strict_schema",
        transport_mode="sdk",
        databricks_dependency_mode="optional_sdk",
        supports_json_mode=True,
        supports_strict_schema=True,
        requires_extra_package=True,
        package_extra="openai",
        recommended_for=("strict structured enrichment", "provider-backed reviews with schema enforcement"),
        notes=(
            "Uses OpenAI structured outputs through the Responses API.",
            "Local validation remains enabled even when provider-side schema enforcement is available.",
        ),
    ),
    "azure_openai": ProviderCapabilities(
        name="azure_openai",
        display_name="Azure OpenAI",
        status="implemented",
        priority="primary",
        structured_output_strategy="strict_schema",
        transport_mode="sdk",
        databricks_dependency_mode="optional_sdk",
        supports_json_mode=True,
        supports_strict_schema=True,
        requires_extra_package=True,
        package_extra="openai",
        recommended_for=("Azure-governed model access", "strict structured enrichment with Azure-hosted deployments"),
        notes=(
            "Uses Azure OpenAI through explicit endpoint, deployment and API version settings.",
            "Provider behavior depends on the deployed model and API version.",
        ),
    ),
    "deepseek": ProviderCapabilities(
        name="deepseek",
        display_name="DeepSeek",
        status="implemented",
        priority="primary",
        structured_output_strategy="json_mode_only",
        transport_mode="http",
        databricks_dependency_mode="http_only",
        supports_openai_compatible_api=True,
        supports_json_mode=True,
        default_endpoint="https://api.deepseek.com",
        recommended_for=("HTTP-only Databricks runtimes", "provider diversity checks with local schema validation"),
        notes=(
            "Uses OpenAI-compatible Chat Completions over HTTP.",
            "JSON mode guarantees valid JSON, not adherence to ContractForge AI schemas.",
        ),
    ),
    "databricks": ProviderCapabilities(
        name="databricks",
        display_name="Databricks Model Serving",
        status="implemented",
        priority="primary",
        structured_output_strategy="endpoint_dependent",
        transport_mode="platform_endpoint",
        databricks_dependency_mode="platform_native",
        supports_openai_compatible_api=True,
        recommended_for=("Databricks-controlled serving endpoints", "workspace-local model governance"),
        notes=(
            "Invokes Databricks Model Serving endpoints over HTTP.",
            "Structured-output guarantees depend on the served model or external model endpoint.",
        ),
    ),
    "anthropic": ProviderCapabilities(
        name="anthropic",
        display_name="Anthropic",
        status="implemented",
        priority="primary",
        structured_output_strategy="tool_schema",
        transport_mode="http",
        databricks_dependency_mode="http_only",
        supports_tool_schema=True,
        recommended_for=("tool-schema based enrichment", "long-context review workflows"),
        notes=(
            "Best implemented through tool use with JSON Schema input_schema.",
            "Should not be routed through the OpenAI-compatible provider path.",
        ),
    ),
    "gemini": ProviderCapabilities(
        name="gemini",
        display_name="Google Gemini API",
        status="implemented",
        priority="primary",
        structured_output_strategy="native_schema",
        transport_mode="http",
        databricks_dependency_mode="http_only",
        supports_native_schema=True,
        default_endpoint="https://generativelanguage.googleapis.com",
        recommended_for=("native schema generation", "Google ecosystem deployments"),
        notes=(
            "Uses Gemini generateContent over HTTP with native structured output response schema.",
            "Vertex AI authentication is intentionally separate from this direct Gemini API entry.",
        ),
    ),
    "bedrock": ProviderCapabilities(
        name="bedrock",
        display_name="AWS Bedrock",
        status="implemented",
        priority="primary",
        structured_output_strategy="tool_schema",
        transport_mode="sdk",
        databricks_dependency_mode="required_sdk",
        supports_tool_schema=True,
        requires_extra_package=True,
        package_extra="aws",
        recommended_for=("AWS-governed model access", "Bedrock Converse tool-use workflows"),
        notes=(
            "Uses Bedrock Runtime Converse with tool use.",
            "AWS SigV4 authentication makes a boto3/botocore dependency preferable to raw HTTP.",
        ),
    ),
}


def get_provider_capabilities(name: str) -> ProviderCapabilities:
    """Return capability metadata for a provider name."""

    normalized = name.strip().lower()
    try:
        return PROVIDER_CAPABILITIES[normalized]
    except KeyError as exc:
        allowed = ", ".join(sorted(PROVIDER_CAPABILITIES))
        raise ProviderCapabilityError(
            f"Unsupported provider capability name: {name!r}. Expected one of: {allowed}."
        ) from exc


def list_provider_capabilities(
    *,
    include_planned: bool = True,
    status: ProviderStatus | None = None,
    priority: ProviderPriority | None = None,
) -> list[ProviderCapabilities]:
    """List registered provider capabilities, optionally filtered by status or priority."""

    capabilities = sorted(PROVIDER_CAPABILITIES.values(), key=lambda item: item.name)
    if not include_planned:
        capabilities = [item for item in capabilities if item.implemented]
    if status is not None:
        capabilities = [item for item in capabilities if item.status == status]
    if priority is not None:
        capabilities = [item for item in capabilities if item.priority == priority]
    return capabilities


def implemented_provider_names() -> tuple[str, ...]:
    """Return provider names that have a concrete implementation."""

    return tuple(item.name for item in list_provider_capabilities(include_planned=False))


def planned_provider_names() -> tuple[str, ...]:
    """Return provider names that are intentionally registered but not implemented yet."""

    return tuple(item.name for item in list_provider_capabilities(status="planned"))
