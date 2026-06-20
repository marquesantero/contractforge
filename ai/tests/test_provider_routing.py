from contractforge_ai.providers import ProviderRoutingRequest, recommend_providers


def test_routing_selects_strict_schema_provider_for_project_planning():
    report = recommend_providers(ProviderRoutingRequest(task="project_planning", require_strict_schema=True))

    assert report.selected is not None
    assert report.selected.provider in {"openai", "azure_openai"}
    assert report.selected.structured_output_strategy == "strict_schema"
    assert _by_provider(report, "deepseek").blockers == [
        "Strict schema was required but the provider does not declare strict schema support."
    ]
    assert _by_provider(report, "anthropic").blockers == [
        "Strict schema was required but the provider does not declare strict schema support."
    ]


def test_routing_prefers_databricks_boundary_for_failure_explanation():
    report = recommend_providers(
        ProviderRoutingRequest(task="failure_explanation", prefer_databricks_boundary=True)
    )

    assert report.selected is not None
    assert report.selected.provider == "databricks"
    assert any("Databricks model-serving boundary" in reason for reason in report.selected.reasons)


def test_routing_can_recommend_deepseek_for_http_only_review_with_warning():
    report = recommend_providers(
        ProviderRoutingRequest(
            task="review_enrichment",
            prefer_http_only=True,
            allowed_providers=("deepseek",),
        )
    )

    assert report.selected is not None
    assert report.selected.provider == "deepseek"
    assert report.selected.structured_output_strategy == "json_mode_only"
    assert any("local schema validation" in warning for warning in report.selected.warnings)


def test_routing_blocks_providers_outside_allowed_list():
    report = recommend_providers(
        ProviderRoutingRequest(
            task="metadata_enrichment",
            allowed_providers=("missing_future_provider",),
        )
    )

    assert report.selected is None
    assert report.recommendations
    assert all(
        "Provider is not in the allowed provider list." in recommendation.blockers
        for recommendation in report.recommendations
    )


def test_routing_can_recommend_bedrock_as_implemented_sdk_tool_schema_provider():
    report = recommend_providers(
        ProviderRoutingRequest(
            task="metadata_enrichment",
            allowed_providers=("bedrock",),
        )
    )

    assert report.selected is not None
    assert report.selected.provider == "bedrock"
    assert report.selected.status == "implemented"
    assert report.selected.structured_output_strategy == "tool_schema"
    assert report.to_dict()["selected"]["provider"] == "bedrock"


def test_routing_can_recommend_anthropic_as_implemented_http_tool_schema_provider():
    report = recommend_providers(
        ProviderRoutingRequest(
            task="metadata_enrichment",
            prefer_http_only=True,
            allowed_providers=("anthropic",),
        )
    )

    assert report.selected is not None
    assert report.selected.provider == "anthropic"
    assert report.selected.status == "implemented"
    assert report.selected.structured_output_strategy == "tool_schema"


def test_routing_can_recommend_gemini_as_implemented_http_native_schema_provider():
    report = recommend_providers(
        ProviderRoutingRequest(
            task="metadata_enrichment",
            prefer_http_only=True,
            allowed_providers=("gemini",),
        )
    )

    assert report.selected is not None
    assert report.selected.provider == "gemini"
    assert report.selected.status == "implemented"
    assert report.selected.structured_output_strategy == "native_schema"


def test_routing_excludes_offline_by_default():
    report = recommend_providers(ProviderRoutingRequest(task="review_enrichment"))

    assert _by_provider(report, "offline").blockers == [
        "Offline provider is excluded from provider-backed routing by default."
    ]


def _by_provider(report, provider: str):
    for recommendation in report.recommendations:
        if recommendation.provider == provider:
            return recommendation
    raise AssertionError(f"provider {provider!r} not found")
