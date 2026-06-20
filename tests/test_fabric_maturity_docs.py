from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_central_docs_describe_current_fabric_stable_surface_claim() -> None:
    adapters = (ROOT / "docs" / "adapters.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "| Fabric | `contractforge-fabric` | Stable supported surface" in adapters
    assert "`contractforge-fabric` | Stable supported surface" in roadmap
    assert "Private-network shortcuts, managed identity/OAuth object-storage access" in adapters
    assert "excluded from stable-final" in roadmap
    assert "not yet a full stable claim" not in roadmap
    assert "| `contractforge-fabric` | Planned |" not in roadmap

    assert "[Fabric adapter](adapters/fabric.md)" in readme
    assert "[Fabric stable-surface evidence](reports/fabric-stable-surface-evidence.json)" in readme
    assert "[Fabric platform parity report](reports/fabric-platform-parity.json)" in readme
    assert (
        "[Fabric source-expansion stable-scope decision]"
        "(reports/fabric-source-expansion-stable-scope-decision.json)"
        in readme
    )
    assert "[Fabric project deploy-only smoke](reports/fabric-project-deploy-smoke.json)" in readme
    assert "[Fabric OneLake data access role smoke](reports/fabric-onelake-data-access-role-smoke.json)" in readme
    assert "[Fabric OneLake row/column policy smoke](reports/fabric-onelake-row-column-policy-smoke.json)" in readme
    assert "[Fabric deployment pipeline read probe](reports/fabric-deployment-pipeline-read-probe.json)" in readme
    assert (
        "[Fabric deployment pipeline lifecycle smoke](reports/fabric-deployment-pipeline-lifecycle-smoke.json)"
        in readme
    )
    assert (
        "[Fabric deployment pipeline stage promotion smoke]"
        "(reports/fabric-deployment-pipeline-stage-promotion-smoke.json)"
        in readme
    )
    assert "[Fabric HTTP JSON source smoke](reports/fabric-http-json-source-smoke.json)" in readme
    assert "[Fabric HTTP CSV source smoke](reports/fabric-http-csv-source-smoke.json)" in readme
    assert "[Fabric HTTP text source smoke](reports/fabric-http-text-source-smoke.json)" in readme
    assert "[Fabric Lakehouse text source smoke](reports/fabric-lakehouse-text-source-smoke.json)" in readme
    assert (
        "[Fabric Lakehouse file formats source smoke](reports/fabric-lakehouse-file-formats-source-smoke.json)"
        in readme
    )
    assert "[Fabric OneLake shortcut source smoke](reports/fabric-onelake-shortcut-source-smoke.json)" in readme
    assert "[Fabric authenticated REST source smoke](reports/fabric-auth-rest-source-smoke.json)" in readme
    assert "[Fabric authenticated REST variants source smoke](reports/fabric-auth-rest-variants-source-smoke.json)" in readme
    assert "[Fabric authenticated REST OAuth source smoke](reports/fabric-auth-rest-oauth-source-smoke.json)" in readme
    assert "[Fabric authenticated HTTP JSON source smoke](reports/fabric-auth-http-json-source-smoke.json)" in readme
    assert "[Fabric authenticated HTTP JSON variants source smoke](reports/fabric-auth-http-json-variants-source-smoke.json)" in readme
    assert "[Fabric authenticated HTTP CSV variants source smoke](reports/fabric-auth-http-csv-variants-source-smoke.json)" in readme
    assert "[Fabric authenticated HTTP text Basic source smoke](reports/fabric-auth-http-text-basic-source-smoke.json)" in readme
    assert "[Fabric authenticated HTTP text bearer source smoke](reports/fabric-auth-http-text-bearer-source-smoke.json)" in readme
    assert "[Fabric authenticated HTTP text API-key source smoke](reports/fabric-auth-http-text-api-key-source-smoke.json)" in readme
    assert "[Fabric SQL Server JDBC source smoke](reports/fabric-sqlserver-jdbc-source-smoke.json)" in readme
    assert "[Fabric PostgreSQL JDBC source smoke](reports/fabric-postgres-jdbc-source-smoke.json)" in readme
    assert "[Fabric Azure Blob source smoke](reports/fabric-azure-blob-source-smoke.json)" in readme
    assert "[Fabric private Azure Blob source smoke](reports/fabric-private-azure-blob-source-smoke.json)" in readme
    assert (
        "[Fabric external Azure Blob shortcut source smoke](reports/fabric-external-azure-blob-shortcut-source-smoke.json)"
        in readme
    )
    assert "[Fabric ADLS Gen2 shortcut source smoke](reports/fabric-adls-shortcut-source-smoke.json)" in readme
    assert "[Fabric GCS shortcut source smoke](reports/fabric-gcs-shortcut-source-smoke.json)" in readme
    assert (
        "[Fabric external Amazon S3 shortcut source smoke](reports/fabric-external-s3-shortcut-source-smoke.json)"
        in readme
    )
    assert (
        "[Fabric S3-compatible shortcut source smoke](reports/fabric-s3-compatible-shortcut-source-smoke.json)"
        in readme
    )
    assert (
        "[Fabric Iceberg table shortcut source smoke](reports/fabric-iceberg-table-shortcut-source-smoke.json)"
        in readme
    )
    assert (
        "[Fabric ADLS Iceberg table shortcut source smoke](reports/fabric-adls-iceberg-table-shortcut-source-smoke.json)"
        in readme
    )
    assert (
        "[Fabric GCS Iceberg table shortcut source smoke](reports/fabric-gcs-iceberg-table-shortcut-source-smoke.json)"
        in readme
    )
    assert "[Fabric Confluent Kafka bounded source smoke](reports/fabric-confluent-kafka-bounded-source-smoke.json)" in readme
    assert (
        "[Fabric Confluent Kafka available-now source smoke](reports/fabric-confluent-kafka-available-now-source-smoke.json)"
        in readme
    )
    assert (
        "[Fabric Event Hubs Kafka available-now source smoke](reports/fabric-eventhubs-kafka-available-now-source-smoke.json)"
        in readme
    )


def test_fabric_adapter_guide_links_evidence_and_boundaries() -> None:
    guide = (ROOT / "docs" / "adapters" / "fabric.md").read_text(encoding="utf-8")

    required = [
        "stable supported notebook-first Fabric Lakehouse",
        "public/no-auth bounded `rest_api`",
        "public/no-auth `http_json`",
        "Fabric HTTP CSV source smoke",
        "Fabric HTTP text source smoke",
        "Fabric Lakehouse text source smoke",
        "Fabric Lakehouse file formats source smoke",
        "Fabric OneLake shortcut source smoke",
        "authenticated bounded REST",
        "Fabric stable-surface evidence",
        "Fabric platform parity report",
        "Fabric source-expansion stable-scope decision",
        "Fabric project deploy-only smoke",
        "Fabric OneLake data access role smoke",
        "Fabric OneLake row/column policy smoke",
        "Fabric deployment pipeline read probe",
        "Fabric deployment pipeline lifecycle smoke",
        "Fabric deployment pipeline stage promotion smoke",
        "Fabric HTTP JSON source smoke",
        "Fabric authenticated REST source smoke",
        "Fabric authenticated REST variants source smoke",
        "Fabric authenticated REST OAuth source smoke",
        "Fabric authenticated HTTP JSON source smoke",
        "Fabric authenticated HTTP JSON variants source smoke",
        "Fabric authenticated HTTP CSV variants source smoke",
        "Fabric authenticated HTTP text Basic source smoke",
        "Fabric authenticated HTTP text bearer source smoke",
        "Fabric authenticated HTTP text API-key source smoke",
        "Fabric SQL Server JDBC source smoke",
        "Fabric PostgreSQL JDBC source smoke",
        "Fabric Azure Blob source smoke",
        "Fabric private Azure Blob source smoke",
        "Fabric external Azure Blob shortcut source smoke",
        "Fabric ADLS Gen2 shortcut source smoke",
        "Fabric GCS shortcut source smoke",
        "Fabric external Amazon S3 shortcut source smoke",
        "Fabric S3-compatible shortcut source smoke",
        "Fabric Iceberg table shortcut source smoke",
        "Fabric ADLS Iceberg table shortcut source smoke",
        "Fabric GCS Iceberg table shortcut source smoke",
        "Fabric Confluent Kafka bounded source smoke",
        "Fabric Confluent Kafka available-now source smoke",
        "Fabric Event Hubs Kafka available-now source smoke",
        "bounded Confluent Kafka path",
        "Event Hubs Kafka-compatible",
        "Kafka bounded and available-now paths",
        "TooManyRequestsForCapacity",
        "OAuth client-credentials",
        "workspace role assignments through the Fabric",
        "items/bulkSetLabels",
        "items/{itemId}/dataAccessRoles",
        "row/column constraints against a Fabric-resolved Lakehouse table",
        "table grants, row filters, column masks",
        "live Data Factory pipeline deployment",
        "create/list/delete lifecycle and stage-to-stage Notebook content promotion",
        "stage-to-stage Notebook content promotion",
        "stabilization-report --strict-final",
        "stable-final claim",
        "../../adapters/fabric/PARITY.md",
    ]

    for phrase in required:
        assert phrase in guide
