# Databricks notebook source
# MAGIC %md
# MAGIC # ContractForge AI - Full Project Artifact Validation
# MAGIC
# MAGIC This notebook validates ContractForge AI from the user-facing perspective:
# MAGIC
# MAGIC - Generate complete projects for multiple scenarios and output targets.
# MAGIC - Write all generated artifacts to DBFS for manual review.
# MAGIC - Run deterministic validation and critique for each generated project.
# MAGIC - Enrich project synthesis and operational analysis with configured model providers.
# MAGIC - Produce rich HTML and Markdown review reports, including an index page.
# MAGIC
# MAGIC Artifacts are written to `/Volumes/workspace/default/contractforge_ai/validation-runs/<run_id>/`.

# COMMAND ----------

# MAGIC %pip install --quiet --upgrade "typing_extensions>=4.15" "pydantic>=2" openai PyYAML

# COMMAND ----------

# MAGIC %pip install --upgrade --no-deps /Volumes/workspace/default/contractforge_ai/contractforge-wheels/contractforge_core-0.2.0-py3-none-any.whl /Volumes/workspace/default/contractforge_ai/libs/contractforge_ai-0.3.0-py3-none-any.whl

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import html
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from contractforge_ai.context.redaction import redact_secrets
from contractforge_ai.enrichment import enrich_control_table_analysis, enrich_project_synthesis
from contractforge_ai.evaluation import render_prompt
from contractforge_ai.generators.metadata import suggest_metadata
from contractforge_ai.generators.shape import suggest_shape
from contractforge_ai.intelligence import TaskRouteRequest, critique_output, route_task
from contractforge_ai.observability import analyze_control_tables
from contractforge_ai.projects import write_project_plan
from contractforge_ai.projects.guided import GuidedProjectRequest, generate_guided_project
from contractforge_ai.providers import GenerationOptions, ProviderConfig, create_provider
from contractforge_ai.reports import render_guided_project_review, render_operational_analysis_review
from contractforge_ai.validation import validate_model_artifact

if "dbutils" not in globals():
    dbutils = None
if "display" not in globals():
    def display(value):
        print(value)

# COMMAND ----------

dbutils.widgets.text("openai_model", "")
dbutils.widgets.text("deepseek_model", "")
dbutils.widgets.text("provider_timeout_seconds", "120")

run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
artifact_root = Path(f"/Volumes/workspace/default/contractforge_ai/validation-runs/{run_id}")
dbfs_root = artifact_root
context_root = artifact_root / "_contexts"
dbfs_root.mkdir(parents=True, exist_ok=True)
context_root.mkdir(parents=True, exist_ok=True)

print(f"Run ID: {run_id}")
print(f"Artifact root: {dbfs_root}")
print(f"Volume path: /Volumes/workspace/default/contractforge_ai/validation-runs/{run_id}/")

# COMMAND ----------

def _secret_value(scope, *keys):
    last_error = None
    for key in keys:
        try:
            value = dbutils.secrets.get(scope, key)
            if value:
                return value
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError(f"No secret value found in scope {scope!r} for keys: {keys!r}")


def _secret_or_default(scope, key, default):
    try:
        value = dbutils.secrets.get(scope, key)
        return value or default
    except Exception:
        return default


def provider_from_secret(provider_name):
    scope = "contractforge-ai"
    timeout = int(dbutils.widgets.get("provider_timeout_seconds") or "120")
    if provider_name == "openai":
        return create_provider(
            ProviderConfig(
                provider="openai",
                model=dbutils.widgets.get("openai_model")
                or _secret_or_default(scope, "model", "gpt-4.1-mini"),
                api_key=_secret_value(scope, "openai_api_key", "api_key"),
                timeout=timeout,
                max_retries=1,
            )
        )
    if provider_name == "deepseek":
        return create_provider(
            ProviderConfig(
                provider="deepseek",
                model=dbutils.widgets.get("deepseek_model")
                or _secret_or_default(scope, "deepseek_model", "deepseek-chat"),
                api_key=_secret_value(scope, "deepseek_api_key"),
                timeout=timeout,
                max_retries=1,
            )
        )
    raise ValueError(provider_name)


