from contractforge_ai.onboarding import EnvironmentReport, OnboardingInitRequest, build_onboarding_plan
from contractforge_ai.onboarding.provider_credentials import provider_credentials, registered_onboarding_providers


def _environment() -> EnvironmentReport:
    return EnvironmentReport(
        python_version="3.11.0",
        platform="test-platform",
        packages={
            "contractforge_core": True,
            "contractforge_ai": True,
            "contractforge_databricks": True,
            "contractforge_aws": False,
            "yaml": True,
            "openai": False,
            "boto3": False,
            "databricks.sdk": True,
        },
        commands={"databricks": True, "git": True, "dbt": False},
        provider_environment={"OPENAI_API_KEY": {"configured": True, "value": "[REDACTED]"}},
        databricks={"in_notebook": False, "host_configured": True, "token_configured": False},
        warnings=["DATABRICKS_TOKEN is not configured."],
    )


def test_build_onboarding_plan_generates_safe_artifacts():
    plan = build_onboarding_plan(
        OnboardingInitRequest(
            profile="databricks-job",
            provider_mode="provider-enriched",
            provider="openai",
            model="gpt-4.1",
            catalog="main",
            ctrl_schema="ops",
        ),
        environment=_environment(),
    )

    artifacts = {artifact.path: artifact.content for artifact in plan.artifacts}

    assert plan.target == "contractforge-ai-onboarding"
    assert "contractforge-ai.yaml" in artifacts
    assert "SETUP_REPORT.md" in artifacts
    assert "api_key_env: OPENAI_API_KEY" in artifacts["contractforge-ai.yaml"]
    assert "[REDACTED]" not in artifacts["contractforge-ai.yaml"]
    assert "#### Contractforge" in artifacts["SETUP_REPORT.md"]
    assert "`contractforge_core`: available" in artifacts["SETUP_REPORT.md"]
    assert "#### Adapters" in artifacts["SETUP_REPORT.md"]
    assert "`contractforge_aws`: missing" in artifacts["SETUP_REPORT.md"]
    assert "DATABRICKS_TOKEN is not configured." in plan.report.warnings
    assert any("provider-enriched output is allowed" in item.question for item in plan.report.decisions_required)


def test_build_onboarding_plan_reports_missing_profile_config():
    plan = build_onboarding_plan(
        OnboardingInitRequest(profile="databricks-job", catalog="main"),
        environment=_environment(),
    )

    assert any("Missing required profile config: ctrl_schema." == warning for warning in plan.report.warnings)
    assert any(item.path == "ctrl_schema" for item in plan.report.decisions_required)


def test_onboarding_provider_credentials_are_registry_driven():
    assert "openai" in registered_onboarding_providers()
    assert provider_credentials("openai") == {"api_key_env": "OPENAI_API_KEY"}
    assert provider_credentials("databricks")["serving_endpoint_env"] == "DATABRICKS_SERVING_ENDPOINT"
    assert provider_credentials("unknown") == {"secret_policy": "configure credentials outside this file"}
