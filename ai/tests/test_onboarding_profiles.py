from contractforge_ai.onboarding import get_integration_profile, list_integration_profiles


def test_list_integration_profiles_returns_supported_profiles():
    names = {profile.name for profile in list_integration_profiles()}

    assert names == {
        "agent-skill",
        "databricks-job",
        "databricks-notebook",
        "github-actions",
        "local-cli",
        "mcp",
    }


def test_profile_validation_reports_missing_required_config():
    profile = get_integration_profile("databricks-notebook")

    report = profile.validate_config({"catalog": "main"})

    assert report.status == "WARN"
    assert report.missing_required == ["ctrl_schema"]
    assert report.recommended_commands


def test_profile_validation_reports_unsupported_capabilities():
    profile = get_integration_profile("github-actions")

    report = profile.validate_config({"fail_on": "high", "interactive_prompts": True})

    assert report.status == "WARN"
    assert report.missing_required == []
    assert report.warnings == ["Unsupported capability for github-actions: interactive_prompts"]


def test_get_integration_profile_rejects_unknown_profile():
    try:
        get_integration_profile("unknown")
    except ValueError as exc:
        assert "Unsupported integration profile" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported profile")