ai_first_provider = None
ai_first_provider_status = {"provider": "openai", "status": "NOT_CONFIGURED"}
try:
    ai_first_provider = provider_from_secret("openai")
    ai_first_provider_status = {"provider": "openai", "status": "CONFIGURED"}
except Exception as exc:
    ai_first_provider_status = {
        "provider": "openai",
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }

print("AI-first provider:", ai_first_provider_status)

# COMMAND ----------

def write_context(name, files):
    path = context_root / name
    path.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        target = path / filename
        if isinstance(content, (dict, list)):
            target.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            target.write_text(str(content), encoding="utf-8")
    return path


orders_context = write_context(
    "orders_silver",
    {
        "orders_nested_sample.json": [
            {
                "order_id": "O-1001",
                "updated_at": "2026-05-20T10:45:00Z",
                "status": "paid",
                "currency": "BRL",
                "customer": {
                    "customer_id": "C-001",
                    "email": "ana@example.com",
                    "segment": "enterprise",
                    "addresses": [
                        {"type": "billing", "city": "Sao Paulo", "country": "BR"},
                        {"type": "shipping", "city": "Campinas", "country": "BR"},
                    ],
                },
                "items": [
                    {"sku": "SKU-1", "quantity": 2, "unit_price": 19.9},
                    {"sku": "SKU-2", "quantity": 1, "unit_price": 129.5},
                ],
                "payments": [{"method": "credit_card", "amount": 159.3, "authorized": True}],
            },
            {
                "order_id": "O-1002",
                "updated_at": "2026-05-21T12:04:00Z",
                "status": "pending",
                "currency": "BRL",
                "customer": {"customer_id": "C-002", "email": "bruno@example.com", "segment": "retail"},
                "items": [{"sku": "SKU-3", "quantity": 4, "unit_price": 12.0}],
                "payments": [],
            },
        ],
        "schema_profile.yaml": yaml.safe_dump(
            {
                "columns": [
                    {"name": "order_id", "type": "string", "nullable": False},
                    {"name": "updated_at", "type": "timestamp", "nullable": False},
                    {"name": "status", "type": "string", "nullable": False},
                    {"name": "currency", "type": "string", "nullable": False},
                    {"name": "customer", "type": "struct", "nullable": False},
                    {"name": "items", "type": "array", "nullable": False},
                    {"name": "payments", "type": "array", "nullable": True},
                ]
            },
            sort_keys=False,
        ),
        "requirements.md": (
            "# Retail orders silver\n\n"
            "Use order_id as merge key, updated_at as watermark, classify customer.email as PII, "
            "generate annotations and operations metadata, and use scd1_hash_diff."
        ),
    },
)

events_context = write_context(
    "eonet_bronze",
    {
        "eonet_response.json": {
            "title": "EONET Events",
            "events": [
                {
                    "id": "EONET_1",
                    "title": "Wildfire event",
                    "categories": [{"id": "wildfires", "title": "Wildfires"}],
                    "geometry": [{"date": "2026-05-20T00:00:00Z", "type": "Point", "coordinates": [-50.1, -12.4]}],
                }
            ],
        },
        "schema_profile.yaml": yaml.safe_dump(
            {
                "columns": [
                    {"name": "raw_payload", "type": "string", "nullable": False},
                    {"name": "ingested_at", "type": "timestamp", "nullable": False},
                ]
            },
            sort_keys=False,
        ),
    },
)

jdbc_context = write_context(
    "customer_jdbc",
    {
        "customers_profile.csv": (
            "column,type,nullable,notes\n"
            "customer_id,string,false,business key\n"
            "email,string,true,PII email\n"
            "updated_at,timestamp,false,incremental watermark\n"
            "credit_limit,double,true,commercial attribute\n"
        ),
        "schema_profile.yaml": yaml.safe_dump(
            {
                "columns": [
                    {"name": "customer_id", "type": "string", "nullable": False},
                    {"name": "email", "type": "string", "nullable": True},
                    {"name": "updated_at", "type": "timestamp", "nullable": False},
                    {"name": "credit_limit", "type": "double", "nullable": True},
                ]
            },
            sort_keys=False,
        ),
    },
)

