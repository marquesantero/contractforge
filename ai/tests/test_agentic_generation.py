import json
from pathlib import Path

import yaml

from contractforge_ai.agentic import IntentGenerationRequest, analyze_project_state, generate_from_intent, interpret_intent, plan_project_gaps
from contractforge_ai.generators.environments import aws_glue_iceberg_environment_payload, databricks_environment_payload
from contractforge_ai.project_structure import validate_project_structure
from contractforge_ai.providers import GenerationOptions


class FakeProvider:
    name = "fake"

    def __init__(self, output: str):
        self.output = output
        self.requests: list[dict[str, object]] = []

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        self.requests.append({"prompt": prompt, "system": system, "options": options})
        return self.output


class SequenceProvider:
    name = "fake"

    def __init__(self, outputs: list[str]):
        self.outputs = outputs
        self.requests: list[dict[str, object]] = []

    def complete(self, prompt: str, *, system: str | None = None, options: GenerationOptions | None = None) -> str:
        self.requests.append({"prompt": prompt, "system": system, "options": options})
        return self.outputs.pop(0)


def test_adapter_environment_payload_helpers_keep_platform_details_out_of_contracts():
    databricks = databricks_environment_payload()
    aws = aws_glue_iceberg_environment_payload("orders")

    assert databricks["adapter"] == "databricks"
    assert databricks["evidence"] == {"catalog": "main", "schema": "ops"}
    assert databricks["runtime"] == {"kind": "classic_cluster"}
    assert aws["adapter"] == "aws"
    assert aws["runtime"]["runtime"] == "aws_glue_spark"
    assert aws["artifacts"]["uri"] == "s3://review-required-contractforge-artifacts/orders/"
    assert "source" not in databricks
    assert "source" not in aws


VALID_PROJECT_SPEC_TRANSFORM_OUTPUT = """
{
  "kind": "project_spec",
  "summary": "A safe target projection can map total_amount to the existing amount column.",
  "field_updates": {
    "shape_columns": {
      "value": {
        "total_amount": "amount"
      },
      "confidence": 0.83,
      "evidence": ["The requested final column total_amount is semantically close to schema column amount."],
      "review_required": false
    }
  },
  "recommendations": ["Review the renamed projection before deployment."],
  "evidence": ["Schema evidence contains amount."],
  "assumptions": ["total_amount should be sourced from amount."],
  "decisions_required": [],
  "confidence": 0.83,
  "review_required": true
}
"""


MIXED_PROJECT_SPEC_TRANSFORM_OUTPUT = """
{
  "kind": "project_spec",
  "summary": "One projection is safe and two require policy handling.",
  "field_updates": {
    "shape_columns": {
      "value": {
        "total_amount": "amount",
        "bad-name": "amount",
        "customer_segment": "segment"
      },
      "confidence": 0.72,
      "evidence": ["Provider compared requested columns with source schema."],
      "review_required": false
    }
  },
  "recommendations": ["Review rejected and ambiguous transformation suggestions."],
  "evidence": ["Schema evidence contains amount but not segment."],
  "assumptions": ["total_amount should be sourced from amount."],
  "decisions_required": [],
  "confidence": 0.72,
  "review_required": true
}
"""


FULL_PROJECT_SPEC_TRANSFORM_OUTPUT = """
{
  "kind": "project_spec",
  "summary": "The request needs a full ContractForge transform block, not only column projection.",
  "field_updates": {
    "transform": {
      "value": {
        "shape": {
          "parse_json": [
            {
              "source_column": "raw_payload",
              "target_column": "payload",
              "schema": "STRUCT<order_id: STRING, amount: DOUBLE>"
            }
          ],
          "flatten": [{"column": "payload"}],
          "columns": {
            "order_id": "payload.order_id",
            "total_amount": "payload.amount"
          }
        }
      },
      "confidence": 0.82,
      "evidence": ["The prompt requested JSON parsing, flattening and final projection."],
      "review_required": true
    }
  },
  "recommendations": ["Review JSON parsing and flattening before production use."],
  "evidence": ["Schema contains raw_payload."],
  "assumptions": ["raw_payload contains the documented JSON structure."],
  "decisions_required": [],
  "confidence": 0.82,
  "review_required": true
}
"""


