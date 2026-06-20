from contractforge_ai.planning import EnrichedProjectSpec, ProjectPlannerRequest, SpecValue, plan_project_from_intent


def test_enriched_project_spec_from_ready_planner_keeps_generation_kwargs():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a bronze ingestion from s3a://landing/orders into main.bronze.b_orders using scd0_append.",
            schema_path="schemas/orders.yaml",
        )
    )

    spec = EnrichedProjectSpec.from_planner(planner, selected_target="databricks-dab")

    assert spec.selected_target.value == "databricks-dab"
    assert spec.connector.value == "s3"
    assert spec.source_path.value == "s3a://landing/orders"
    assert spec.generation_kwargs()["target_table"] == "b_orders"
    assert spec.validate().status == "READY"


def test_enriched_project_spec_extracts_explicit_operations_quality_and_dab_compute():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create a bronze DAB ingestion from s3a://landing/orders into main.bronze.b_orders using serverless. "
                "Business owner: revenue-analytics. Technical owner: data-engineering. Steward: data-governance. "
                "Criticality: high. Expected frequency: daily. SLA: 120 minutes. Alert on failure and alert on quality failure. "
                "Required columns: order_id, customer_id, amount. Unique key: order_id. "
                "amount must be >= 0. currency accepted values: USD, EUR, BRL. quality severity: fail."
            ),
            schema_path="schemas/orders.yaml",
            preferred_target="databricks-dab",
        )
    )

    spec = EnrichedProjectSpec.from_planner(planner, selected_target="databricks-dab")

    assert spec.operations is not None
    assert spec.operations.value["business_owner"] == "revenue-analytics"
    assert spec.operations.value["technical_owner"] == "data-engineering"
    assert spec.operations.value["criticality"] == "high"
    assert spec.operations.value["freshness_sla_minutes"] == 120
    assert spec.operations.value["alert_on_failure"] is True
    assert spec.operations.value["alert_on_quality_fail"] is True
    assert spec.quality_rules is not None
    assert spec.quality_rules.value["not_null"] == ["order_id", "customer_id", "amount"]
    assert spec.quality_rules.value["unique_key"] == ["order_id"]
    assert spec.quality_rules.value["accepted_values"]["currency"] == ["USD", "EUR", "BRL"]
    assert spec.quality_rules.value["expressions"][0]["expression"] == "amount >= 0"
    assert spec.quality_rules.value["expressions"][0]["severity"] == "abort"
    assert spec.dab_compute is not None
    assert spec.dab_compute.value == {"type": "serverless"}


def test_enriched_project_spec_carries_prompt_schedule_and_governance():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent=(
                "Create Supabase medallion for AWS and Databricks daily at 6 Sao Paulo time. "
                "Source system: supabase. Use postgres JDBC from jdbc:postgresql://db.example/postgres "
                "into analytics.bronze.b_orders. Require PII masking, row filters, evidence, "
                "minimal differences between platforms, and freshness target 30 minutes."
            ),
            schema_path="schemas/orders.yaml",
        )
    )

    spec = EnrichedProjectSpec.from_planner(planner, selected_target="aws-glue-iceberg")

    assert spec.source_system is not None
    assert spec.source_system.value == "supabase"
    assert spec.schedule is not None
    assert spec.schedule.value == {"cron": "0 6 * * *", "timezone": "America/Sao_Paulo", "enabled": True}
    assert spec.freshness is not None
    assert spec.freshness.value == {"class": "near_real_time", "latency_target": "30 minutes"}
    assert spec.governance is not None
    assert spec.governance.review_required is True
    assert spec.portability_priority is not None
    assert spec.portability_priority.value == "high"


def test_enriched_project_spec_requires_merge_keys_for_hash_diff():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a silver ingestion from s3a://landing/orders into main.silver.orders using scd1_hash_diff.",
            schema_path="schemas/orders.yaml",
        )
    )

    spec = EnrichedProjectSpec.from_planner(planner)
    validation = spec.validate()

    assert validation.status == "NEEDS_DECISIONS"
    assert any(decision.path == "merge_keys" for decision in validation.decisions_required)
    assert any(decision.path == "hash_columns" for decision in validation.decisions_required)


