import json
from pathlib import Path

import yaml

from contractforge_ai.providers import GenerationOptions
from contractforge_ai.projects.guided import GuidedProjectRequest, generate_guided_project


class FakeProvider:
    name = "fake"

    def __init__(self, output: str):
        self.output = output
        self.request = None

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        self.request = {"prompt": prompt, "system": system, "options": options}
        return self.output


class ReportTranslationProvider:
    name = "fake"

    def __init__(self):
        self.requests: list[dict[str, object]] = []

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        self.requests.append({"prompt": prompt, "system": system, "options": options})
        if prompt.startswith("Target language:"):
            payload = json.loads(prompt.rsplit("Translate the text values in this JSON payload:", 1)[-1])
            return json.dumps(
                {
                    "translations": [
                        {"id": item["id"], "text": f"TRADUZIDO: {item['text']}"}
                        for item in payload["segments"]
                    ]
                }
            )
        return json.dumps(
            {
                "kind": "project_spec",
                "summary": "No additional project changes are required.",
                "field_updates": {},
                "recommendations": [],
                "evidence": ["Schema evidence is sufficient for the draft."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )


def test_guided_project_attaches_validation_and_critique(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from /landing/orders into main.bronze.b_orders.",
            schema_path=str(schema),
            preferred_target="contractforge-yaml",
            allow_review_required=True,
        )
    )

    assert result.project is not None
    assert result.validation is not None
    assert result.critique is not None
    assert result.context_snapshot is not None
    assert result.generation_signature is not None
    assert result.policy_result is not None
    assert result.audit_trail is not None
    assert result.validation.status in {"READY", "NEEDS_DECISIONS"}
    assert result.critique.status in {"READY", "NEEDS_DECISIONS"}
    assert result.to_dict()["validation"] is not None
    assert result.to_dict()["critique"] is not None
    assert result.to_dict()["generation_signature"]["signature_hash"]
    assert result.to_dict()["audit_trail"]["last_hash"]
    assert not any(artifact.path == "AI_REVIEW.md" for artifact in result.project.artifacts)
    assert not any(artifact.path == "README.md" for artifact in result.project.artifacts)
    assert any(artifact.path == "AI_REVIEW.html" for artifact in result.project.artifacts)


def test_guided_project_with_allowed_review_decisions_is_not_marked_ready(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a silver ingestion from s3a://landing/orders into main.silver.orders using scd1_hash_diff.",
            schema_path=str(schema),
            allow_review_required=True,
        )
    )

    payload = result.to_dict()

    assert result.project is not None
    assert result.status == "NEEDS_DECISIONS"
    assert payload["validation"] is not None
    assert payload["critique"] is not None
    assert payload["critique"]["decisions_required"]


def test_guided_project_context_generation_keeps_context_and_validation(tmp_path: Path):
    context_dir = tmp_path / "context"
    context_dir.mkdir()
    (context_dir / "orders.json").write_text(json.dumps([{"order_id": "A-1", "amount": 10.5}]), encoding="utf-8")

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from /landing/orders into main.bronze.b_orders.",
            context_dir=str(context_dir),
            runtime="serverless",
            allow_review_required=True,
        )
    )

    assert result.project is not None
    assert result.context is not None
    assert result.validation is not None
    assert result.critique is not None
    assert not any(artifact.path == "CONTEXT.md" for artifact in result.project.artifacts)
    assert any(artifact.path == "context/context-package.json" for artifact in result.project.artifacts)
    review = next(artifact for artifact in result.project.artifacts if artifact.path == "AI_REVIEW.html")
    assert "ContractForge AI Project Review" in review.content
    assert '<section class="hero">' in review.content
    assert '<section class="grid">' in review.content
    assert "Requested Project" in review.content
    assert "Deterministic Validation" in review.content
    assert "Critique Findings" in review.content
    assert "Generated Artifacts" in review.content
    assert "Consolidated Project Guide" in review.content
    assert "Review checklist and required decisions" in review.content
    assert "Generated project overview" in review.content
    assert "Operational runbook" in review.content
    assert "Generated contract validation report" in review.content
    assert "Project synthesis context summary" in review.content
    assert "Validation Commands" in review.content
    assert "Traceability" in review.content
    assert "Signature" in review.content
    assert "Context" in review.content
    assert "Last audit hash" in review.content
    assert "Traceability and Governance Evidence" not in review.content
    assert "Provider Proposal Audit" not in review.content
    assert "Generation Governance" not in review.content
    assert "<pre><code class=\"language-bash\">" in review.content
    assert review.content.index("Recommended Next Actions") < review.content.index("Decisions Required Before Use")
    assert review.content.index("AI Guidance") < review.content.index("Consolidated Project Guide")
    assert review.content.index("Deterministic Validation") < review.content.index("Generated Artifacts")
    assert review.content.index("Generated Artifacts") < review.content.index("Context Evidence")