UNSAFE_PROJECT_SPEC_TRANSFORM_OUTPUT = """
{
  "kind": "project_spec",
  "summary": "The provider suggests a full transform and an unsupported runtime field.",
  "field_updates": {
    "transform": {
      "value": {
        "shape": {
          "columns": {
            "order_id": "order_id"
          }
        }
      },
      "confidence": 0.82,
      "evidence": ["The prompt requested an order projection."],
      "review_required": false
    },
    "runtime_secret": {
      "value": "{{ secret:scope/key }}",
      "confidence": 0.90,
      "evidence": ["Provider guessed a runtime secret reference."],
      "review_required": false
    }
  },
  "recommendations": ["Review generated runtime assumptions."],
  "evidence": ["Schema contains order_id."],
  "assumptions": [],
  "decisions_required": [],
  "confidence": 0.82,
  "review_required": true
}
"""


VALID_PROJECT_PLAN_OUTPUT = """
{
  "kind": "project_plan",
  "summary": "Review SCD keys and source format before materializing the project.",
  "recommendations": ["Confirm stable merge keys before approving generated contracts."],
  "evidence": ["The pre-generation plan uses scd1_hash_diff."],
  "assumptions": ["The provided schema is representative."],
  "decisions_required": ["Confirm merge keys and hash-diff exclusions."],
  "confidence": 0.86,
  "review_required": true
}
"""


def test_generate_from_intent_creates_medallion_contracts(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "order_id", "type": "STRING", "nullable": False},
                    {"name": "customer_id", "type": "STRING", "nullable": True},
                    {"name": "amount", "type": "DOUBLE", "nullable": True},
                    {"name": "order_date", "type": "DATE", "nullable": True},
                    {"name": "status", "type": "STRING", "nullable": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Use table main.raw.orders_sample and create a bronze to gold project. "
                "Silver must use scd1_hash_diff. Gold final columns: order_id, customer_id, amount, order_date, status."
            ),
            schema_path=str(schema),
        )
    )

    assert result.project is not None
    assert result.layers == ["bronze", "silver", "gold"]
    paths = {artifact.path for artifact in result.project.artifacts}

    assert "contracts/bronze/b_orders.ingestion.yaml" in paths
    assert "contracts/silver/s_orders.ingestion.yaml" in paths
    assert "contracts/gold/g_orders.ingestion.yaml" in paths
    assert "AI_REVIEW.html" in paths
    assert "README.md" not in paths
    assert "DECISIONS.md" not in paths

    bronze = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/bronze/b_orders.ingestion.yaml"))
    silver = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/silver/s_orders.ingestion.yaml"))
    gold = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/gold/g_orders.ingestion.yaml"))
    review = next(artifact.content for artifact in result.project.artifacts if artifact.path == "AI_REVIEW.html")

    assert bronze["source"]["type"] == "connection"
    assert bronze["source"]["connection_path"] == "project://connections/bronze_source.yaml"
    assert bronze["source"]["table"] == "main.raw.orders_sample"
    assert silver["source"]["type"] == "connection"
    assert silver["source"]["connection_path"] == "project://connections/silver_source.yaml"
    assert silver["source"]["table"] == "main.bronze.b_orders"
    assert silver["mode"] == "hash_diff_upsert"
    assert gold["source"]["type"] == "connection"
    assert gold["source"]["connection_path"] == "project://connections/gold_source.yaml"
    assert gold["source"]["table"] == "main.silver.s_orders"
    assert gold["transform"]["shape"]["columns"] == {
        "order_id": "order_id",
        "customer_id": "customer_id",
        "amount": "amount",
        "order_date": "order_date",
        "status": "status",
    }
    assert "ContractForge AI Generation Review" in review