def test_enriched_project_spec_flags_provider_suggested_critical_fields_without_review():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a silver ingestion from s3a://landing/orders into main.silver.orders using scd1_hash_diff.",
            schema_path="schemas/orders.yaml",
        )
    )
    base = EnrichedProjectSpec.from_planner(planner)
    spec = EnrichedProjectSpec(
        project_name=base.project_name,
        selected_target=base.selected_target,
        connector=base.connector,
        source_path=base.source_path,
        target_catalog=base.target_catalog,
        target_schema=base.target_schema,
        target_table=base.target_table,
        layer=base.layer,
        mode=base.mode,
        schema_path=base.schema_path,
        merge_keys=SpecValue(value=["order_id"], source="provider", confidence=0.8),
        hash_columns=SpecValue(value=["status", "amount"], source="provider", confidence=0.8),
    )

    validation = spec.validate()

    assert validation.status == "NEEDS_DECISIONS"
    assert any("Provider-suggested critical field" in warning for warning in validation.warnings)
    assert any(decision.path == "merge_keys" for decision in validation.decisions_required)


def test_enriched_project_spec_applies_safe_provider_updates():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a bronze ingestion from https://example.com/events into main.bronze.b_events.",
            schema_path="schemas/events.yaml",
        )
    )
    spec = EnrichedProjectSpec.from_planner(planner)

    enriched = spec.with_provider_enrichment(
        {
            "kind": "project_spec",
            "summary": "HTTP source likely returns JSON.",
            "field_updates": {
                "source_format": {"value": "json", "confidence": 0.86, "evidence": ["URL path and API wording indicate JSON."]},
                "shape": {"value": {"parse_json": [{"source": "raw_payload"}]}, "confidence": 0.72},
            },
            "confidence": 0.82,
            "review_required": True,
            "evidence": ["Context includes a JSON sample."],
        }
    )

    assert enriched.source_format is not None
    assert enriched.source_format.value == "json"
    assert enriched.source_format.source == "provider"
    assert enriched.shape is not None
    assert enriched.shape.value["parse_json"][0]["source"] == "raw_payload"


def test_enriched_project_spec_blocks_provider_override_of_known_identity_fields():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a bronze ingestion from s3a://landing/orders into main.bronze.b_orders using scd0_append.",
            schema_path="schemas/orders.yaml",
        )
    )
    spec = EnrichedProjectSpec.from_planner(planner)

    enriched = spec.with_provider_enrichment(
        {
            "kind": "project_spec",
            "summary": "Provider attempted to rewrite deterministic identity.",
            "field_updates": {
                "source_path": {"value": "s3a://other/orders", "confidence": 0.95},
                "target_table": {"value": "b_other_orders", "confidence": 0.95},
                "source_format": {"value": "json", "confidence": 0.8},
            },
            "confidence": 0.9,
        }
    )

    assert enriched.source_path.value == "s3a://landing/orders"
    assert enriched.target_table.value == "b_orders"
    assert enriched.source_format is not None
    assert enriched.source_format.value == "json"
    assert any(decision.path == "source_path" for decision in enriched.decisions_required)
    assert any(decision.path == "target_table" for decision in enriched.decisions_required)


def test_enriched_project_spec_provider_filled_identity_fields_remain_review_required():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a bronze ingestion from s3a://landing/orders.",
            schema_path="schemas/orders.yaml",
            default_catalog="main",
            default_schema="bronze",
        )
    )
    spec = EnrichedProjectSpec.from_planner(planner)

    enriched = spec.with_provider_enrichment(
        {
            "kind": "project_spec",
            "summary": "Provider inferred a missing target table.",
            "field_updates": {
                "target_table": {"value": "b_orders", "confidence": 0.7},
            },
            "confidence": 0.7,
        }
    )

    assert enriched.target_table.value == "b_orders"
    assert enriched.target_table.review_required is True
    assert enriched.validate().status == "NEEDS_DECISIONS"
    assert any(decision.path == "target_table" for decision in enriched.decisions_required)