def test_guided_project_uses_provider_enriched_spec_before_generation(tmp_path: Path):
    schema = tmp_path / "events.json"
    schema.write_text(
        '{"columns": [{"name": "raw_payload", "type": "STRING", "nullable": true}]}',
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "HTTP events source should be read as JSON and parsed with shape.",
                "field_updates": {
                    "source_format": {"value": "json", "confidence": 0.88, "evidence": ["Context includes JSON payload."]},
                    "transform": {
                        "value": {
                            "shape": {
                                "parse_json": [
                                    {
                                        "source_column": "raw_payload",
                                        "target_column": "payload",
                                        "schema": "STRUCT<event_id: STRING, amount: DOUBLE>",
                                    }
                                ],
                                "flatten": [{"column": "payload"}],
                            }
                        },
                        "confidence": 0.76,
                        "review_required": False,
                    },
                    "quality_rules": {
                        "value": {"not_null": ["raw_payload"]},
                        "confidence": 0.7,
                        "review_required": False,
                    },
                },
                "evidence": ["Context package includes an event sample."],
                "assumptions": ["The sample is representative enough for draft generation."],
                "decisions_required": ["Confirm whether raw_payload can be dropped after parsing."],
                "confidence": 0.8,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from https://example.com/events into main.bronze.b_events.",
            schema_path=str(schema),
            preferred_target="contractforge-yaml",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    assert result.spec_enrichment is not None
    assert result.spec_enrichment.status == "ENRICHED"
    ingestion = next(artifact for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml"))
    payload = yaml.safe_load(ingestion.content)

    assert payload["source"]["format"] == "json"
    assert payload["transform"]["shape"]["parse_json"][0]["column"] == "raw_payload"
    assert payload["transform"]["shape"]["parse_json"][0]["alias"] == "payload"
    assert payload["transform"]["shape"]["flatten"]["column"] == "payload"
    assert payload["quality_rules"]["not_null"] == ["raw_payload"]
    assert result.spec is not None
    assert result.spec.transform is not None
    assert result.spec.transform.review_required is True
    assert result.provider_proposal_audit is not None
    assert result.provider_proposal_audit.review_required_count >= 1
    outcomes = {decision.field_path: decision.outcome for decision in result.provider_proposal_audit.decisions}
    assert outcomes["transform"] == "requires_review"
    assert outcomes["quality_rules"] == "requires_review"
    assert "https://example.com/events" in provider.request["prompt"]


def test_guided_project_audit_rejects_provider_identity_overrides(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider attempted to rewrite deterministic identity.",
                "field_updates": {
                    "source_path": {"value": "s3a://other/orders", "confidence": 0.95},
                    "target_table": {"value": "b_other_orders", "confidence": 0.95},
                    "source_format": {"value": "json", "confidence": 0.8},
                    "credentials": "plain text",
                },
                "evidence": ["Synthetic provider suggestion."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.85,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from s3a://landing/orders into main.bronze.b_orders using scd0_append.",
            schema_path=str(schema),
            preferred_target="contractforge-yaml",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))
    outcomes = {decision.field_path: decision.outcome for decision in result.provider_proposal_audit.decisions}

    assert ingestion["source"]["path"] == "s3a://landing/orders"
    assert ingestion["target"]["table"] == "b_orders"
    assert ingestion["source"]["format"] == "json"
    assert outcomes["source_path"] == "rejected"
    assert outcomes["target_table"] == "rejected"
    assert outcomes["source_format"] == "accepted"
    assert outcomes["credentials"] == "rejected"


def test_guided_dab_materializes_explicit_prompt_operations_quality_and_serverless(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}, {"name": "currency", "type": "STRING"}]}),
        encoding="utf-8",
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent=(
                "Create a bronze DAB ingestion from s3a://landing/orders into main.bronze.b_orders using serverless. "
                "Business owner: revenue-analytics. Technical owner: data-engineering. Steward: data-governance. "
                "Criticality: high. Expected frequency: daily. SLA: 120 minutes. Alert on failure and alert on quality failure. "
                "Required columns: order_id, amount. Unique key: order_id. amount must be >= 0. "
                "currency accepted values: USD, EUR, BRL."
            ),
            schema_path=str(schema),
            preferred_target="databricks-dab",
            allow_review_required=True,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))
    operations = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".operations.yaml")))
    databricks_yml = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "databricks.yml"))
    jobs_yml = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "resources/jobs.yml"))

    assert ingestion["quality_rules"]["not_null"] == ["order_id", "amount"]
    assert ingestion["quality_rules"]["unique_key"] == ["order_id"]
    assert ingestion["quality_rules"]["accepted_values"]["currency"] == ["USD", "EUR", "BRL"]
    assert ingestion["quality_rules"]["expressions"][0]["expression"] == "amount >= 0"
    assert all(rule["expression"] != "be >= 0" for rule in ingestion["quality_rules"]["expressions"])
    assert operations["business_owner"] == "revenue-analytics"
    assert operations["technical_owner"] == "data-engineering"
    assert operations["criticality"] == "high"
    assert operations["freshness_sla_minutes"] == 120
    assert "variables" not in databricks_yml
    task = next(iter(jobs_yml["resources"]["jobs"].values()))["tasks"][0]
    assert task["environment_key"] == "default"
    assert "existing_cluster_id" not in task