def test_generate_from_intent_materializes_explicit_quality_and_operations(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "order_id", "type": "STRING"},
                    {"name": "amount", "type": "DOUBLE"},
                    {"name": "currency", "type": "STRING"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Use table main.raw.orders_sample and create a bronze to gold project. "
                "Business owner: revenue-analytics. Technical owner: data-engineering. Criticality: high. "
                "Expected frequency: daily. SLA: 120 minutes. Alert on failure and alert on quality failure. "
                "Required columns: order_id, amount. Unique key: order_id. amount must be >= 0. "
                "currency accepted values: USD, EUR, BRL. Gold final columns: order_id, amount, currency."
            ),
            schema_path=str(schema),
        )
    )

    assert result.project is not None
    gold = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/gold/g_orders.ingestion.yaml"))
    operations = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/gold/g_orders.operations.yaml"))

    assert gold["quality_rules"]["not_null"] == ["order_id", "amount"]
    assert gold["quality_rules"]["unique_key"] == ["order_id"]
    assert gold["quality_rules"]["accepted_values"]["currency"] == ["USD", "EUR", "BRL"]
    assert gold["quality_rules"]["expressions"][0]["expression"] == "amount >= 0"
    assert operations["business_owner"] == "revenue-analytics"
    assert operations["technical_owner"] == "data-engineering"
    assert operations["criticality"] == "high"
    assert operations["freshness_sla_minutes"] == 120


def test_generate_from_intent_requires_schema_or_table_evidence():
    result = generate_from_intent(
        IntentGenerationRequest(
            prompt="Create a bronze to gold project from orders using scd1_hash_diff.",
        )
    )

    assert result.status == "NEEDS_DECISIONS"
    assert result.project is not None
    assert result.project.artifacts[0].path == "AI_REVIEW.html"
    assert "schema evidence is required" in result.project.artifacts[0].content
    assert result.policy_result is not None
    assert result.policy_result.action == "block"
    assert result.generation_signature is not None
    assert result.generation_signature.signature_hash
    assert result.audit_trail is not None
    assert result.audit_trail.last_hash


def test_interpret_intent_detects_silver_only_and_final_columns():
    intent = interpret_intent(
        "Only silver from main.bronze.b_orders into main.silver.s_orders using scd1_upsert. "
        "Final columns: order_id, amount."
    )

    assert intent.requested_layers == ["silver"]
    assert intent.source == "main.bronze.b_orders"
    assert intent.target_table == "main.silver.s_orders"
    assert intent.base_name == "orders"
    assert intent.final_columns == ["order_id", "amount"]
    assert intent.silver_mode == "upsert"


def test_interpret_intent_detects_platform_hints():
    aws_intent = interpret_intent(
        "Create an AWS Glue bronze project from s3://landing/orders "
        "into analytics.bronze.b_orders using scd0_append."
    )
    databricks_intent = interpret_intent(
        "Create a Databricks Asset Bundle bronze project from /Volumes/raw/orders "
        "into main.bronze.b_orders using scd0_append."
    )

    assert "aws" in aws_intent.platform_hints
    assert "databricks" not in aws_intent.platform_hints
    assert "databricks" in databricks_intent.platform_hints
    assert "aws" not in databricks_intent.platform_hints


def test_interpret_intent_uses_output_target_as_platform_hint():
    aws_intent = interpret_intent(
        "Create a bronze project from s3://landing/orders into analytics.bronze.b_orders.",
        output_target="aws-glue-iceberg",
    )
    databricks_intent = interpret_intent(
        "Create a bronze project from /Volumes/raw/orders into main.bronze.b_orders.",
        output_target="databricks-dab",
    )

    assert aws_intent.platform_hints == ["aws"]
    assert databricks_intent.platform_hints == ["databricks"]


