from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_adapter_authoring_spec_documents_public_adapter_contract() -> None:
    doc = (ROOT / "docs" / "specs" / "adapter-authoring.md").read_text(encoding="utf-8")
    required = {
        "Public Core APIs To Use",
        "Minimal Adapter Protocol",
        "Capability Declaration Contract",
        "Planning Result Semantics",
        "Contract Sections Adapters Must Understand",
        "Source Translation Requirements",
        "Write Mode Requirements",
        "Evidence And Control Tables",
        "Environment Contract",
        "Runtime Execution Pattern",
        "Testing Requirements For A Functional Adapter",
        "Adapter Acceptance Checklist",
        "AWS",
        "Fabric",
        "Snowflake",
        "GCP",
        "AWS_UNKNOWN_EXTENSION",
        "DATABRICKS_UNKNOWN_EXTENSION",
    }

    missing = sorted(item for item in required if item not in doc)

    assert missing == []


def test_readme_points_adapter_authors_to_the_spec() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/specs/adapter-authoring.md" in readme


def test_adapter_authoring_gcp_entry_documents_stable_scope() -> None:
    doc = (ROOT / "docs" / "specs" / "adapter-authoring.md").read_text(encoding="utf-8")

    assert "BigLake Iceberg tables" in doc
    assert "Dataplex data-quality create plus execution/readback planning" in doc
    assert "explicit Dataplex lineage/aspect command execution/readback" in doc
    assert "scoped stable surface" in doc


def test_adapter_technical_checklist_tracks_current_adapters() -> None:
    doc = (
        ROOT / "docs" / "specs" / "adapter-technical-review-checklist.md"
    ).read_text(encoding="utf-8")

    assert "adapters/fabric/src/contractforge_fabric" in doc
    assert "adapters/gcp/src/contractforge_gcp" in doc
    assert "future GCP" not in doc
    assert "| Fabric | 0 | 0 | 0 | 0 | 0/10 |" in doc
