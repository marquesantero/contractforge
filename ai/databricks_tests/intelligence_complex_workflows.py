# Databricks notebook source
# MAGIC %md
# MAGIC # ContractForge AI - Complex Intelligence Workflow Validation
# MAGIC
# MAGIC This notebook exercises ContractForge AI as a user-facing assistant, not as isolated unit functions.
# MAGIC
# MAGIC It generates validation artifacts for human review:
# MAGIC
# MAGIC - Guided project synthesis for `databricks-dab` and `contractforge-yaml`.
# MAGIC - Context package extraction from nested JSON, JSONL and CSV samples.
# MAGIC - Shape and metadata suggestions.
# MAGIC - Local knowledge index build/query and task routing.
# MAGIC - Deterministic validation gate and critique scoring.
# MAGIC - Control-table intelligence over realistic operational evidence.
# MAGIC - Optional provider-backed enrichment using Databricks secrets.
# MAGIC
# MAGIC Artifacts are written to `/FileStore/contractforge-ai-tests/<run_id>/`.

# COMMAND ----------

# MAGIC %pip install --quiet --upgrade openai PyYAML

# COMMAND ----------

# MAGIC %pip install --quiet --upgrade --no-deps /Workspace/Shared/contractforge-wheels/contractforge_core-0.2.0-py3-none-any.whl /Workspace/Shared/contractforge-ai/libs/contractforge_ai-0.3.0-py3-none-any.whl

# COMMAND ----------

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from contractforge_ai.context.knowledge import build_knowledge_index, query_knowledge_index, save_knowledge_index
from contractforge_ai.enrichment import enrich_control_table_analysis, enrich_project_synthesis
from contractforge_ai.generators.metadata import suggest_metadata
from contractforge_ai.generators.shape import suggest_shape
from contractforge_ai.intelligence import TaskRouteRequest, critique_output, route_task
from contractforge_ai.observability import analyze_control_tables
from contractforge_ai.projects import write_project_plan
from contractforge_ai.projects.guided import GuidedProjectRequest, generate_guided_project
from contractforge_ai.providers import GenerationOptions, ProviderConfig, create_provider
from contractforge_ai.reports import render_guided_project_review, render_operational_analysis_review
from contractforge_ai.validation import validate_model_artifact

# Keep this notebook lintable outside Databricks without changing Databricks runtime behavior.
if "dbutils" not in globals():
    dbutils = None
if "display" not in globals():
    def display(value):
        print(value)

# COMMAND ----------

run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
dbfs_root = Path(f"/dbfs/FileStore/contractforge-ai-tests/{run_id}")
local_context = Path(f"/tmp/contractforge-ai-tests/{run_id}/context")
dbfs_root.mkdir(parents=True, exist_ok=True)
local_context.mkdir(parents=True, exist_ok=True)

print(f"Run ID: {run_id}")
print(f"Artifact root: {dbfs_root}")
print(f"Workspace download path: /files/contractforge-ai-tests/{run_id}/")

# COMMAND ----------

orders_sample = [
    {
        "order_id": "O-1001",
        "customer": {
            "customer_id": "C-001",
            "email": "ana@example.com",
            "segment": "enterprise",
            "addresses": [
                {"type": "billing", "city": "Sao Paulo", "country": "BR"},
                {"type": "shipping", "city": "Campinas", "country": "BR"},
            ],
        },
        "status": "paid",
        "order_ts": "2026-05-20T10:31:00Z",
        "updated_at": "2026-05-20T10:45:00Z",
        "currency": "BRL",
        "items": [
            {"sku": "SKU-1", "quantity": 2, "unit_price": 19.9, "discount": 0.0},
            {"sku": "SKU-2", "quantity": 1, "unit_price": 129.5, "discount": 10.0},
        ],
        "payments": [
            {"method": "credit_card", "amount": 159.3, "authorized": True},
        ],
        "metadata": {"source_system": "shop", "campaign": "winter"},
    },
    {
        "order_id": "O-1002",
        "customer": {
            "customer_id": "C-002",
            "email": "bruno@example.com",
            "segment": "retail",
            "addresses": [{"type": "shipping", "city": "Rio de Janeiro", "country": "BR"}],
        },
        "status": "pending",
        "order_ts": "2026-05-21T12:00:00Z",
        "updated_at": "2026-05-21T12:04:00Z",
        "currency": "BRL",
        "items": [{"sku": "SKU-3", "quantity": 4, "unit_price": 12.0, "discount": 0.0}],
        "payments": [],
        "metadata": {"source_system": "marketplace", "campaign": None},
    },
]