def test_generate_from_intent_adds_aws_environment_without_platform_contract_fields(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create an AWS Glue bronze project from s3://landing/orders "
                "into analytics.bronze.b_orders using scd0_append."
            ),
            schema_path=str(schema),
        )
    )

    assert result.intent is not None
    assert result.project is not None
    assert "aws" in result.intent.platform_hints
    artifacts = {artifact.path: artifact for artifact in result.project.artifacts}
    project = yaml.safe_load(artifacts["project.yaml"].content)
    environment = yaml.safe_load(artifacts["environments/aws.environment.yaml"].content)
    contract = yaml.safe_load(artifacts["contracts/bronze/b_orders.ingestion.yaml"].content)

    assert project["environments"] == {
        "review": "environments/review.environment.yaml",
        "aws": "environments/aws.environment.yaml",
    }
    assert project["execution_order"][0]["contracts"]["review"] == "contracts/bronze/b_orders.ingestion.yaml"
    assert project["execution_order"][0]["contracts"]["aws"] == "contracts/bronze/b_orders.ingestion.yaml"
    assert environment["adapter"] == "aws"
    assert environment["runtime"]["runtime"] == "aws_glue_spark"
    assert environment["artifacts"]["uri"].startswith("s3://review-required-")
    assert environment["parameters"]["aws"]["iceberg"]["warehouse"].startswith("s3://review-required-")
    assert environment["parameters"]["aws"]["dependencies"]["extra_py_files"][0].startswith("s3://review-required-")
    assert environment["parameters"]["aws"]["glue_job"]["role_arn"] == "REVIEW_REQUIRED"
    assert "job_bookmarks" not in environment["parameters"]["aws"]
    assert set(environment["parameters"]["aws"]["glue_job"]) == {"role_arn"}
    assert "extensions" not in contract
    assert contract["source"]["type"] == "connection"

    for artifact in result.project.artifacts:
        target = tmp_path / "project" / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact.content, encoding="utf-8")
    structure = validate_project_structure(tmp_path / "project", adapters=("aws",))
    assert structure.status in {"READY", "READY_WITH_WARNINGS", "NEEDS_DECISIONS"}
    assert all(finding.code != "project_structure.ingestion_bundle.invalid" for finding in structure.findings)


def test_generate_from_intent_adds_databricks_environment_without_platform_contract_fields(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create a Databricks Asset Bundle bronze project from /Volumes/raw/orders "
                "into main.bronze.b_orders using scd0_append."
            ),
            schema_path=str(schema),
        )
    )

    assert result.intent is not None
    assert result.project is not None
    assert "databricks" in result.intent.platform_hints
    artifacts = {artifact.path: artifact for artifact in result.project.artifacts}
    project = yaml.safe_load(artifacts["project.yaml"].content)
    environment = yaml.safe_load(artifacts["environments/databricks.environment.yaml"].content)
    contract = yaml.safe_load(artifacts["contracts/bronze/b_orders.ingestion.yaml"].content)

    assert project["environments"] == {
        "review": "environments/review.environment.yaml",
        "databricks": "environments/databricks.environment.yaml",
    }
    assert project["execution_order"][0]["contracts"]["databricks"] == "contracts/bronze/b_orders.ingestion.yaml"
    assert environment["adapter"] == "databricks"
    assert environment["evidence"]["schema"] == "ops"
    assert "extensions" not in contract
    assert contract["source"]["type"] == "connection"