def test_guided_project_emits_canonical_hash_keys_and_shape_columns(tmp_path: Path):
    schema = tmp_path / "customers.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "customer_id", "type": "STRING"},
                    {"name": "email", "type": "STRING"},
                    {"name": "status", "type": "STRING"},
                    {"name": "updated_at", "type": "TIMESTAMP"},
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider supplied canonical project refinements.",
                "field_updates": {
                    "merge_keys": {"value": ["customer_id"], "confidence": 0.8},
                    "hash_columns": {"value": ["email", "status", "updated_at"], "confidence": 0.8},
                    "shape": {"value": {"columns": ["customer_id", "email"]}, "confidence": 0.7},
                },
                "evidence": ["Schema evidence includes the requested columns."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.75,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent=(
                "Create an AWS Glue Iceberg silver ingestion from "
                "jdbc:postgresql://host/db into analytics.silver.s_customers using scd1_hash_diff. "
                "Required columns: customer_id. Unique key: customer_id."
            ),
            schema_path=str(schema),
            preferred_target="aws-glue-iceberg",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    assert "hash_columns" not in ingestion
    assert ingestion["hash_keys"] == ["email", "status", "updated_at"]
    assert ingestion["transform"]["shape"]["columns"] == {"customer_id": "customer_id", "email": "email"}


def test_guided_project_normalizes_provider_parse_json_projection_to_shape_columns(tmp_path: Path):
    schema = tmp_path / "products.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "product_id", "type": "STRING"}, {"name": "price", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider confused parse_json with output projection.",
                "field_updates": {
                    "shape": {
                        "value": {"parse_json": {"columns": ["product_id", "price"]}},
                        "confidence": 0.7,
                    }
                },
                "evidence": ["The requested output columns are known."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent=(
                "Create a ContractForge Python project from https://example.com/products.json into "
                "analytics.bronze.b_products using append. Required columns: product_id, price. price must be >= 0."
            ),
            schema_path=str(schema),
            preferred_target="contractforge-python",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    shape = ingestion["transform"]["shape"]
    assert "parse_json" not in shape
    assert shape["columns"] == {"product_id": "product_id", "price": "price"}


def test_guided_project_drops_provider_shape_type_marker(tmp_path: Path):
    schema = tmp_path / "products.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "product_id", "type": "STRING"}, {"name": "price", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider added a non-canonical shape type marker.",
                "field_updates": {
                    "transform": {
                        "value": {
                            "shape": {
                                "type": "columns",
                                "columns": {"product_id": "product_id", "price": "price"},
                            }
                        },
                        "confidence": 0.72,
                    }
                },
                "evidence": ["The requested output columns are known."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from https://example.com/products.json into analytics.bronze.b_products using overwrite.",
            schema_path=str(schema),
            preferred_target="contractforge-yaml",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    shape = ingestion["transform"]["shape"]
    assert "type" not in shape
    assert shape["columns"] == {"product_id": "product_id", "price": "price"}


def test_guided_project_drops_empty_provider_shape(tmp_path: Path):
    schema = tmp_path / "products.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "raw_response", "type": "STRING"}]}),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider returned an empty shape block.",
                "field_updates": {
                    "transform": {
                        "value": {"shape": {"columns": {}}},
                        "confidence": 0.72,
                    }
                },
                "evidence": ["No shape mapping was actually supplied."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from https://example.com/products.json into analytics.bronze.b_products using overwrite.",
            schema_path=str(schema),
            preferred_target="gcp-bigquery",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    assert "transform" not in ingestion or "shape" not in ingestion["transform"]


def test_guided_project_filters_provider_shape_when_target_does_not_support_it(tmp_path: Path):
    schema = tmp_path / "geojson.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "raw_response", "type": "STRING"},
                    {"name": "response_page_number", "type": "LONG"},
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider suggested a shape projection for GCP.",
                "field_updates": {
                    "transform": {
                        "value": {
                            "shape": {
                                "columns": {
                                    "raw_response": "raw_response",
                                    "parsed_response": "parsed_response",
                                }
                            }
                        },
                        "confidence": 0.72,
                    }
                },
                "evidence": ["The prompt requested a raw response contract."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent=(
                "Create a production-ready bronze ContractForge ingestion project for GCP BigQuery. "
                "Read https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson "
                "and write into contractforge.cf_ai_usgs_bronze.b_usgs_earthquake_geojson using overwrite."
            ),
            schema_path=str(schema),
            preferred_target="gcp-bigquery",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    assert "transform" not in ingestion or "shape" not in ingestion["transform"]


def test_guided_project_moves_provider_shape_schema_policy_to_contract_root(tmp_path: Path):
    schema = tmp_path / "products.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "raw_response", "type": "STRING"}]}),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider placed schema_policy under shape.",
                "field_updates": {
                    "transform": {
                        "value": {"shape": {"schema_policy": "permissive", "columns": {"raw_response": "raw_response"}}},
                        "confidence": 0.72,
                    }
                },
                "evidence": ["The prompt requested permissive schema handling."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from https://example.com/products.json into lakehouse.bronze.b_products using overwrite.",
            schema_path=str(schema),
            preferred_target="fabric-lakehouse",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    assert ingestion["schema_policy"] == "permissive"
    assert "schema_policy" not in ingestion["transform"]["shape"]
    assert ingestion["transform"]["shape"]["columns"] == {"raw_response": "raw_response"}


def test_guided_project_drops_unknown_provider_shape_keys(tmp_path: Path):
    schema = tmp_path / "geojson.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "raw_response", "type": "STRING"}]}),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider emitted a non-canonical shape helper field.",
                "field_updates": {
                    "transform": {
                        "value": {
                            "shape": {
                                "raw_response_column": "raw_response",
                                "columns": {"raw_response": "raw_response"},
                            }
                        },
                        "confidence": 0.72,
                    }
                },
                "evidence": ["The prompt requested raw response handling."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from https://example.com/feed.geojson into CONTRACTFORGE_TEST_DB.PUBLIC.B_GEOJSON using overwrite.",
            schema_path=str(schema),
            preferred_target="snowflake-sql-warehouse",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    assert "raw_response_column" not in ingestion["transform"]["shape"]
    assert ingestion["transform"]["shape"]["columns"] == {"raw_response": "raw_response"}


def test_guided_project_drops_incomplete_provider_parse_json_items(tmp_path: Path):
    schema = tmp_path / "products.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "product_id", "type": "STRING"}, {"name": "price", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    provider = FakeProvider(
        json.dumps(
            {
                "kind": "project_spec",
                "summary": "Provider returned an incomplete parse_json suggestion.",
                "field_updates": {
                    "shape": {
                        "value": {"parse_json": [{}], "columns": ["product_id"]},
                        "confidence": 0.7,
                    }
                },
                "evidence": ["The parse_json rule was not complete."],
                "assumptions": [],
                "decisions_required": [],
                "confidence": 0.7,
                "review_required": True,
            }
        )
    )

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from https://example.com/products.json into analytics.bronze.b_products using append.",
            schema_path=str(schema),
            preferred_target="contractforge-yaml",
            allow_review_required=True,
            provider=provider,
        )
    )

    assert result.project is not None
    ingestion = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path.endswith(".ingestion.yaml")))

    shape = ingestion["transform"]["shape"]
    assert "parse_json" not in shape
    assert shape["columns"] == {"product_id": "product_id"}


def test_guided_project_translates_report_with_provider_when_language_is_requested(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        '{"columns": [{"name": "order_id", "type": "STRING", "nullable": false}]}',
        encoding="utf-8",
    )
    provider = ReportTranslationProvider()

    result = generate_guided_project(
        GuidedProjectRequest(
            intent="Create a bronze ingestion from /landing/orders into main.bronze.b_orders.",
            schema_path=str(schema),
            preferred_target="contractforge-yaml",
            allow_review_required=True,
            provider=provider,
            language="pt-BR",
        )
    )

    assert result.project is not None
    review = next(artifact for artifact in result.project.artifacts if artifact.path == "AI_REVIEW.html")
    assert "TRADUZIDO:" in review.content
    assert "Status:" in review.content
    assert "NEEDS_DECISIONS" in review.content
    translation_requests = [request for request in provider.requests if str(request["prompt"]).startswith("Target language:")]
    assert len(translation_requests) == 2
    assert "Target language: pt-BR" in translation_requests[0]["prompt"]
    assert "Return JSON only" in translation_requests[0]["system"]
