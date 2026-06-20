"""Doc-shape guards for the Databricks GA criteria and waiver registry.

These tests protect the GA gate documents from silent drift. They check
section presence and required vocabulary; they do not parse semantics.

String checks compare against a whitespace-normalized version of the
document so that markdown line wrapping does not cause spurious failures.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GA_CRITERIA_PATH = ROOT / "docs" / "specs" / "databricks-ga-criteria.md"
WAIVERS_PATH = ROOT / "docs" / "specs" / "databricks-ga-waivers.md"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_databricks_ga_criteria_doc_exists_and_has_required_sections() -> None:
    doc = GA_CRITERIA_PATH.read_text(encoding="utf-8")
    required = {
        "## Purpose",
        "## Scope Of This Gate",
        "## Inherited Preconditions",
        "## GA Criteria",
        "### 1. Write Modes",
        "### 2. Source Connectors",
        "### 3. Schema Policy",
        "### 4. Quality Rules",
        "### 5. Governance And Annotations",
        "### 6. Operations Metadata",
        "### 7. Evidence Stores",
        "### 8. Lineage",
        "### 9. Cost Signals",
        "### 10. Parity Scenarios",
        "## Live Workspace Smoke",
        "## Post-GA Breaking Change Policy",
        "## De-GA Criteria",
        "## 1.0.0 Release Checklist",
        "## Non-Goals Of This Gate",
        "## Open Items Before The Gate Is Active",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_ga_criteria_lists_each_portable_write_mode() -> None:
    doc = GA_CRITERIA_PATH.read_text(encoding="utf-8")
    required = {
        "append",
        "overwrite",
        "upsert",
        "hash_diff_upsert",
        "historical",
        "snapshot_reconcile_soft_delete",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_ga_criteria_lists_each_evidence_table() -> None:
    doc = GA_CRITERIA_PATH.read_text(encoding="utf-8")
    required = {
        "ctrl_ingestion_runs",
        "ctrl_ingestion_errors",
        "ctrl_ingestion_quality",
        "ctrl_ingestion_state",
        "ctrl_ingestion_locks",
        "ctrl_ingestion_schema_changes",
        "ctrl_ingestion_lineage",
        "ctrl_ingestion_streams",
        "ctrl_ingestion_annotations",
        "ctrl_ingestion_access",
        "ctrl_ingestion_operations",
        "ctrl_ingestion_explain",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_ga_criteria_references_inherited_precondition_tests() -> None:
    doc = GA_CRITERIA_PATH.read_text(encoding="utf-8")
    required = {
        "tests/test_core_platform_independence.py",
        "tests/test_adapter_independence.py",
        "ai/tests/test_architecture_boundaries.py",
        "tests/test_publication_packaging.py",
        "tests/test_package_version.py",
        "tests/test_databricks_contractforge_parity_docs.py",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_ga_criteria_records_workspace_smoke_decision() -> None:
    doc = GA_CRITERIA_PATH.read_text(encoding="utf-8")

    assert "cf_supabase_jdbc_e2e_v2_ops" in doc
    assert "supabase-jdbc-medallion" in doc
    assert "Weekly cron" in doc
    assert "workflow_dispatch" in doc
    assert "databricks-smoke.yml" in doc


def test_databricks_ga_criteria_states_core_couples_to_databricks_ga() -> None:
    doc = _normalize(GA_CRITERIA_PATH.read_text(encoding="utf-8"))

    assert "Core (`contractforge-core`) GA is bound to Databricks GA" in doc


def test_databricks_ga_criteria_each_criterion_declares_verification() -> None:
    doc = GA_CRITERIA_PATH.read_text(encoding="utf-8")
    headings = (
        "### 1. Write Modes",
        "### 2. Source Connectors",
        "### 3. Schema Policy",
        "### 4. Quality Rules",
        "### 5. Governance And Annotations",
        "### 6. Operations Metadata",
        "### 7. Evidence Stores",
        "### 8. Lineage",
        "### 9. Cost Signals",
        "### 10. Parity Scenarios",
    )

    missing: list[str] = []
    for heading in headings:
        start = doc.find(heading)
        assert start != -1, heading
        # Look at the section body up to the next heading at the same or higher level.
        next_section = doc.find("\n### ", start + len(heading))
        next_super = doc.find("\n## ", start + len(heading))
        candidates = [pos for pos in (next_section, next_super) if pos != -1]
        end = min(candidates) if candidates else len(doc)
        body = doc[start:end]
        if (
            "**What must hold.**" not in body
            or "**How to verify.**" not in body
            or "**Status.**" not in body
        ):
            missing.append(heading)

    assert missing == []


def test_databricks_ga_waivers_doc_exists_and_has_required_sections() -> None:
    doc = WAIVERS_PATH.read_text(encoding="utf-8")
    required = {
        "## Purpose",
        "## When A Waiver Is Allowed",
        "## Waiver Lifecycle",
        "## Approval Requirements",
        "## Waiver Entry Format",
        "## Registry",
        "## Active Waivers",
        "## Expired Waivers",
        "## Revoked Waivers",
        "## Cross-References",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_ga_waivers_declares_forbidden_categories() -> None:
    doc = WAIVERS_PATH.read_text(encoding="utf-8")
    required = {
        "core platform isolation",
        "adapter independence boundaries",
        "ctrl_ingestion_runs",
        "ctrl_ingestion_errors",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_databricks_ga_waivers_caps_waiver_window_at_90_days() -> None:
    doc = _normalize(WAIVERS_PATH.read_text(encoding="utf-8"))

    assert "90 days" in doc
    assert "never deleted" in doc


def test_databricks_ga_criteria_references_waiver_registry() -> None:
    doc = GA_CRITERIA_PATH.read_text(encoding="utf-8")

    assert "databricks-ga-waivers.md" in doc


def test_databricks_adapter_doc_links_kafka_contract_runtime_evidence() -> None:
    doc = (ROOT / "docs" / "databricks.md").read_text(encoding="utf-8")
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "`kafka_available_now`" in doc
    assert "reports/databricks-stable-surface-evidence.json" in doc
    assert "reports/databricks-stable-surface-evidence.json" in index
    assert "reports/databricks-kafka-provider-smoke.json" in doc