def test_project_state_and_gap_plan_preserve_existing_bronze(tmp_path: Path):
    project = tmp_path / "project"
    contract_dir = project / "contracts" / "bronze"
    contract_dir.mkdir(parents=True)
    (contract_dir / "b_orders.ingestion.yaml").write_text(
        yaml.safe_dump(
            {
                "source": {"connector": "files", "path": "/landing/orders"},
                "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
                "layer": "bronze",
                "mode": "scd0_append",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    intent = interpret_intent("Complete the project to gold from main.bronze.b_orders. Gold final columns: order_id, amount.")
    state = analyze_project_state(project)
    plan = plan_project_gaps(intent, state)

    assert state.layers == ["bronze"]
    assert [action.action for action in plan.actions] == ["preserve", "generate", "generate"]
    assert plan.actions[0].existing_contract == "contracts/bronze/b_orders.ingestion.yaml"
    assert plan.actions[1].source_table == "main.bronze.b_orders"


def test_generate_from_intent_uses_existing_bronze_context(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    project = tmp_path / "project"
    bronze_dir = project / "contracts" / "bronze"
    bronze_dir.mkdir(parents=True)
    (bronze_dir / "b_orders.ingestion.yaml").write_text(
        yaml.safe_dump(
            {
                "source": {"connector": "files", "path": "/landing/orders"},
                "target": {"catalog": "main", "schema": "bronze", "table": "b_orders"},
                "layer": "bronze",
                "mode": "scd0_append",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt="Complete the existing orders project to gold. Gold final columns: order_id, amount.",
            schema_path=str(schema),
            project_root=str(project),
            default_catalog="main",
        )
    )

    assert result.project is not None
    assert result.layers == ["silver", "gold"]
    paths = {artifact.path for artifact in result.project.artifacts}
    assert "contracts/bronze/b_orders.ingestion.yaml" not in paths
    assert "contracts/silver/s_orders.ingestion.yaml" in paths
    assert "contracts/gold/g_orders.ingestion.yaml" in paths
    review = next(artifact.content for artifact in result.project.artifacts if artifact.path == "AI_REVIEW.html")
    assert "Traceability" in review
    assert "Existing layers" in review
    assert "Gap Plan" in review
    assert "Policy:" in review
    assert "Last audit hash" in review
    assert "Generation Audit" not in review


def test_generate_from_intent_keeps_unknown_final_columns_as_decisions(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt="Create gold from main.silver.s_orders. Final columns: order_id, customer_segment.",
            schema_path=str(schema),
        )
    )

    assert result.transformation_plan is not None
    assert result.transformation_plan.shape_columns == {"order_id": "order_id"}
    assert result.policy_result is not None
    assert result.policy_result.action == "review_required"
    assert any("customer_segment" in decision.question for decision in result.transformation_plan.decisions_required)
    gold = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/gold/g_orders.ingestion.yaml"))
    assert gold["transform"]["shape"]["columns"] == {"order_id": "order_id"}


def test_generate_from_intent_runs_provider_before_artifact_materialization(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    provider = SequenceProvider([VALID_PROJECT_SPEC_TRANSFORM_OUTPUT, VALID_PROJECT_PLAN_OUTPUT, VALID_PROJECT_PLAN_OUTPUT])

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create a gold ingestion from s3a://landing/orders into main.gold.g_orders using scd1_hash_diff. "
                "Final columns: order_id, total_amount."
            ),
            schema_path=str(schema),
            provider=provider,
        )
    )

    assert result.pre_generation_enrichment is not None
    assert result.pre_generation_enrichment.status == "ENRICHED"
    assert result.transformation_enrichment is not None
    assert result.transformation_enrichment.status == "ENRICHED"
    assert result.pre_generation_enrichment.data["summary"].startswith("Review SCD keys")
    assert result.enrichment is not None
    assert len(provider.requests) == 3
    assert "<project_spec>" in provider.requests[0]["prompt"]
    assert '"status": "PRE_GENERATION_REVIEW"' in provider.requests[1]["prompt"]
    assert "project_plan_enrichment_v1" == provider.requests[1]["options"].response_schema_name
    assert result.transformation_plan.shape_columns["total_amount"] == "amount"
    assert result.provider_proposal_audit is not None
    assert result.provider_proposal_audit.accepted_count == 1
    assert result.provider_proposal_audit.rejected_count == 0
    assert result.provider_proposal_audit.review_required_count == 0
    assert any(event.stage == "provider_pre_generation" for event in result.audit_trail.events)
    assert any(event.stage == "provider_transformation_refinement" for event in result.audit_trail.events)
    gold = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/gold/g_orders.ingestion.yaml"))
    assert gold["transform"]["shape"]["columns"] == {"order_id": "order_id", "total_amount": "amount"}
    review = next(artifact.content for artifact in result.project.artifacts if artifact.path == "AI_REVIEW.html")
    assert "Project Guidance" in review
    assert "Transformation Guidance" in review
    assert "Provider Proposal Audit" not in review
    assert "metric" in review
    assert "Generated Artifacts" in review
    assert "Confirm stable merge keys" in review


def test_generate_from_intent_preserves_provider_full_transform_block(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "raw_payload", "type": "STRING"}]}),
        encoding="utf-8",
    )
    provider = SequenceProvider([FULL_PROJECT_SPEC_TRANSFORM_OUTPUT, VALID_PROJECT_PLAN_OUTPUT, VALID_PROJECT_PLAN_OUTPUT])

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create a gold ingestion from main.silver.s_orders into main.gold.g_orders. "
                "Parse raw_payload as JSON, flatten payload and keep final columns order_id and total_amount."
            ),
            schema_path=str(schema),
            provider=provider,
        )
    )

    assert result.transformation_plan is not None
    assert result.transformation_plan.contract_transform["shape"]["parse_json"][0]["target_column"] == "payload"
    assert result.provider_proposal_audit is not None
    assert result.provider_proposal_audit.review_required_count == 1
    gold = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/gold/g_orders.ingestion.yaml"))
    assert gold["transform"]["shape"]["parse_json"][0]["source_column"] == "raw_payload"
    assert gold["transform"]["shape"]["flatten"][0]["column"] == "payload"
    assert gold["transform"]["shape"]["columns"] == {
        "order_id": "payload.order_id",
        "total_amount": "payload.amount",
    }


