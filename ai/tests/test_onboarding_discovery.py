from contractforge_ai.onboarding import discover_environment


def test_discover_environment_redacts_provider_secrets_and_reports_capabilities():
    report = discover_environment(
        environ={
            "CONTRACTFORGE_AI_PROVIDER": "openai",
            "OPENAI_API_KEY": "secret-value",
            "DATABRICKS_HOST": "https://workspace",
            "DATABRICKS_TOKEN": "token-value",
            "DATABRICKS_SERVING_ENDPOINT": "cf-ai-endpoint",
        },
        command_lookup=lambda command: "/bin/" + command if command in {"git", "databricks"} else None,
        package_lookup=lambda package: package in {"contractforge_core", "contractforge_ai", "yaml", "databricks.sdk"},
    )
    payload = report.to_dict()

    assert payload["packages"]["contractforge_core"] is True
    assert payload["packages"]["contractforge_aws"] is False
    assert payload["package_groups"]["contractforge"]["contractforge_core"] is True
    assert payload["package_groups"]["adapters"]["contractforge_aws"] is False
    assert payload["package_groups"]["provider_clients"]["boto3"] is False
    assert payload["commands"]["databricks"] is True
    assert payload["provider_environment"]["OPENAI_API_KEY"]["value"] == "[REDACTED]"
    assert payload["provider_environment"]["DATABRICKS_TOKEN"]["value"] == "[REDACTED]"
    assert payload["provider_environment"]["DATABRICKS_SERVING_ENDPOINT"]["value"] == "cf-ai-endpoint"
    assert payload["provider_environment"]["CONTRACTFORGE_AI_PROVIDER"]["value"] == "openai"
    assert not any("ContractForge package is not installed" in warning for warning in payload["warnings"])


def test_discover_environment_detects_partial_provider_configuration():
    report = discover_environment(
        environ={"AZURE_OPENAI_API_KEY": "secret-value"},
        command_lookup=lambda command: None,
        package_lookup=lambda package: package == "contractforge_ai",
    )

    assert any("CONTRACTFORGE_AI_PROVIDER is missing" in warning for warning in report.warnings)


def test_discover_environment_reports_missing_ai_package_separately():
    report = discover_environment(
        environ={},
        command_lookup=lambda command: None,
        package_lookup=lambda package: package == "contractforge_core",
    )

    assert any("contractforge-ai is not importable" in warning for warning in report.warnings)


def test_discover_environment_detects_databricks_runtime_without_sdk():
    report = discover_environment(
        environ={"DATABRICKS_RUNTIME_VERSION": "16.4"},
        command_lookup=lambda command: None,
        package_lookup=lambda package: package == "contractforge_ai",
    )
    payload = report.to_dict()

    assert payload["databricks"]["in_notebook"] is True
    assert payload["databricks"]["sdk_available"] is False
    assert any("databricks.sdk is not importable" in warning for warning in payload["warnings"])