print("Context directories:", [p.name for p in context_root.iterdir()])

# COMMAND ----------

scenarios = [
    {
        "name": "retail_orders_silver_dab",
        "preferred_target": "databricks-dab",
        "context_dir": str(orders_context),
        "runtime": "databricks-classic",
        "ai_first": True,
        "intent": (
            "Create a production-grade silver ingestion project for retail orders. "
            "Read nested JSON order files from s3a://landing/retail/orders into main.silver.orders. "
            "Use ContractForge with scd1_hash_diff, merge key order_id, hash diff over customer/status/currency/items/payments, "
            "watermark on updated_at, null-key protection, duplicate-key detection, quality gates, annotations, operations metadata, "
            "required columns: order_id, updated_at, status. Unique key: order_id. "
            "currency accepted values: BRL, USD, EUR. amount must be >= 0. quality severity: fail. "
            "business owner: retail-ops technical owner: data-platform steward: data-governance support group: data-platform "
            "criticality: high frequency: daily SLA: 120 minutes alert on failure alert on quality failure "
            "runbook https://example.com/runbooks/retail-orders. "
            "Generate Databricks DAB deployment artifacts using serverless compute."
        ),
    },
    {
        "name": "retail_orders_silver_yaml",
        "preferred_target": "contractforge-yaml",
        "context_dir": str(orders_context),
        "runtime": "databricks-serverless",
        "ai_first": True,
        "intent": (
            "Create a reusable ContractForge YAML project for silver retail orders from s3a://landing/retail/orders "
            "to main.silver.orders using scd1_hash_diff, order_id, updated_at, annotations and operations metadata. "
            "required columns: order_id, updated_at, status. Unique key: order_id. "
            "status accepted values: paid, pending, cancelled. total_amount must be >= 0. quality severity: quarantine. "
            "business owner: retail-ops technical owner: data-platform criticality: medium frequency: hourly SLA: 60 minutes."
        ),
    },
    {
        "name": "eonet_bronze_python",
        "preferred_target": "contractforge-python",
        "context_dir": str(events_context),
        "runtime": "databricks-serverless",
        "ai_first": True,
        "intent": (
            "Create a bronze Python ingestion project for NASA EONET REST API data. "
            "Use rest_api raw response mode from https://eonet.gsfc.nasa.gov/api/v3/events into main.bronze.b_eonet_events "
            "with scd0_overwrite, transform.shape.parse_json, array explosion for events and geometry, annotations and operations. "
            "required columns: raw_payload, ingestion_ts. Unique key: event_id. "
            "business owner: science-analytics technical owner: data-platform criticality: low frequency: daily SLA: 1440 minutes."
        ),
    },
    {
        "name": "customer_jdbc_classic",
        "preferred_target": "classic-pyspark",
        "context_dir": str(jdbc_context),
        "runtime": "databricks-classic",
        "ai_first": False,
        "intent": (
            "Create a classic PySpark migration scaffold for customer dimension ingestion from jdbc postgres table public.customers "
            "into main.silver.s_customers using scd1_upsert, merge key customer_id, watermark updated_at, JDBC partitioning, "
            "quality rules and PII annotations."
        ),
    },
    {
        "name": "customer_jdbc_dbt",
        "preferred_target": "dbt",
        "context_dir": str(jdbc_context),
        "runtime": "databricks-classic",
        "ai_first": False,
        "intent": (
            "Create a dbt starter around a ContractForge-managed customer dimension from jdbc postgres table public.customers "
            "into main.gold.g_customer_metrics. Use gold layer, scd0_overwrite, quality checks and operations metadata."
        ),
    },
]

naming = {
    "policy": "custom",
    "preserve_target_identifiers": True,
}

