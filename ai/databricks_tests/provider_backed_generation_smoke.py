# Databricks notebook source
# ruff: noqa: E402,F821
# MAGIC %md
# MAGIC # ContractForge AI - Provider-Backed Generation Smoke
# MAGIC
# MAGIC This notebook validates the user-facing AI generation path in a Databricks workspace:
# MAGIC
# MAGIC - inspect schema evidence from an existing or synthetic Spark table;
# MAGIC - run intent-first ContractForge project generation;
# MAGIC - optionally call a configured model provider before and after artifact generation;
# MAGIC - write generated artifacts, `AI_REVIEW.html`, provider status and validation summary to DBFS.
# MAGIC
# MAGIC It is intentionally smaller than the full validation notebook. Use it as a fast smoke test after installing a new `contractforge-ai` wheel.

# COMMAND ----------

# MAGIC %pip install --quiet --upgrade PyYAML

# COMMAND ----------

# MAGIC %md
# MAGIC Optional wheel installation can be enabled by setting `install_wheels=true`.
# MAGIC
# MAGIC Default paths match the workspace convention used by ContractForge validation jobs.

# COMMAND ----------

dbutils.widgets.text("install_wheels", "false")
dbutils.widgets.text("contractforge_wheel", "/Workspace/Shared/contractforge-wheels/contractforge_core-0.2.0-py3-none-any.whl")
dbutils.widgets.text("contractforge_ai_wheel", "/Workspace/Shared/contractforge-ai/libs/contractforge_ai-0.3.0-py3-none-any.whl")
dbutils.widgets.text("provider", "openai")
dbutils.widgets.text("provider_secret_scope", "contractforge-ai")
dbutils.widgets.text("openai_secret_key", "openai_api_key")
dbutils.widgets.text("deepseek_secret_key", "deepseek_api_key")
dbutils.widgets.text("openai_model", "gpt-4.1-mini")
dbutils.widgets.text("deepseek_model", "deepseek-chat")
dbutils.widgets.text("sample_table", "")
dbutils.widgets.text("output_root", "/dbfs/FileStore/contractforge-ai-smoke")
dbutils.widgets.text("require_provider", "false")

# COMMAND ----------

if dbutils.widgets.get("install_wheels").lower() == "true":
    import subprocess
    import sys

    contractforge_wheel = dbutils.widgets.get("contractforge_wheel")
    contractforge_ai_wheel = dbutils.widgets.get("contractforge_ai_wheel")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--upgrade",
            "--no-deps",
            contractforge_wheel,
            contractforge_ai_wheel,
        ]
    )
    dbutils.library.restartPython()

# COMMAND ----------

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contractforge_ai.agentic import IntentGenerationRequest, generate_from_intent
from contractforge_ai.projects import write_project_plan
from contractforge_ai.providers import ProviderConfig, create_provider

if "display" not in globals():
    def display(value):
        print(value)

# COMMAND ----------

run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
output_root = Path(dbutils.widgets.get("output_root")) / run_id
output_root.mkdir(parents=True, exist_ok=True)

print(f"Run ID: {run_id}")
print(f"Output root: {output_root}")
print(f"Download URL path: /files/contractforge-ai-smoke/{run_id}/")

# COMMAND ----------

sample_table = dbutils.widgets.get("sample_table").strip()
if not sample_table:
    rows = [
        ("O-1001", "C-001", "ana@example.com", 159.30, "paid", "2026-05-20T10:45:00Z"),
        ("O-1002", "C-002", "bruno@example.com", 48.00, "pending", "2026-05-21T12:04:00Z"),
    ]
    columns = ["order_id", "customer_id", "customer_email", "amount", "status", "updated_at"]
    spark.createDataFrame(rows, columns).createOrReplaceTempView("cf_ai_orders_sample")
    sample_table = "cf_ai_orders_sample"

print(f"Using sample table: {sample_table}")

# COMMAND ----------

