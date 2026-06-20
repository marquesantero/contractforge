import json

import pytest

from contractforge_ai.providers import (
    ProviderCapabilityError,
    get_provider_capabilities,
    implemented_provider_names,
    list_provider_capabilities,
    planned_provider_names,
)


def test_current_providers_are_registered_as_implemented():
    assert implemented_provider_names() == (
        "anthropic",
        "azure_openai",
        "bedrock",
        "databricks",
        "deepseek",
        "gemini",
        "offline",
        "openai",
    )


def test_prioritized_future_providers_are_registered_as_planned():
    assert planned_provider_names() == ()


def test_openai_capabilities_use_strict_schema_and_optional_sdk_extra():
    capabilities = get_provider_capabilities("openai")

    assert capabilities.status == "implemented"
    assert capabilities.structured_output_strategy == "strict_schema"
    assert capabilities.supports_strict_schema is True
    assert capabilities.requires_extra_package is True
    assert capabilities.package_extra == "openai"
    assert capabilities.needs_local_validation is False


def test_deepseek_is_openai_compatible_but_json_mode_only():
    capabilities = get_provider_capabilities("deepseek")

    assert capabilities.status == "implemented"
    assert capabilities.supports_openai_compatible_api is True
    assert capabilities.structured_output_strategy == "json_mode_only"
    assert capabilities.supports_json_mode is True
    assert capabilities.supports_strict_schema is False
    assert capabilities.transport_mode == "http"
    assert capabilities.databricks_dependency_mode == "http_only"
    assert capabilities.needs_local_validation is True


def test_databricks_structured_output_is_endpoint_dependent():
    capabilities = get_provider_capabilities("databricks")

    assert capabilities.status == "implemented"
    assert capabilities.structured_output_strategy == "endpoint_dependent"
    assert capabilities.databricks_dependency_mode == "platform_native"
    assert capabilities.needs_local_validation is True


def test_bedrock_requires_sdk_for_sigv4_and_uses_tool_schema():
    capabilities = get_provider_capabilities("bedrock")

    assert capabilities.status == "implemented"
    assert capabilities.structured_output_strategy == "tool_schema"
    assert capabilities.transport_mode == "sdk"
    assert capabilities.databricks_dependency_mode == "required_sdk"
    assert capabilities.requires_extra_package is True
    assert capabilities.package_extra == "aws"


def test_anthropic_uses_http_tool_schema_without_sdk_dependency():
    capabilities = get_provider_capabilities("anthropic")

    assert capabilities.status == "implemented"
    assert capabilities.structured_output_strategy == "tool_schema"
    assert capabilities.transport_mode == "http"
    assert capabilities.databricks_dependency_mode == "http_only"
    assert capabilities.supports_tool_schema is True
    assert capabilities.requires_extra_package is False


def test_gemini_uses_http_native_schema_without_sdk_dependency():
    capabilities = get_provider_capabilities("gemini")

    assert capabilities.status == "implemented"
    assert capabilities.structured_output_strategy == "native_schema"
    assert capabilities.transport_mode == "http"
    assert capabilities.databricks_dependency_mode == "http_only"
    assert capabilities.supports_native_schema is True
    assert capabilities.requires_extra_package is False
    assert capabilities.default_endpoint == "https://generativelanguage.googleapis.com"


def test_list_provider_capabilities_filters_by_status_priority_and_planned_flag():
    implemented = list_provider_capabilities(include_planned=False)
    planned_primary = list_provider_capabilities(status="planned", priority="primary")

    assert [item.name for item in implemented] == list(implemented_provider_names())
    assert [item.name for item in planned_primary] == list(planned_provider_names())


def test_unknown_provider_capability_raises_actionable_error():
    with pytest.raises(ProviderCapabilityError, match="Unsupported provider capability name"):
        get_provider_capabilities("unknown")


def test_capability_payload_is_json_friendly():
    payload = get_provider_capabilities("anthropic").to_dict()

    assert payload["structured_output_strategy"] == "tool_schema"
    assert payload["recommended_for"]
    json.dumps(payload)