def test_generate_from_intent_forces_provider_full_transform_review_and_rejects_unsupported_fields(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}]}),
        encoding="utf-8",
    )
    provider = SequenceProvider([UNSAFE_PROJECT_SPEC_TRANSFORM_OUTPUT, VALID_PROJECT_PLAN_OUTPUT, VALID_PROJECT_PLAN_OUTPUT])

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt="Create a gold ingestion from main.silver.s_orders into main.gold.g_orders with final columns order_id.",
            schema_path=str(schema),
            provider=provider,
        )
    )

    assert result.provider_proposal_audit is not None
    outcomes = {decision.field_path: decision.outcome for decision in result.provider_proposal_audit.decisions}
    assert outcomes["transform"] == "requires_review"
    assert outcomes["runtime_secret"] == "rejected"
    assert result.provider_proposal_audit.accepted_count == 0
    assert result.provider_proposal_audit.rejected_count == 1
    assert result.provider_proposal_audit.review_required_count == 1
    assert any(decision.path == "transform" for decision in result.transformation_plan.decisions_required)

    gold = yaml.safe_load(next(artifact.content for artifact in result.project.artifacts if artifact.path == "contracts/gold/g_orders.ingestion.yaml"))
    assert gold["transform"]["shape"]["columns"] == {"order_id": "order_id"}
    assert "runtime_secret" not in gold


def test_generate_from_intent_audits_rejected_and_review_required_provider_proposals(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    provider = SequenceProvider([MIXED_PROJECT_SPEC_TRANSFORM_OUTPUT, VALID_PROJECT_PLAN_OUTPUT, VALID_PROJECT_PLAN_OUTPUT])

    result = generate_from_intent(
        IntentGenerationRequest(
            prompt=(
                "Create a gold ingestion from s3a://landing/orders into main.gold.g_orders using scd1_hash_diff. "
                "Final columns: order_id, total_amount, customer_segment."
            ),
            schema_path=str(schema),
            provider=provider,
        )
    )

    assert result.provider_proposal_audit is not None
    assert result.provider_proposal_audit.accepted_count == 1
    assert result.provider_proposal_audit.rejected_count == 1
    assert result.provider_proposal_audit.review_required_count == 1
    assert result.provider_proposal_audit.action == "review_required"
    outcomes = {decision.field_path: decision.outcome for decision in result.provider_proposal_audit.decisions}
    assert outcomes["transform.shape.columns.total_amount"] == "accepted"
    assert outcomes["transform.shape.columns.bad-name"] == "rejected"
    assert outcomes["transform.shape.columns.customer_segment"] == "requires_review"
    assert result.transformation_plan.shape_columns == {"order_id": "order_id", "total_amount": "amount"}
    assert any("customer_segment" in decision.question for decision in result.transformation_plan.decisions_required)

    payload = result.to_dict()
    assert payload["provider_proposal_audit"]["accepted_count"] == 1
    review = next(artifact.content for artifact in result.project.artifacts if artifact.path == "AI_REVIEW.html")
    assert "shape_column.unsafe_target_identifier" not in review
    assert "customer_segment" in review
    assert "shape_column.source_not_in_schema" not in review
    assert "Recommended Next Actions" in review
