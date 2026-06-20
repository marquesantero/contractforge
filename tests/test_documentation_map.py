from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


USER_DOCS = [
    "docs/README.md",
    "docs/quickstart.md",
    "docs/usage-guide.md",
    "docs/architecture.md",
    "docs/contracts.md",
    "docs/project-yaml.md",
    "docs/connection-yaml.md",
    "docs/cli.md",
    "docs/adapters.md",
    "docs/databricks.md",
    "docs/roadmap.md",
    "docs/connectors.md",
    "docs/operations.md",
    "docs/security.md",
    "docs/naming.md",
    "docs/project-template.md",
    "docs/anti-patterns.md",
]


def test_readme_links_user_documentation_and_adapter_boundary() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    required = [
        "# ContractForge",
        "Define ingestion intent once. Run it natively anywhere.",
        "Why ContractForge",
        "Honest portability",
        "Status And Roadmap",
        "docs/assets/logo/contractforge-logo.png",
        "contractforge-core",
        "contractforge-databricks",
        "contractforge-fabric",
        "contractforge-gcp",
        "adapters/fabric",
        "adapters/gcp",
        "https://github.com/marquesantero/contractforge/actions/workflows/ci.yml",
        "https://img.shields.io/badge/python-%3E%3D3.10-blue",
        "docs/assets/diagrams/contractforge-flow.svg",
        "The core does not import Spark, Databricks SDK, boto3, Azure SDK, Fabric SDK or Snowflake clients.",
        "docs/README.md",
        "docs/specs/publication-packaging.md",
        "docs/adapters.md",
        "docs/project-yaml.md",
        "docs/databricks.md",
        "docs/roadmap.md",
        "| Fabric | `contractforge-fabric` | Stable supported surface",
        "| GCP | `contractforge-gcp` | Stable supported surface",
    ]

    for phrase in required:
        assert phrase in readme


def test_readme_ci_badge_points_to_existing_workflow() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "actions/workflows/ci.yml" in readme
    assert (ROOT / ".github" / "workflows" / "ci.yml").exists()


def test_user_documentation_files_exist_and_have_titles() -> None:
    for relative_path in USER_DOCS:
        doc = ROOT / relative_path
        content = doc.read_text(encoding="utf-8")

        assert doc.exists()
        assert content.startswith("# ")


def test_docs_index_links_core_guides_and_specs() -> None:
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    required_links = [
        "quickstart.md",
        "usage-guide.md",
        "contracts.md",
        "project-yaml.md",
        "connection-yaml.md",
        "cli.md",
        "adapters.md",
        "databricks.md",
        "roadmap.md",
        "specs/semantic-contract.md",
        "specs/adapter-authoring.md",
        "specs/databricks-ga-criteria.md",
        "specs/databricks-ga-waivers.md",
        "specs/extensions-aws.md",
        "specs/aws-ga-criteria.md",
        "specs/aws-ga-waivers.md",
        "specs/snowflake-ga-criteria.md",
        "specs/snowflake-ga-waivers.md",
        "specs/aws-snowflake-production-maturity-plan.md",
        "specs/hash-diff-production-benchmark-runbook.md",
        "specs/api-stability.md",
        "specs/publication-packaging.md",
        "adrs",
    ]

    for link in required_links:
        assert link in index


def test_adapter_docs_keep_core_and_platform_boundaries_clear() -> None:
    adapters = (ROOT / "docs" / "adapters.md").read_text(encoding="utf-8")
    databricks = (ROOT / "docs" / "databricks.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

    assert "adapter -> contractforge-core" in adapters
    assert "contractforge-core -> no adapter dependency" in adapters
    assert "The adapter wheel owns:" in databricks
    assert "The core wheel does not include this package." in databricks
    assert "Second Adapter Criteria" in roadmap
    assert "`contractforge-databricks`" in roadmap
    assert "`contractforge-aws`" in roadmap
    assert "`contractforge-fabric`" in adapters
    assert "`contractforge-gcp`" in adapters
    assert "| Fabric | `contractforge-fabric` | Stable supported surface" in adapters
    assert "| GCP | `contractforge-gcp` | Stable supported surface" in adapters
    assert "reports/gcp-stable-surface-evidence.json" in adapters
    assert "validated table/SQL/GCS-source runtime enforcement" in adapters
    assert "certified Google Workflows deployment runner" in adapters
    assert "repeated full-project rerun execution/readback" in adapters
    assert "real-account schema-policy E2E promotion" not in adapters
    assert "optionally enforce table-source schema policy" not in (
        ROOT / "docs" / "adapters" / "gcp.md"
    ).read_text(encoding="utf-8")
    assert "`contractforge-fabric` | Stable supported surface" in roadmap
    assert "`contractforge-gcp` | Stable supported surface" in roadmap
    assert "validated table/SQL/GCS-source runtime enforcement" in roadmap
    assert "certified Google Workflows deployment runner" in roadmap
    assert "repeated full-project rerun execution/readback" in roadmap
    assert "real-account schema-policy E2E promotion" not in roadmap


def test_repository_docs_link_project_yaml_and_connector_reference() -> None:
    project = (ROOT / "docs" / "project-yaml.md").read_text(encoding="utf-8")
    connectors = (ROOT / "docs" / "connectors.md").read_text(encoding="utf-8")
    connection_yaml = (ROOT / "docs" / "connection-yaml.md").read_text(encoding="utf-8")
    adapter_portability = (
        ROOT / "docs" / "adapters" / "test-contracts-across-adapters.md"
    ).read_text(encoding="utf-8")

    assert "project://connections/supabase.yaml" in project
    assert "contractforge validate-project" in project
    assert "source.type: connection" in project
    assert "project://connections/" in project
    assert "source.type: connection" in connectors
    assert "project://connections/" in connectors
    assert "Ingestion `source`" in connection_yaml
    assert "These values win" in connection_yaml
    assert "read.fetchsize" in connection_yaml
    assert "Test Contracts Across Adapters" in adapter_portability
    assert "Define ingestion intent once. Run it natively anywhere." in adapter_portability
    assert "Reused Contract Set" in adapter_portability
    assert "Shared Contract Parameters" in adapter_portability
    assert "Shared Contract Content" in adapter_portability
    assert "Exact same block in Databricks, AWS, Snowflake, Fabric and GCP" in adapter_portability
    assert "quality_rules:" in adapter_portability
    assert "runbook_url: https://example.com/runbooks/contractforge/usgs-earthquake-feed" in adapter_portability
    assert "Contract Parameter Differences" in adapter_portability
    assert "Contract Parameter Snippets" in adapter_portability
    assert "bronze_usgs_geojson.ingestion.yaml" in adapter_portability
    assert "silver_usgs_events.ingestion.yaml" in adapter_portability
    assert "gold_usgs_daily_summary.ingestion.yaml" in adapter_portability
    assert "gold_usgs_magnitude_bands.ingestion.yaml" in adapter_portability
    assert "Each adapter writes to its native table namespace." in adapter_portability
    assert "CF_USGS_REST_ACCESS" in adapter_portability
    assert "CONTRACTFORGE_TEST_DB.PUBLIC.CF_USGS_GEOJSON_DATA/frozen/" not in adapter_portability
    assert "For the Snowflake USGS hosted-procedure validation" not in adapter_portability
    assert "Source Execution Boundary" not in adapter_portability
    assert "Snowflake Source Boundary" not in adapter_portability
    assert "Runtime/environment uses Snowflake" not in adapter_portability