schema_profile = {
    "columns": [
        {"name": "order_id", "type": "string", "nullable": False},
        {"name": "customer", "type": "struct", "nullable": False},
        {"name": "status", "type": "string", "nullable": False},
        {"name": "order_ts", "type": "timestamp", "nullable": False},
        {"name": "updated_at", "type": "timestamp", "nullable": False},
        {"name": "currency", "type": "string", "nullable": False},
        {"name": "items", "type": "array", "nullable": False},
        {"name": "payments", "type": "array", "nullable": True},
        {"name": "metadata", "type": "struct", "nullable": True},
    ]
}

(local_context / "orders_nested_sample.json").write_text(json.dumps(orders_sample, indent=2), encoding="utf-8")
(local_context / "orders_stream_sample.jsonl").write_text(
    "\n".join(json.dumps(item) for item in orders_sample),
    encoding="utf-8",
)
(local_context / "schema_profile.yaml").write_text(yaml.safe_dump(schema_profile, sort_keys=False), encoding="utf-8")
(local_context / "orders_profile.csv").write_text(
    "column,type,nullable,notes\n"
    "order_id,string,false,business key\n"
    "customer.email,string,false,PII email\n"
    "updated_at,timestamp,false,watermark candidate\n",
    encoding="utf-8",
)
(local_context / "README.md").write_text(
    "# Retail orders context\n\n"
    "Silver ingestion from S3 landing data into Databricks using scd1_hash_diff.\n"
    "Expected keys: order_id. Watermark: updated_at. PII: customer.email.\n",
    encoding="utf-8",
)

print(f"Context files: {[item.name for item in local_context.iterdir()]}")

# COMMAND ----------

intent = (
    "Create a production-grade silver ingestion project for retail orders. "
    "Read nested JSON order files from s3a://landing/retail/orders into main.silver.orders. "
    "Use ContractForge with scd1_hash_diff, merge key order_id, hash diff over customer/status/currency/items/payments, "
    "watermark on updated_at, null-key protection, duplicate-key detection, quality gates, annotations, operations metadata, "
    "and Databricks DAB deployment artifacts."
)

naming = {
    "policy": "custom",
    "display_name": "Retail Orders Silver",
    "logical_name": "retail_orders_silver",
    "slug": "retail-orders-silver",
    "contract_basename": "retail_orders_silver",
    "bundle_name": "retail-orders-silver",
    "job_name": "contractforge-retail-orders-silver",
    "task_key": "retail_orders_silver",
    "artifact_prefix": "retail_orders_silver",
    "preserve_target_identifiers": True,
}

dab_result = generate_guided_project(
    GuidedProjectRequest(
        intent=intent,
        context_dir=str(local_context),
        runtime="databricks-classic",
        default_catalog="main",
        default_schema="silver",
        default_layer="silver",
        preferred_target="databricks-dab",
        allow_review_required=True,
        naming=naming,
    )
)

yaml_result = generate_guided_project(
    GuidedProjectRequest(
        intent=intent,
        context_dir=str(local_context),
        runtime="databricks-serverless",
        default_catalog="main",
        default_schema="silver",
        default_layer="silver",
        preferred_target="contractforge-yaml",
        allow_review_required=True,
        naming=naming,
    )
)

