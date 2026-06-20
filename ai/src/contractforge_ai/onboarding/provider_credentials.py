"""Provider credential metadata for onboarding configuration drafts."""

from __future__ import annotations

DEFAULT_PROVIDER_CREDENTIALS = {"secret_policy": "configure credentials outside this file"}

PROVIDER_CREDENTIALS: dict[str, dict[str, str]] = {
    "openai": {"api_key_env": "OPENAI_API_KEY"},
    "azure_openai": {
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "endpoint_env": "AZURE_OPENAI_ENDPOINT",
        "api_version_env": "AZURE_OPENAI_API_VERSION",
    },
    "databricks": {
        "host_env": "DATABRICKS_HOST",
        "token_env": "DATABRICKS_TOKEN",
        "serving_endpoint_env": "DATABRICKS_SERVING_ENDPOINT",
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "base_url_env": "DEEPSEEK_BASE_URL",
    },
}


def provider_credentials(provider: str | None) -> dict[str, str]:
    """Return credential environment metadata for an onboarding provider."""

    return dict(PROVIDER_CREDENTIALS.get(provider or "", DEFAULT_PROVIDER_CREDENTIALS))


def registered_onboarding_providers() -> tuple[str, ...]:
    """Return providers with explicit onboarding credential metadata."""

    return tuple(PROVIDER_CREDENTIALS)