results = {}
for scenario in scenarios:
    result = generate_guided_project(
        GuidedProjectRequest(
            intent=scenario["intent"],
            context_dir=scenario["context_dir"],
            runtime=scenario["runtime"],
            default_catalog="main",
            default_schema="silver",
            default_layer="silver",
            preferred_target=scenario["preferred_target"],
            allow_review_required=True,
            naming={**naming, "logical_name": scenario["name"], "contract_basename": scenario["name"]},
            provider=ai_first_provider if scenario.get("ai_first") else None,
        )
    )
    results[scenario["name"]] = result

    scenario_root = dbfs_root / "projects" / scenario["name"]
    scenario_root.mkdir(parents=True, exist_ok=True)
    (scenario_root / "request.json").write_text(json.dumps(scenario, indent=2, ensure_ascii=False), encoding="utf-8")
    (scenario_root / "result.json").write_text(json.dumps(result.to_dict(include_content=True), indent=2, ensure_ascii=False), encoding="utf-8")
    if result.project:
        write_project_plan(result.project, scenario_root / "artifacts", force=True)
        report = render_guided_project_review(result)
        (scenario_root / "AI_REVIEW.html").write_text(report.html, encoding="utf-8")

ai_first_summary = {
    "provider": ai_first_provider_status,
    "scenarios": {
        name: {
            "status": result.status,
            "spec_enrichment_status": result.spec_enrichment.status if result.spec_enrichment else "NOT_REQUESTED",
            "spec_enrichment_prompt": result.spec_enrichment.prompt if result.spec_enrichment else None,
            "selected_target": result.selected_target,
            "validation_status": result.validation.status if result.validation else None,
            "review_required": result.spec.validate().status if result.spec else None,
        }
        for name, result in results.items()
    },
}
(dbfs_root / "ai_first_guided_generation.json").write_text(
    json.dumps(ai_first_summary, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

ai_first_enrichment_ok = any(
    item["spec_enrichment_status"] == "ENRICHED"
    for item in ai_first_summary["scenarios"].values()
)
ai_first_validation_notes = []
if not ai_first_enrichment_ok:
    ai_first_validation_notes.append(
        "AI-first guided generation did not produce any ENRICHED spec_enrichment result. "
        "The notebook will continue so the generated artifacts and provider diagnostics remain available."
    )

print({name: result.status for name, result in results.items()})
print("AI-first spec enrichment:", ai_first_summary)
print("AI-first validation notes:", ai_first_validation_notes)

# COMMAND ----------

shape_results = {
    "orders": suggest_shape(str(orders_context / "orders_nested_sample.json"), source_column="raw_payload").to_dict(),
    "eonet": suggest_shape(str(events_context / "eonet_response.json"), source_column="raw_payload").to_dict(),
}
metadata_results = {
    "orders": suggest_metadata(str(orders_context / "schema_profile.yaml")).to_dict(),
    "customers": suggest_metadata(str(jdbc_context / "schema_profile.yaml")).to_dict(),
}

(dbfs_root / "shape_suggestions.json").write_text(json.dumps(shape_results, indent=2, ensure_ascii=False), encoding="utf-8")
(dbfs_root / "metadata_suggestions.json").write_text(json.dumps(metadata_results, indent=2, ensure_ascii=False), encoding="utf-8")

route_payload = route_task(
    TaskRouteRequest(
        intent="Generate multiple production-ready ContractForge projects and analyze failed control table evidence with HTML reports.",
        context_limit=10,
        task_hint="project_synthesis",
        require_strict_schema=True,
    )
)
(dbfs_root / "task_route.json").write_text(json.dumps(route_payload.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

print("Route:", route_payload.task, route_payload.confidence)

# COMMAND ----------

control_evidence = {
    "scope": {
        "catalog": "main",
        "ctrl_schema": "ops",
        "domain": "retail",
        "window": "last_24h",
    },
    "runs": [
        {
            "run_id": "orders-001",
            "target_table": "main.silver.orders",
            "source_connector": "s3",
            "status": "FAILED",
            "runtime_type": "serverless",
            "duration_seconds": 121,
            "rows_read": 0,
            "rows_written": 0,
            "error_message": "Unauthorized access to S3 External Location.",
        },
        {
            "run_id": "orders-002",
            "target_table": "main.silver.orders",
            "source_connector": "s3",
            "status": "FAILED",
            "runtime_type": "serverless",
            "duration_seconds": 118,
            "rows_read": 0,
            "rows_written": 0,
            "error_message": "Unauthorized access to S3 External Location.",
        },
        {
            "run_id": "orders-003",
            "target_table": "main.silver.orders",
            "source_connector": "s3",
            "status": "SUCCESS",
            "runtime_type": "classic",
            "duration_seconds": 1510,
            "rows_read": 100000,
            "rows_written": 99500,
        },
        {
            "run_id": "eonet-001",
            "target_table": "main.bronze.b_eonet_events",
            "source_connector": "rest_api",
            "status": "SUCCESS",
            "runtime_type": "serverless",
            "duration_seconds": 47,
            "rows_read": 1,
            "rows_written": 1,
        },
        {
            "run_id": "customers-001",
            "target_table": "main.silver.s_customers",
            "source_connector": "jdbc",
            "status": "FAILED",
            "runtime_type": "classic",
            "duration_seconds": 30,
            "rows_read": 0,
            "rows_written": 0,
            "error_message": "No suitable driver for jdbc:postgresql.",
        },
    ],
    "errors": [
        {"run_id": "orders-001", "error_message": "Unauthorized access to S3 External Location."},
        {"run_id": "orders-002", "error_message": "Unauthorized access to S3 External Location."},
        {"run_id": "customers-001", "error_message": "No suitable driver for jdbc:postgresql."},
    ],
    "quality": [
        {"run_id": "orders-003", "rule_name": "not_null_order_id", "status": "PASS", "failed_rows": 0},
        {"run_id": "orders-003", "rule_name": "accepted_status", "status": "WARN", "failed_rows": 500},
        {"run_id": "customers-001", "rule_name": "not_null_customer_id", "status": "SKIPPED", "failed_rows": 0},
    ],
    "streams": [
        {
            "stream_run_id": "orders-stream-001",
            "target_table": "main.silver.orders",
            "batches_processed": 4,
            "total_rows_read": 100000,
            "total_rows_written": 99500,
        }
    ],
    "schema_changes": [
        {"run_id": "orders-003", "target_table": "main.silver.orders", "change_type": "ADD_COLUMN", "column_name": "metadata"}
    ],
    "operations": [
        {
            "target_table": "main.silver.orders",
            "criticality": "high",
            "freshness_sla_minutes": 60,
            "last_success_ts_utc": "2026-05-24T12:24:00Z",
            "observed_at_utc": "2026-05-24T15:00:00Z",
        },
        {
            "target_table": "main.silver.s_customers",
            "criticality": "medium",
            "freshness_sla_minutes": 1440,
            "last_success_ts_utc": None,
            "observed_at_utc": "2026-05-24T15:00:00Z",
        },
    ],
}

analysis = analyze_control_tables(control_evidence)
(dbfs_root / "control_table_evidence.json").write_text(json.dumps(control_evidence, indent=2, ensure_ascii=False), encoding="utf-8")
(dbfs_root / "control_table_analysis.json").write_text(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

ops_report = render_operational_analysis_review(analysis)
(dbfs_root / "OPERATIONAL_REVIEW.html").write_text(ops_report.html, encoding="utf-8")

print("Operational analysis:", analysis.status, analysis.risk, [finding.code for finding in analysis.findings])

# COMMAND ----------

provider_outputs = {}
provider_requests = {}
enrichment_options = GenerationOptions(temperature=0.1, max_output_tokens=2200)

for provider_name in ["openai", "deepseek"]:
    try:
        provider = provider_from_secret(provider_name)
        provider_outputs[provider_name] = {}
        provider_requests[provider_name] = {}

        for scenario_name in ["retail_orders_silver_dab", "eonet_bronze_python", "customer_jdbc_classic"]:
            result = results[scenario_name]
            variables = {
                "context_package": result.context.to_dict() if result.context else {},
                "generated_project": result.project.to_dict(include_content=False) if result.project else {},
                "user_intent": next(item["intent"] for item in scenarios if item["name"] == scenario_name),
            }
            system_prompt, user_prompt = render_prompt("project.synthesis.enrichment.v1", redact_secrets(variables))
            provider_requests[provider_name][f"{scenario_name}.project_synthesis"] = {
                "prompt": "project.synthesis.enrichment.v1",
                "system": system_prompt,
                "user": user_prompt,
            }
            enriched = enrich_project_synthesis(
                context_package=variables["context_package"],
                generated_project=variables["generated_project"],
                user_intent=variables["user_intent"],
                provider=provider,
                options=enrichment_options,
            )
            provider_outputs[provider_name][f"{scenario_name}.project_synthesis"] = enriched.to_dict()

        ops_variables = {
            "deterministic_analysis": analysis.to_dict(),
            "control_table_evidence": redact_secrets(control_evidence),
        }
        system_prompt, user_prompt = render_prompt("observability.enrichment.v1", ops_variables)
        provider_requests[provider_name]["observability"] = {
            "prompt": "observability.enrichment.v1",
            "system": system_prompt,
            "user": user_prompt,
        }
        ops_enriched = enrich_control_table_analysis(
            analysis.to_dict(),
            control_evidence,
            provider=provider,
            options=enrichment_options,
        )
        provider_outputs[provider_name]["observability"] = ops_enriched.to_dict()
    except Exception as exc:
        provider_outputs[provider_name] = {
            "status": "FAILED",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

(dbfs_root / "provider_requests.json").write_text(json.dumps(provider_requests, indent=2, ensure_ascii=False), encoding="utf-8")
(dbfs_root / "provider_outputs.json").write_text(json.dumps(provider_outputs, indent=2, ensure_ascii=False), encoding="utf-8")

provider_outputs

# COMMAND ----------

for scenario in scenarios:
    scenario_name = scenario["name"]
    result = results[scenario_name]
    if not result.project:
        continue
    enrichments = {}
    for provider_name, outputs in provider_outputs.items():
        if not isinstance(outputs, dict):
            continue
        key = f"{scenario_name}.project_synthesis"
        if isinstance(outputs.get(key), dict):
            enrichments[f"{provider_name} project synthesis"] = outputs[key]
    report = render_guided_project_review(result, enrichments=enrichments)
    scenario_root = dbfs_root / "projects" / scenario_name
    (scenario_root / "AI_REVIEW.html").write_text(report.html, encoding="utf-8")
    artifacts_root = scenario_root / "artifacts"
    if artifacts_root.exists():
        (artifacts_root / "AI_REVIEW.html").write_text(report.html, encoding="utf-8")

ops_enrichment = None
if isinstance(provider_outputs.get("openai"), dict):
    ops_enrichment = provider_outputs["openai"].get("observability")
ops_report = render_operational_analysis_review(analysis, enrichment=ops_enrichment)
(dbfs_root / "OPERATIONAL_REVIEW.html").write_text(ops_report.html, encoding="utf-8")

validation_payload = {
    "kind": "project_plan",
    "summary": "Full ContractForge AI artifact validation across DAB, YAML, Python, dbt and classic PySpark targets.",
    "confidence": 0.92,
    "evidence": [
        "Generated projects for multiple targets with context packages.",
        "Each generated project includes a consolidated AI_REVIEW.html.",
        "AI-first guided generation was requested for selected scenarios before artifact generation.",
        "Provider enrichment was requested for multiple project scenarios and operational analysis.",
        "Control-table analysis contains failures, warnings, stream metrics, schema changes and operations metadata.",
    ],
    "decisions_required": [
        "Confirm merge keys and hash diff columns before deploying generated projects.",
        "Confirm runtime access patterns for serverless and classic clusters.",
        "Confirm PII annotations and masking expectations with data owners.",
    ],
    "recommendations": [
        "Review generated HTML reports before accepting artifacts as implementation input.",
        "Use deterministic validation and critique output as the release gate for generated projects.",
    ],
    "assumptions": [
        "Artifacts are review scaffolds until human decisions are closed.",
        "Provider guidance is advisory and does not override deterministic validation.",
    ],
    "review_required": True,
}
model_validation = validate_model_artifact(validation_payload, prompt_name="project.synthesis.enrichment.v1")
critique = critique_output(
    validation_payload,
    validation=model_validation,
    context_results=[result.to_dict(include_content=False) for result in results.values()],
)

(dbfs_root / "model_validation.json").write_text(json.dumps(model_validation.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
(dbfs_root / "critique.json").write_text(json.dumps(critique.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

print("Model validation:", model_validation.status, model_validation.ready)
print("Critique:", critique.status, critique.ready, critique.confidence)

# COMMAND ----------

def html_link(path, text):
    return f'<a href="{html.escape(path)}">{html.escape(text)}</a>'


download_base = f"/Volumes/workspace/default/contractforge_ai/validation-runs/{run_id}"
project_rows = []
for scenario in scenarios:
    name = scenario["name"]
    result = results[name]
    project_rows.append(
        "<tr>"
        f"<td>{html.escape(name)}</td>"
        f"<td>{html.escape(scenario['preferred_target'])}</td>"
        f"<td>{html.escape(result.status)}</td>"
        f"<td>{len(result.project.artifacts) if result.project else 0}</td>"
        f"<td>{html_link(f'{download_base}/projects/{name}/AI_REVIEW.html', 'HTML review')}</td>"
        f"<td>{html_link(f'{download_base}/projects/{name}/artifacts/', 'Artifacts')}</td>"
        "</tr>"
    )

provider_rows = []
for provider_name, outputs in provider_outputs.items():
    if isinstance(outputs, dict):
        for key, output in outputs.items():
            if isinstance(output, dict):
                provider_rows.append(
                    "<tr>"
                    f"<td>{html.escape(provider_name)}</td>"
                    f"<td>{html.escape(key)}</td>"
                    f"<td>{html.escape(str(output.get('status', 'UNKNOWN')))}</td>"
                    f"<td>{html.escape(str(output.get('prompt', '')))}</td>"
                    "</tr>"
                )

ai_first_notes_html = ""
if ai_first_validation_notes:
    ai_first_notes_html = (
        "<section class=\"card\">"
        "<div class=\"label\">AI-first provider diagnostics</div>"
        "<ul>"
        + "".join(f"<li>{html.escape(note)}</li>" for note in ai_first_validation_notes)
        + "</ul>"
        "</section>"
    )

index_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ContractForge AI Full Validation - {html.escape(run_id)}</title>
  <style>
    body {{ font-family: IBM Plex Sans, Segoe UI, sans-serif; margin: 0; background: #f7f2ea; color: #173044; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 42px 24px 64px; }}
    header {{ background: linear-gradient(135deg, #173044, #1f4e69); color: white; padding: 34px; border-radius: 26px; box-shadow: 0 24px 60px rgba(23,48,68,.18); }}
    h1 {{ margin: 0 0 8px; font-size: 38px; letter-spacing: -0.04em; }}
    h2 {{ margin-top: 34px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 22px 0; }}
    .card {{ background: #fffdf8; border: 1px solid rgba(31,78,105,.18); border-radius: 18px; padding: 18px; box-shadow: 0 14px 36px rgba(23,48,68,.08); }}
    .label {{ color: #bf7b2c; font-weight: 800; text-transform: uppercase; font-size: 12px; letter-spacing: .09em; }}
    .value {{ font-size: 24px; font-weight: 850; margin-top: 6px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fffdf8; border-radius: 18px; overflow: hidden; box-shadow: 0 14px 36px rgba(23,48,68,.08); }}
    th, td {{ text-align: left; padding: 12px 14px; border-bottom: 1px solid rgba(31,78,105,.12); vertical-align: top; }}
    th {{ background: rgba(31,78,105,.10); }}
    a {{ color: #1f4e69; font-weight: 800; }}
    code {{ background: rgba(31,78,105,.10); padding: 2px 6px; border-radius: 7px; }}
    .card ul {{ margin-bottom: 0; }}
  </style>
</head>
<body>
<main>
  <header>
    <div class="label">ContractForge AI validation</div>
    <h1>Full project artifact validation</h1>
    <p>Generated complete projects, provider-enriched reviews, operational analysis and HTML artifacts for manual inspection.</p>
    <p><code>{html.escape(str(dbfs_root))}</code></p>
  </header>
  <section class="cards">
    <div class="card"><div class="label">Projects</div><div class="value">{len(scenarios)}</div></div>
    <div class="card"><div class="label">Providers</div><div class="value">{len(provider_outputs)}</div></div>
    <div class="card"><div class="label">Ops status</div><div class="value">{html.escape(analysis.status)}</div></div>
    <div class="card"><div class="label">Risk</div><div class="value">{html.escape(analysis.risk)}</div></div>
  </section>
  {ai_first_notes_html}
  <h2>Primary reports</h2>
  <ul>
    <li>{html_link(f'{download_base}/OPERATIONAL_REVIEW.html', 'Operational analysis HTML')}</li>
    <li>{html_link(f'{download_base}/provider_requests.json', 'Provider request payloads and prompts')}</li>
    <li>{html_link(f'{download_base}/provider_outputs.json', 'Provider structured outputs')}</li>
    <li>{html_link(f'{download_base}/ai_first_guided_generation.json', 'AI-first guided generation summary')}</li>
    <li>{html_link(f'{download_base}/summary.json', 'Machine-readable summary')}</li>
  </ul>
  <h2>Generated projects</h2>
  <table><thead><tr><th>Scenario</th><th>Target</th><th>Status</th><th>Artifacts</th><th>Review</th><th>Files</th></tr></thead><tbody>{''.join(project_rows)}</tbody></table>
  <h2>Provider calls</h2>
  <table><thead><tr><th>Provider</th><th>Request</th><th>Status</th><th>Prompt</th></tr></thead><tbody>{''.join(provider_rows)}</tbody></table>
</main>
</body>
</html>
"""
(dbfs_root / "INDEX.html").write_text(index_html, encoding="utf-8")

# COMMAND ----------

summary = {
    "run_id": run_id,
    "artifact_root": str(dbfs_root),
    "download_url_path": f"{download_base}/",
    "index_html": f"{download_base}/INDEX.html",
    "operational_review_html": f"{download_base}/OPERATIONAL_REVIEW.html",
    "projects": {
        name: {
            "status": result.status,
            "selected_target": result.selected_target,
            "artifact_count": len(result.project.artifacts) if result.project else 0,
            "review_html": f"{download_base}/projects/{name}/AI_REVIEW.html",
            "artifact_dir": f"{download_base}/projects/{name}/artifacts/",
            "validation_status": result.validation.status if result.validation else None,
            "critique_status": result.critique.status if result.critique else None,
            "ai_first": next(item.get("ai_first", False) for item in scenarios if item["name"] == name),
            "spec_enrichment_status": result.spec_enrichment.status if result.spec_enrichment else "NOT_REQUESTED",
        }
        for name, result in results.items()
    },
    "ai_first_guided_generation": ai_first_summary,
    "ai_first_enrichment_ok": ai_first_enrichment_ok,
    "ai_first_validation_notes": ai_first_validation_notes,
    "shape_scenarios": list(shape_results),
    "metadata_scenarios": list(metadata_results),
    "operational_analysis": {
        "status": analysis.status,
        "risk": analysis.risk,
        "finding_codes": [finding.code for finding in analysis.findings],
    },
    "model_validation": {
        "status": model_validation.status,
        "ready": model_validation.ready,
    },
    "critique": {
        "status": critique.status,
        "ready": critique.ready,
        "confidence": critique.confidence,
    },
    "provider_statuses": {
        provider_name: {
            key: value.get("status") if isinstance(value, dict) else "UNKNOWN"
            for key, value in outputs.items()
        }
        if isinstance(outputs, dict)
        else {"status": "FAILED"}
        for provider_name, outputs in provider_outputs.items()
    },
}

(dbfs_root / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

display(summary)
dbutils.notebook.exit(json.dumps(summary, ensure_ascii=False))