for name, result in {"guided_dab": dab_result, "guided_yaml": yaml_result}.items():
    target_dir = dbfs_root / name
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "result.json").write_text(json.dumps(result.to_dict(include_content=True), indent=2, ensure_ascii=False), encoding="utf-8")
    (target_dir / "result.md").write_text(result.to_markdown(), encoding="utf-8")
    if result.project:
        write_project_plan(result.project, target_dir / "artifacts", force=True)

print("Guided DAB status:", dab_result.status)
print("Guided YAML status:", yaml_result.status)

# COMMAND ----------

shape_result = suggest_shape(str(local_context / "orders_nested_sample.json"), source_column="raw_payload")
metadata_result = suggest_metadata(str(local_context / "schema_profile.yaml"))

(dbfs_root / "shape_suggestion.json").write_text(
    json.dumps(shape_result.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
)
(dbfs_root / "metadata_suggestion.json").write_text(
    json.dumps(metadata_result.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("Shape decisions:", shape_result.decisions_required)
print("Metadata suggestions:", len(metadata_result.suggestions))

# COMMAND ----------

knowledge_index = build_knowledge_index([local_context, dbfs_root / "guided_dab" / "artifacts"], root=local_context.parent)
knowledge_path = dbfs_root / "knowledge_index.json"
save_knowledge_index(knowledge_index, knowledge_path)
knowledge_results = query_knowledge_index(
    knowledge_index,
    "scd1_hash_diff order_id watermark updated_at pii email databricks dab",
    limit=8,
)
route_result = route_task(
    TaskRouteRequest(
        intent="Generate and validate a Databricks DAB project for S3 silver orders with hash diff and PII annotations.",
        knowledge_index=knowledge_index,
        context_limit=8,
        task_hint="project_synthesis",
        require_strict_schema=True,
    )
)

(dbfs_root / "knowledge_query.json").write_text(
    json.dumps([item.to_dict() for item in knowledge_results], indent=2, ensure_ascii=False),
    encoding="utf-8",
)
(dbfs_root / "task_route.json").write_text(json.dumps(route_result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

print("Knowledge chunks:", len(knowledge_index.chunks))
print("Knowledge results:", len(knowledge_results))
print("Route task:", route_result.task, "confidence:", route_result.confidence)

# COMMAND ----------

control_evidence = {
    "runs": [
        {
            "run_id": "r1",
            "target_table": "main.silver.orders",
            "status": "FAILED",
            "runtime_type": "serverless",
            "rows_read": 0,
            "rows_written": 0,
            "error_message": "Unauthorized access to cloud storage external location.",
            "started_at_utc": "2026-05-24T10:00:00Z",
            "finished_at_utc": "2026-05-24T10:02:00Z",
        },
        {
            "run_id": "r2",
            "target_table": "main.silver.orders",
            "status": "FAILED",
            "runtime_type": "serverless",
            "rows_read": 0,
            "rows_written": 0,
            "error_message": "Unauthorized access to cloud storage external location.",
            "started_at_utc": "2026-05-24T11:00:00Z",
            "finished_at_utc": "2026-05-24T11:02:00Z",
        },
        {
            "run_id": "r3",
            "target_table": "main.silver.orders",
            "status": "SUCCESS",
            "runtime_type": "classic",
            "rows_read": 100000,
            "rows_written": 99500,
            "started_at_utc": "2026-05-24T12:00:00Z",
            "finished_at_utc": "2026-05-24T12:24:00Z",
        },
    ],
    "quality": [
        {"run_id": "r3", "rule_name": "not_null_order_id", "status": "PASS", "failed_rows": 0},
        {"run_id": "r3", "rule_name": "accepted_status", "status": "WARN", "failed_rows": 500},
    ],
    "streams": [
        {"stream_run_id": "s1", "target_table": "main.silver.orders", "batches_processed": 4, "total_rows_written": 99500}
    ],
    "operations": [
        {
            "target_table": "main.silver.orders",
            "criticality": "high",
            "freshness_sla_minutes": 60,
            "last_success_ts_utc": "2026-05-24T12:24:00Z",
            "observed_at_utc": "2026-05-24T15:00:00Z",
        }
    ],
}

analysis = analyze_control_tables(control_evidence)
(dbfs_root / "control_table_analysis.json").write_text(
    json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("Control analysis status:", analysis.status)
print("Control analysis risk:", analysis.risk)
print("Findings:", [finding.code for finding in analysis.findings])

# COMMAND ----------

def provider_from_secret(provider_name: str):
    if provider_name == "openai":
        api_key = dbutils.secrets.get("contractforge-ai", "openai_api_key")
        return create_provider(
            ProviderConfig(
                provider="openai",
                model=dbutils.widgets.get("openai_model") or "gpt-4.1-mini",
                api_key=api_key,
                timeout=90,
                max_retries=1,
            )
        )
    if provider_name == "deepseek":
        api_key = dbutils.secrets.get("contractforge-ai", "deepseek_api_key")
        return create_provider(
            ProviderConfig(
                provider="deepseek",
                model=dbutils.widgets.get("deepseek_model") or "deepseek-chat",
                api_key=api_key,
                timeout=90,
                max_retries=1,
            )
        )
    raise ValueError(provider_name)


dbutils.widgets.text("openai_model", "gpt-4.1-mini")
dbutils.widgets.text("deepseek_model", "deepseek-chat")

provider_outputs = {}
for provider_name in ["openai", "deepseek"]:
    try:
        provider = provider_from_secret(provider_name)
        project_enrichment = enrich_project_synthesis(
            context_package=dab_result.context.to_dict() if dab_result.context else {},
            generated_project=dab_result.project.to_dict(include_content=False) if dab_result.project else {},
            user_intent=intent,
            provider=provider,
            options=GenerationOptions(temperature=0.1, max_output_tokens=1800),
        )
        observability_enrichment = enrich_control_table_analysis(
            analysis.to_dict(),
            control_evidence,
            provider=provider,
            options=GenerationOptions(temperature=0.1, max_output_tokens=1800),
        )
        provider_outputs[provider_name] = {
            "project_synthesis": project_enrichment.to_dict(),
            "observability": observability_enrichment.to_dict(),
        }
    except Exception as exc:
        provider_outputs[provider_name] = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

(dbfs_root / "provider_enrichments.json").write_text(
    json.dumps(provider_outputs, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

provider_outputs

# COMMAND ----------

validation_payload = {
    "kind": "project_plan",
    "summary": "Generated Databricks DAB project for retail orders.",
    "confidence": 0.91,
    "evidence": [
        "Context package contains nested JSON and schema profile.",
        "Generated project contains DAB artifacts and ContractForge contracts.",
        "Validation and critique were executed before marking review status.",
    ],
    "decisions_required": [
        "Confirm final hash-diff exclusions for audit and technical columns.",
        "Confirm whether customer.email should be masked downstream.",
    ],
    "recommendations": [
        "Keep generated DAB artifacts under review until keys and PII policies are approved.",
        "Run ContractForge validate against the target runtime before deployment.",
    ],
    "assumptions": [
        "order_id is stable as the business merge key.",
        "updated_at is monotonic enough for watermarking.",
    ],
    "review_required": True,
}

validation = validate_model_artifact(validation_payload, prompt_name="project.synthesis.enrichment.v1")
critique = critique_output(
    validation_payload,
    validation=validation,
    context_results=[item.to_dict() for item in knowledge_results],
)

(dbfs_root / "model_validation.json").write_text(json.dumps(validation.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
(dbfs_root / "critique.json").write_text(json.dumps(critique.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

print("Model validation:", validation.status, "ready:", validation.ready)
print("Critique:", critique.status, "ready:", critique.ready, "confidence:", critique.confidence)

# COMMAND ----------

project_enrichments = {}
for provider_name, output in provider_outputs.items():
    project_output = output.get("project_synthesis") if isinstance(output, dict) else None
    if isinstance(project_output, dict):
        project_enrichments[f"{provider_name} project synthesis"] = project_output

rich_project_report = render_guided_project_review(dab_result, enrichments=project_enrichments)
rich_ops_report = render_operational_analysis_review(
    analysis,
    enrichment=provider_outputs.get("openai", {}).get("observability")
    if isinstance(provider_outputs.get("openai"), dict)
    else None,
)

(dbfs_root / "AI_REVIEW.html").write_text(rich_project_report.html, encoding="utf-8")
(dbfs_root / "OPERATIONAL_REVIEW.html").write_text(rich_ops_report.html, encoding="utf-8")

dab_artifact_root = dbfs_root / "guided_dab" / "artifacts"
if dab_artifact_root.exists():
    (dab_artifact_root / "AI_REVIEW.html").write_text(rich_project_report.html, encoding="utf-8")

print("Rich review artifacts written:", str(dbfs_root / "AI_REVIEW.html"))

# COMMAND ----------

summary = {
    "run_id": run_id,
    "artifact_root": str(dbfs_root),
    "download_url_path": f"/files/contractforge-ai-tests/{run_id}/",
    "review_html": f"/files/contractforge-ai-tests/{run_id}/AI_REVIEW.html",
    "operational_review_html": f"/files/contractforge-ai-tests/{run_id}/OPERATIONAL_REVIEW.html",
    "guided_dab_status": dab_result.status,
    "guided_yaml_status": yaml_result.status,
    "guided_dab_artifacts": [artifact.path for artifact in dab_result.project.artifacts] if dab_result.project else [],
    "guided_yaml_artifacts": [artifact.path for artifact in yaml_result.project.artifacts] if yaml_result.project else [],
    "shape_decisions_required": shape_result.decisions_required,
    "metadata_suggestion_count": len(metadata_result.suggestions),
    "knowledge_chunk_count": len(knowledge_index.chunks),
    "knowledge_result_count": len(knowledge_results),
    "route_task": route_result.task,
    "route_confidence": route_result.confidence,
    "control_analysis_status": analysis.status,
    "control_analysis_risk": analysis.risk,
    "control_finding_codes": [finding.code for finding in analysis.findings],
    "model_validation_status": validation.status,
    "model_validation_ready": validation.ready,
    "critique_status": critique.status,
    "critique_ready": critique.ready,
    "provider_statuses": {
        provider: {
            key: value.get("status")
            for key, value in output.items()
            if isinstance(value, dict)
        }
        for provider, output in provider_outputs.items()
    },
}

(dbfs_root / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

report = [
    "# ContractForge AI Complex Intelligence Validation",
    "",
    f"- Run ID: `{run_id}`",
    f"- Artifact root: `{dbfs_root}`",
    f"- Download path: `/files/contractforge-ai-tests/{run_id}/`",
    "",
    "## Status",
    "",
    f"- Guided DAB: `{dab_result.status}`",
    f"- Guided YAML: `{yaml_result.status}`",
    f"- Control-table analysis: `{analysis.status}` / risk `{analysis.risk}`",
    f"- Deterministic model validation: `{validation.status}` / ready `{validation.ready}`",
    f"- Critique: `{critique.status}` / ready `{critique.ready}`",
    "",
    "## Generated Artifacts",
    "",
    *[f"- DAB: `{artifact}`" for artifact in summary["guided_dab_artifacts"]],
    *[f"- YAML: `{artifact}`" for artifact in summary["guided_yaml_artifacts"]],
    "",
    "## Provider Outputs",
    "",
    json.dumps(summary["provider_statuses"], indent=2, ensure_ascii=False),
]
(dbfs_root / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

display(summary)

# COMMAND ----------

dbutils.notebook.exit(json.dumps(summary, ensure_ascii=False))
