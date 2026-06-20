import json

import pytest

from contractforge_ai.providers import (
    AnthropicProvider,
    AzureOpenAIProvider,
    BedrockProvider,
    DatabricksModelServingProvider,
    DeepSeekProvider,
    GenerationOptions,
    GeminiProvider,
    OpenAIProvider,
    ProviderConfig,
    ProviderConfigurationError,
    create_provider,
    registered_provider_names,
)


class FakeResponses:
    def __init__(self):
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return {"output": [{"content": [{"type": "output_text", "text": "review text"}]}]}


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class FakeHTTPResponse:
    def __init__(self, payload: str):
        self.payload = payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.payload


class FakeHTTPClient:
    def __init__(self, payload: str):
        self.payload = payload
        self.request = None
        self.timeout = None

    def __call__(self, request, timeout=None):
        self.request = request
        self.timeout = timeout
        return FakeHTTPResponse(self.payload)


class FakeBedrockClient:
    def __init__(self, response):
        self.response = response
        self.request = None

    def converse(self, **kwargs):
        self.request = kwargs
        return self.response


def test_provider_config_from_env_openai(monkeypatch):
    monkeypatch.setenv("CONTRACTFORGE_AI_PROVIDER", "openai")
    monkeypatch.setenv("CONTRACTFORGE_AI_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    monkeypatch.setenv("CONTRACTFORGE_AI_TIMEOUT", "12.5")
    monkeypatch.setenv("CONTRACTFORGE_AI_MAX_RETRIES", "3")

    config = ProviderConfig.from_env()

    assert config.provider == "openai"
    assert config.model == "gpt-test"
    assert config.api_key == "secret-key"
    assert config.timeout == 12.5
    assert config.max_retries == 3
    assert config.to_safe_dict()["api_key"] == "[REDACTED]"


def test_provider_config_strips_string_values():
    config = ProviderConfig(
        provider="openai",
        model=" gpt-test\n",
        api_key=" sk-test\r\n",
        organization=" org ",
    )

    assert config.model == "gpt-test"
    assert config.api_key == "sk-test"
    assert config.organization == "org"


def test_provider_config_from_env_azure(monkeypatch):
    monkeypatch.setenv("CONTRACTFORGE_AI_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "review-deployment")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

    config = ProviderConfig.from_env()

    assert config.provider == "azure_openai"
    assert config.model == "review-deployment"
    assert config.endpoint == "https://example.openai.azure.com"
    assert config.api_version == "2025-04-01-preview"


def test_create_provider_returns_offline_provider():
    provider = create_provider(ProviderConfig(provider="offline"))

    assert provider.name == "offline"


def test_provider_factory_registry_covers_supported_provider_names():
    assert registered_provider_names() == (
        "offline",
        "openai",
        "azure_openai",
        "databricks",
        "deepseek",
        "anthropic",
        "gemini",
        "bedrock",
    )


def test_provider_config_from_env_databricks(monkeypatch):
    monkeypatch.setenv("CONTRACTFORGE_AI_PROVIDER", "databricks")
    monkeypatch.setenv("DATABRICKS_SERVING_ENDPOINT", "cf-ai-endpoint")
    monkeypatch.setenv("DATABRICKS_HOST", "https://adb.example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "secret-token")

    config = ProviderConfig.from_env()

    assert config.provider == "databricks"
    assert config.model == "cf-ai-endpoint"
    assert config.endpoint == "https://adb.example.databricks.com"
    assert config.api_key == "secret-token"
    assert config.to_safe_dict()["api_key"] == "[REDACTED]"


def test_provider_config_from_env_deepseek(monkeypatch):
    monkeypatch.setenv("CONTRACTFORGE_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    config = ProviderConfig.from_env()

    assert config.provider == "deepseek"
    assert config.model == "deepseek-chat"
    assert config.endpoint == "https://api.deepseek.com"
    assert config.api_key == "secret-key"
    assert config.to_safe_dict()["api_key"] == "[REDACTED]"


def test_provider_config_from_env_anthropic(monkeypatch):
    monkeypatch.setenv("CONTRACTFORGE_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    monkeypatch.setenv("ANTHROPIC_VERSION", "2023-06-01")

    config = ProviderConfig.from_env()

    assert config.provider == "anthropic"
    assert config.model == "claude-test"
    assert config.endpoint == "https://api.anthropic.com"
    assert config.api_version == "2023-06-01"
    assert config.api_key == "secret-key"
    assert config.to_safe_dict()["api_key"] == "[REDACTED]"


def test_provider_config_from_env_gemini(monkeypatch):
    monkeypatch.setenv("CONTRACTFORGE_AI_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key")
    monkeypatch.setenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
    monkeypatch.setenv("GEMINI_API_VERSION", "v1beta")

    config = ProviderConfig.from_env()

    assert config.provider == "gemini"
    assert config.model == "gemini-test"
    assert config.endpoint == "https://generativelanguage.googleapis.com"
    assert config.api_version == "v1beta"
    assert config.api_key == "secret-key"
    assert config.to_safe_dict()["api_key"] == "[REDACTED]"


def test_provider_config_from_env_bedrock(monkeypatch):
    monkeypatch.setenv("CONTRACTFORGE_AI_PROVIDER", "bedrock")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_ENDPOINT_URL", "https://bedrock-runtime.us-east-1.amazonaws.com")

    config = ProviderConfig.from_env()

    assert config.provider == "bedrock"
    assert config.model == "anthropic.claude-test"
    assert config.api_version == "us-east-1"
    assert config.endpoint == "https://bedrock-runtime.us-east-1.amazonaws.com"
    assert config.api_key is None


def test_openai_provider_uses_responses_api_request_shape():
    client = FakeClient()
    provider = OpenAIProvider(ProviderConfig(provider="openai", model="gpt-test"), client=client)

    output = provider.complete(
        "Review this contract",
        system="You review contracts.",
        options=GenerationOptions(temperature=0.1, max_output_tokens=500),
    )

    assert output == "review text"
    assert client.responses.request == {
        "model": "gpt-test",
        "input": "Review this contract",
        "instructions": "You review contracts.",
        "temperature": 0.1,
        "max_output_tokens": 500,
    }


def test_openai_provider_passes_strict_json_schema_response_format():
    client = FakeClient()
    provider = OpenAIProvider(ProviderConfig(provider="openai", model="gpt-test"), client=client)

    provider.complete(
        "Return JSON",
        options=GenerationOptions(
            response_schema_name="review_schema",
            response_schema={
                "type": "object",
                "required": ["kind"],
                "properties": {"kind": {"const": "review"}},
                "additionalProperties": False,
            },
        ),
    )

    assert client.responses.request["text"] == {
        "format": {
            "type": "json_schema",
            "name": "review_schema",
            "schema": {
                "type": "object",
                "required": ["kind"],
                "properties": {"kind": {"enum": ["review"]}},
                "additionalProperties": False,
            },
            "strict": True,
        }
    }


def test_openai_provider_makes_strict_schema_require_all_declared_properties():
    client = FakeClient()
    provider = OpenAIProvider(ProviderConfig(provider="openai", model="gpt-test"), client=client)

    provider.complete(
        "Return JSON",
        options=GenerationOptions(
            response_schema={
                "type": "object",
                "required": ["kind"],
                "properties": {
                    "kind": {"const": "review"},
                    "summary": {"type": "string"},
                },
                "additionalProperties": False,
            },
        ),
    )

    assert client.responses.request["text"]["format"]["schema"]["required"] == ["kind", "summary"]


def test_databricks_provider_invokes_serving_endpoint():
    client = FakeHTTPClient('{"choices": [{"message": {"content": "validated output"}}]}')
    provider = DatabricksModelServingProvider(
        ProviderConfig(
            provider="databricks",
            model="cf-ai-endpoint",
            endpoint="https://adb.example.databricks.com",
            api_key="secret-token",
            timeout=12.0,
        ),
        http_client=client,
    )

    output = provider.complete(
        "Review this contract",
        system="You review contracts.",
        options=GenerationOptions(temperature=0.1, max_output_tokens=500),
    )

    assert output == "validated output"
    assert client.timeout == 12.0
    assert client.request.full_url == "https://adb.example.databricks.com/serving-endpoints/cf-ai-endpoint/invocations"
    assert client.request.get_header("Authorization") == "Bearer secret-token"
    request_payload = client.request.data.decode("utf-8")
    assert '"role": "system"' in request_payload
    assert '"temperature": 0.1' in request_payload
    assert '"max_tokens": 500' in request_payload


def test_deepseek_provider_invokes_chat_completions_with_json_mode():
    client = FakeHTTPClient('{"choices": [{"message": {"content": "{\\"kind\\": \\"project_plan\\"}"}}]}')
    provider = DeepSeekProvider(
        ProviderConfig(
            provider="deepseek",
            model="deepseek-chat",
            endpoint="https://api.deepseek.com",
            api_key="secret-key",
            timeout=12.0,
        ),
        http_client=client,
    )

    output = provider.complete(
        "Return JSON",
        system="You return strict JSON.",
        options=GenerationOptions(
            temperature=0.1,
            max_output_tokens=500,
            response_schema={"type": "object", "properties": {"kind": {"type": "string"}}},
        ),
    )

    assert output == '{"kind": "project_plan"}'
    assert client.timeout == 12.0
    assert client.request.full_url == "https://api.deepseek.com/chat/completions"
    assert client.request.get_header("Authorization") == "Bearer secret-key"
    request_payload = json.loads(client.request.data.decode("utf-8"))
    assert request_payload["model"] == "deepseek-chat"
    assert request_payload["messages"][0] == {"role": "system", "content": "You return strict JSON."}
    assert request_payload["messages"][1] == {"role": "user", "content": "Return JSON"}
    assert request_payload["temperature"] == 0.1
    assert request_payload["max_tokens"] == 500
    assert request_payload["response_format"] == {"type": "json_object"}


def test_anthropic_provider_invokes_messages_api_with_tool_schema():
    client = FakeHTTPClient(
        '{"content": [{"type": "tool_use", "name": "review_schema", "input": {"kind": "review"}}]}'
    )
    provider = AnthropicProvider(
        ProviderConfig(
            provider="anthropic",
            model="claude-test",
            endpoint="https://api.anthropic.com",
            api_key="secret-key",
            api_version="2023-06-01",
            timeout=12.0,
        ),
        http_client=client,
    )

    output = provider.complete(
        "Return JSON",
        system="You return strict JSON.",
        options=GenerationOptions(
            temperature=0.1,
            max_output_tokens=500,
            response_schema_name="review_schema",
            response_schema={
                "type": "object",
                "required": ["kind"],
                "properties": {"kind": {"const": "review"}},
                "additionalProperties": False,
            },
        ),
    )

    assert json.loads(output) == {"kind": "review"}
    assert client.timeout == 12.0
    assert client.request.full_url == "https://api.anthropic.com/v1/messages"
    headers = {key.lower(): value for key, value in client.request.header_items()}
    assert headers["x-api-key"] == "secret-key"
    assert headers["anthropic-version"] == "2023-06-01"
    request_payload = json.loads(client.request.data.decode("utf-8"))
    assert request_payload["model"] == "claude-test"
    assert request_payload["system"] == "You return strict JSON."
    assert request_payload["messages"] == [{"role": "user", "content": "Return JSON"}]
    assert request_payload["temperature"] == 0.1
    assert request_payload["max_tokens"] == 500
    assert request_payload["tools"][0]["name"] == "review_schema"
    assert request_payload["tools"][0]["input_schema"]["properties"]["kind"]["const"] == "review"
    assert request_payload["tool_choice"] == {"type": "tool", "name": "review_schema"}


def test_anthropic_provider_extracts_text_response_without_schema():
    client = FakeHTTPClient('{"content": [{"type": "text", "text": "plain answer"}]}')
    provider = AnthropicProvider(
        ProviderConfig(provider="anthropic", model="claude-test", api_key="secret-key"),
        http_client=client,
    )

    output = provider.complete("Answer")

    assert output == "plain answer"
    request_payload = json.loads(client.request.data.decode("utf-8"))
    assert request_payload["max_tokens"] == 1024
    assert "tools" not in request_payload


def test_gemini_provider_invokes_generate_content_with_native_schema():
    client = FakeHTTPClient(
        '{"candidates": [{"content": {"parts": [{"text": "{\\"kind\\": \\"review\\"}"}]}}]}'
    )
    provider = GeminiProvider(
        ProviderConfig(
            provider="gemini",
            model="gemini-test",
            endpoint="https://generativelanguage.googleapis.com",
            api_key="secret-key",
            api_version="v1beta",
            timeout=12.0,
        ),
        http_client=client,
    )

    output = provider.complete(
        "Return JSON",
        system="You return strict JSON.",
        options=GenerationOptions(
            temperature=0.1,
            max_output_tokens=500,
            response_schema={
                "type": "object",
                "required": ["kind"],
                "properties": {"kind": {"const": "review"}},
                "additionalProperties": False,
            },
        ),
    )

    assert json.loads(output) == {"kind": "review"}
    assert client.timeout == 12.0
    assert client.request.full_url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    headers = {key.lower(): value for key, value in client.request.header_items()}
    assert headers["x-goog-api-key"] == "secret-key"
    request_payload = json.loads(client.request.data.decode("utf-8"))
    assert request_payload["systemInstruction"] == {"parts": [{"text": "You return strict JSON."}]}
    assert request_payload["contents"] == [{"role": "user", "parts": [{"text": "Return JSON"}]}]
    assert request_payload["generationConfig"]["temperature"] == 0.1
    assert request_payload["generationConfig"]["maxOutputTokens"] == 500
    assert request_payload["generationConfig"]["responseMimeType"] == "application/json"
    assert request_payload["generationConfig"]["responseJsonSchema"]["properties"]["kind"]["enum"] == ["review"]


def test_gemini_provider_extracts_text_response_without_schema():
    client = FakeHTTPClient('{"candidates": [{"content": {"parts": [{"text": "plain answer"}]}}]}')
    provider = GeminiProvider(
        ProviderConfig(provider="gemini", model="gemini-test", api_key="secret-key"),
        http_client=client,
    )

    output = provider.complete("Answer")

    assert output == "plain answer"
    request_payload = json.loads(client.request.data.decode("utf-8"))
    assert "generationConfig" not in request_payload


def test_bedrock_provider_invokes_converse_with_tool_schema():
    client = FakeBedrockClient(
        {
            "output": {
                "message": {
                    "content": [
                        {"toolUse": {"name": "review_schema", "input": {"kind": "review"}}},
                    ]
                }
            }
        }
    )
    provider = BedrockProvider(
        ProviderConfig(provider="bedrock", model="anthropic.claude-test", api_version="us-east-1"),
        client=client,
    )

    output = provider.complete(
        "Return JSON",
        system="You return strict JSON.",
        options=GenerationOptions(
            temperature=0.1,
            max_output_tokens=500,
            response_schema_name="review_schema",
            response_schema={
                "type": "object",
                "required": ["kind"],
                "properties": {"kind": {"const": "review"}},
                "additionalProperties": False,
            },
        ),
    )

    assert json.loads(output) == {"kind": "review"}
    assert client.request["modelId"] == "anthropic.claude-test"
    assert client.request["system"] == [{"text": "You return strict JSON."}]
    assert client.request["messages"] == [{"role": "user", "content": [{"text": "Return JSON"}]}]
    assert client.request["inferenceConfig"] == {"temperature": 0.1, "maxTokens": 500}
    tool_config = client.request["toolConfig"]
    assert tool_config["toolChoice"] == {"tool": {"name": "review_schema"}}
    assert tool_config["tools"][0]["toolSpec"]["name"] == "review_schema"
    assert tool_config["tools"][0]["toolSpec"]["inputSchema"]["json"]["properties"]["kind"]["enum"] == ["review"]


def test_bedrock_provider_extracts_text_response_without_schema():
    client = FakeBedrockClient(
        {
            "output": {
                "message": {
                    "content": [
                        {"text": "plain answer"},
                    ]
                }
            }
        }
    )
    provider = BedrockProvider(
        ProviderConfig(provider="bedrock", model="anthropic.claude-test"),
        client=client,
    )

    output = provider.complete("Answer")

    assert output == "plain answer"
    assert "toolConfig" not in client.request


def test_create_provider_returns_deepseek_provider():
    provider = create_provider(
        ProviderConfig(provider="deepseek", model="deepseek-chat", api_key="secret-key"),
    )

    assert provider.name == "deepseek"


def test_create_provider_returns_anthropic_provider():
    provider = create_provider(
        ProviderConfig(provider="anthropic", model="claude-test", api_key="secret-key"),
    )

    assert provider.name == "anthropic"


def test_create_provider_returns_gemini_provider():
    provider = create_provider(
        ProviderConfig(provider="gemini", model="gemini-test", api_key="secret-key"),
    )

    assert provider.name == "gemini"


def test_create_provider_returns_bedrock_provider_with_injected_client():
    provider = BedrockProvider(
        ProviderConfig(provider="bedrock", model="anthropic.claude-test"),
        client=FakeBedrockClient({"output": {"message": {"content": [{"text": "ok"}]}}}),
    )

    assert provider.name == "bedrock"


def test_databricks_provider_requires_connection_settings():
    with pytest.raises(ProviderConfigurationError, match="Databricks provider requires"):
        DatabricksModelServingProvider(ProviderConfig(provider="databricks", model="endpoint"))


def test_azure_provider_requires_explicit_connection_settings():
    with pytest.raises(ProviderConfigurationError, match="Azure OpenAI provider requires"):
        AzureOpenAIProvider(ProviderConfig(provider="azure_openai", model="deployment"))


def test_openai_provider_requires_model_even_with_fake_client():
    with pytest.raises(ProviderConfigurationError, match="requires CONTRACTFORGE_AI_MODEL"):
        OpenAIProvider(ProviderConfig(provider="openai"), client=FakeClient())


def test_deepseek_provider_requires_connection_settings():
    with pytest.raises(ProviderConfigurationError, match="DeepSeek provider requires"):
        DeepSeekProvider(ProviderConfig(provider="deepseek", model="deepseek-chat"))


def test_anthropic_provider_requires_connection_settings():
    with pytest.raises(ProviderConfigurationError, match="Anthropic provider requires"):
        AnthropicProvider(ProviderConfig(provider="anthropic", model="claude-test"))


def test_gemini_provider_requires_connection_settings():
    with pytest.raises(ProviderConfigurationError, match="Gemini provider requires"):
        GeminiProvider(ProviderConfig(provider="gemini", model="gemini-test"))


def test_bedrock_provider_requires_model():
    with pytest.raises(ProviderConfigurationError, match="Bedrock provider requires"):
        BedrockProvider(ProviderConfig(provider="bedrock"), client=FakeBedrockClient({}))