def _provider_from_widgets():
    provider_name = dbutils.widgets.get("provider").strip().lower()
    if provider_name in {"", "offline", "none"}:
        return None

    scope = dbutils.widgets.get("provider_secret_scope")
    if provider_name == "openai":
        return create_provider(
            ProviderConfig(
                provider="openai",
                model=dbutils.widgets.get("openai_model"),
                api_key=dbutils.secrets.get(scope, dbutils.widgets.get("openai_secret_key")),
                timeout=120,
                max_retries=1,
            )
        )
    if provider_name == "deepseek":
        return create_provider(
            ProviderConfig(
                provider="deepseek",
                model=dbutils.widgets.get("deepseek_model"),
                api_key=dbutils.secrets.get(scope, dbutils.widgets.get("deepseek_secret_key")),
                timeout=120,
                max_retries=1,
            )
        )
    raise ValueError(f"Unsupported smoke provider: {provider_name}")


provider_status = {"provider": dbutils.widgets.get("provider"), "status": "NOT_REQUESTED"}
try:
    provider = _provider_from_widgets()
    provider_status = {
        "provider": dbutils.widgets.get("provider"),
        "status": "CONFIGURED" if provider else "SKIPPED",
    }
except Exception as exc:
    provider = None
    provider_status = {
        "provider": dbutils.widgets.get("provider"),
        "status": "FAILED",
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }

print(provider_status)

# COMMAND ----------

prompt = (
    f"Create a gold ContractForge project from {sample_table} into main.gold.g_orders_ai_smoke. "
    "Use final columns: order_id, customer_id, customer_email, amount, status, updated_at. "
    "Use scd1_hash_diff where relevant, classify customer_email as PII, add quality gates, annotations, operations metadata, "
    "and produce reviewable artifacts for Databricks."
)

result = generate_from_intent(
    IntentGenerationRequest(
        prompt=prompt,
        sample_table=sample_table,
        default_catalog="main",
        provider=provider,
        spark=spark,
    )
)

print("Generation status:", result.status)
print("Layers:", result.layers)
print("Transformation plan:", result.transformation_plan.to_dict() if result.transformation_plan else None)

# COMMAND ----------

result_path = output_root / "result.json"
result_path.write_text(json.dumps(result.to_dict(include_content=True), indent=2, ensure_ascii=False), encoding="utf-8")

if result.project:
    write_project_plan(result.project, output_root / "artifacts", force=True)
    for artifact in result.project.artifacts:
        if artifact.path == "AI_REVIEW.html":
            (output_root / "AI_REVIEW.html").write_text(artifact.content, encoding="utf-8")

summary = {
    "run_id": run_id,
    "sample_table": sample_table,
    "status": result.status,
    "layers": result.layers,
    "provider_status": provider_status,
    "pre_generation_enrichment_status": result.pre_generation_enrichment.status if result.pre_generation_enrichment else "NOT_REQUESTED",
    "transformation_enrichment_status": result.transformation_enrichment.status if result.transformation_enrichment else "NOT_REQUESTED",
    "post_generation_enrichment_status": result.enrichment.status if result.enrichment else "NOT_REQUESTED",
    "artifact_count": len(result.project.artifacts) if result.project else 0,
    "artifact_root": str(output_root),
    "download_url_path": f"/files/contractforge-ai-smoke/{run_id}/",
    "review_html": f"/files/contractforge-ai-smoke/{run_id}/AI_REVIEW.html",
    "result_json": f"/files/contractforge-ai-smoke/{run_id}/result.json",
}

(output_root / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

display(summary)

# COMMAND ----------

require_provider = dbutils.widgets.get("require_provider").lower() == "true"
if provider_status["status"] == "FAILED":
    raise RuntimeError(f"Provider configuration failed: {provider_status}")
if require_provider and not any(
    status == "ENRICHED"
    for status in (
        summary["pre_generation_enrichment_status"],
        summary["transformation_enrichment_status"],
        summary["post_generation_enrichment_status"],
    )
):
    raise RuntimeError("Provider was required, but no generation enrichment stage returned ENRICHED.")

dbutils.notebook.exit(json.dumps(summary, ensure_ascii=False))
