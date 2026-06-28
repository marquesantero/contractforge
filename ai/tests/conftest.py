"""Shared pytest fixtures for the ContractForge AI test suite."""

from __future__ import annotations

import pytest

# Every environment variable consulted by
# contractforge_ai.providers.env.provider_config_from_env. They are cleared
# before each test so provider configuration depends only on what a test sets
# explicitly, never on the ambient shell (which may export real provider keys).
_PROVIDER_ENV_VARS = (
    "CONTRACTFORGE_AI_PROVIDER",
    "CONTRACTFORGE_AI_MODEL",
    "CONTRACTFORGE_AI_API_KEY",
    "CONTRACTFORGE_AI_ENDPOINT",
    "CONTRACTFORGE_AI_API_VERSION",
    "CONTRACTFORGE_AI_TIMEOUT",
    "CONTRACTFORGE_AI_MAX_RETRIES",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_MODEL",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION",
    "DATABRICKS_SERVING_ENDPOINT",
    "DATABRICKS_MODEL_SERVING_ENDPOINT",
    "DATABRICKS_TOKEN",
    "DATABRICKS_HOST",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_VERSION",
    "GEMINI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_BASE_URL",
    "GEMINI_API_VERSION",
    "BEDROCK_MODEL_ID",
    "BEDROCK_ENDPOINT_URL",
    "BEDROCK_REGION",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
)


@pytest.fixture(autouse=True)
def _isolate_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove ambient provider configuration so tests are environment-independent."""

    for name in _PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
