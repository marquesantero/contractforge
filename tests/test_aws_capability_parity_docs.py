import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_aws_capability_parity_documents_official_native_surfaces() -> None:
    doc = (ROOT / "docs" / "specs" / "aws-capability-parity.md").read_text(encoding="utf-8")

    required = [
        "AWS Glue Spark",
        "Apache Iceberg",
        "AWS Glue Data Quality",
        "DQDL",
        "EvaluateDataQuality",
        "Lake Formation data filters",
        "Glue job bookmarks",
        "native connectors",
        "hash_diff_upsert",
        "historical",
        "native passthrough",
        "https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-format-iceberg.html",
        "https://docs.aws.amazon.com/glue/latest/dg/dqdl.html",
        "https://docs.aws.amazon.com/lake-formation/latest/dg/data-filtering.html",
    ]

    for phrase in required:
        assert phrase in doc


def test_aws_docs_link_capability_parity_spec() -> None:
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    aws = (ROOT / "docs" / "adapters" / "aws.md").read_text(encoding="utf-8")
    spec = (ROOT / "docs" / "specs" / "aws-adapter.md").read_text(encoding="utf-8")

    assert "specs/aws-capability-parity.md" in index
    assert "../specs/aws-capability-parity.md" in aws
    assert "aws-capability-parity.md" in spec


def test_aws_docs_define_stable_surface_gate_and_waivers() -> None:
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    aws = (ROOT / "docs" / "adapters" / "aws.md").read_text(encoding="utf-8")
    criteria = (ROOT / "docs" / "specs" / "aws-ga-criteria.md").read_text(encoding="utf-8")
    waivers = (ROOT / "docs" / "specs" / "aws-ga-waivers.md").read_text(encoding="utf-8")

    assert "specs/aws-ga-criteria.md" in index
    assert "specs/aws-ga-waivers.md" in index
    assert "../specs/aws-ga-criteria.md" in aws
    assert "STABLE_SUPPORTED_SURFACE" in criteria
    assert "stable_final = true" in criteria
    assert "No waivers are currently recorded." in waivers


def test_aws_stable_surface_evidence_manifest_is_complete() -> None:
    manifest = json.loads((ROOT / "docs" / "reports" / "aws-stable-surface-evidence.json").read_text(encoding="utf-8"))

    assert manifest["kind"] == "contractforge_aws_stable_surface_evidence"
    assert manifest["classification"] == "STABLE_SUPPORTED_SURFACE"
    assert manifest["supported_surface_ready"] is True
    assert manifest["stable_final"] is True
    assert manifest["stability_criteria"] == "docs/specs/aws-ga-criteria.md"
    assert manifest["waiver_registry"] == "docs/specs/aws-ga-waivers.md"
    assert {project["name"] for project in manifest["real_validation_projects"]} >= {
        "aws_supabase_jdbc_medallion",
        "aws_usgs_rest_medallion",
        "aws_s3_file_medallion",
        "aws_incremental_files",
        "aws_failure_paths",
        "aws_eventhubs_kafka_available_now",
        "aws_hashdiff_production_benchmark",
    }
    assert {boundary["code"] for boundary in manifest["accepted_review_boundaries"]} >= {
        "AWS_HASH_DIFF_PERFORMANCE_UNVALIDATED",
        "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW",
        "AWS_LAKE_FORMATION_GOVERNANCE_REVIEW",
        "AWS_SCD2_REVIEW",
    }
    historical = next(boundary for boundary in manifest["accepted_review_boundaries"] if boundary["code"] == "AWS_SCD2_REVIEW")
    assert historical["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    kafka = next(
        boundary
        for boundary in manifest["accepted_review_boundaries"]
        if boundary["code"] == "AWS_AVAILABLE_NOW_STREAMING_PROVIDER_REVIEW"
    )
    lf = next(
        boundary
        for boundary in manifest["accepted_review_boundaries"]
        if boundary["code"] == "AWS_LAKE_FORMATION_GOVERNANCE_REVIEW"
    )
    assert kafka["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert lf["decision"] == "EXCLUDED_FROM_STABLE_FINAL"
    assert manifest["same_contract_e2e"]["status"] == "PASS"
    assert set(manifest["same_contract_e2e"]["platforms"]) == {"databricks", "aws", "snowflake"}