def test_enriched_project_spec_accepts_full_contractforge_transform_updates():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a bronze ingestion from https://example.com/events into main.bronze.b_events.",
            schema_path="schemas/events.yaml",
        )
    )
    spec = EnrichedProjectSpec.from_planner(planner)

    enriched = spec.with_provider_enrichment(
        {
            "kind": "project_spec",
            "summary": "The provider proposed a full ContractForge transform block.",
            "field_updates": {
                "transform": {
                    "value": {
                        "shape": {
                            "parse_json": [
                                {
                                    "source_column": "raw_payload",
                                    "target_column": "payload",
                                    "schema": "STRUCT<event_id: STRING>",
                                }
                            ],
                            "flatten": [{"column": "payload"}],
                            "columns": {"event_id": "payload.event_id"},
                        }
                    },
                    "confidence": 0.78,
                    "evidence": ["The user requested JSON parsing and projection."],
                    "review_required": True,
                }
            },
            "confidence": 0.8,
            "review_required": True,
            "evidence": ["Context includes a JSON sample."],
        }
    )

    assert enriched.transform is not None
    assert enriched.transform.value["shape"]["parse_json"][0]["target_column"] == "payload"
    assert enriched.transform.value["shape"]["columns"] == {"event_id": "payload.event_id"}


def test_enriched_project_spec_forces_contract_mutating_provider_updates_to_review_required():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a bronze ingestion from https://example.com/events into main.bronze.b_events.",
            schema_path="schemas/events.yaml",
        )
    )
    spec = EnrichedProjectSpec.from_planner(planner)

    enriched = spec.with_provider_enrichment(
        {
            "kind": "project_spec",
            "summary": "The provider proposed behavior-changing contract fields as ready.",
            "field_updates": {
                "transform": {
                    "value": {"shape": {"columns": {"event_id": "payload.event_id"}}},
                    "confidence": 0.9,
                    "review_required": False,
                },
                "quality_rules": {
                    "value": {"not_null": ["event_id"]},
                    "confidence": 0.9,
                    "review_required": False,
                },
                "annotations": {
                    "value": {"table": {"description": "Provider generated description."}},
                    "confidence": 0.9,
                    "review_required": False,
                },
                "operations": {
                    "value": {"criticality": "high"},
                    "confidence": 0.9,
                    "review_required": False,
                },
            },
            "confidence": 0.9,
            "review_required": False,
        }
    )

    validation = enriched.validate()

    assert enriched.transform is not None
    assert enriched.transform.review_required is True
    assert enriched.quality_rules is not None
    assert enriched.quality_rules.review_required is True
    assert enriched.annotations is not None
    assert enriched.annotations.review_required is True
    assert validation.status == "NEEDS_DECISIONS"
    decision_paths = {decision.path for decision in validation.decisions_required}
    assert {"transform", "quality_rules", "annotations", "operations"}.issubset(decision_paths)


def test_enriched_project_spec_rejects_unsupported_provider_fields_as_decisions():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a bronze ingestion from /landing/orders into main.bronze.b_orders.",
            schema_path="schemas/orders.yaml",
        )
    )
    spec = EnrichedProjectSpec.from_planner(planner)

    enriched = spec.with_provider_enrichment(
        {
            "kind": "project_spec",
            "summary": "Unsupported mutation attempt.",
            "field_updates": {"credentials": "plain text"},
            "confidence": 0.9,
            "review_required": True,
            "evidence": [],
        }
    )

    assert enriched.validate().status == "NEEDS_DECISIONS"
    assert any(decision.path == "credentials" for decision in enriched.decisions_required)


def test_enriched_project_spec_keeps_provider_business_keys_review_required():
    planner = plan_project_from_intent(
        ProjectPlannerRequest(
            intent="Create a silver ingestion from s3a://landing/orders into main.silver.orders using scd1_hash_diff.",
            schema_path="schemas/orders.yaml",
        )
    )
    spec = EnrichedProjectSpec.from_planner(planner)

    enriched = spec.with_provider_enrichment(
        {
            "kind": "project_spec",
            "summary": "The sample suggests order_id is a candidate key.",
            "field_updates": {
                "merge_keys": {"value": ["order_id"], "confidence": 0.78, "evidence": ["The sample contains order_id."]},
                "hash_columns": {"value": ["status", "amount"], "confidence": 0.76},
            },
            "confidence": 0.8,
            "review_required": True,
            "evidence": ["Context includes an orders sample."],
        }
    )

    validation = enriched.validate()

    assert enriched.merge_keys is not None
    assert enriched.merge_keys.review_required is True
    assert enriched.hash_columns is not None
    assert enriched.hash_columns.review_required is True
    assert validation.status == "NEEDS_DECISIONS"
    assert any(decision.path == "merge_keys" for decision in validation.decisions_required)
