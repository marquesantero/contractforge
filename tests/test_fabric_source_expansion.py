from __future__ import annotations

import json
import yaml
from pathlib import Path

from contractforge_core.contracts import load_contract_bundle
from contractforge_fabric import fabric_source_support, plan_fabric_contract, render_fabric_contract


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples" / "source-expansion" / "fabric-http-json"
HTTP_CSV_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-http-csv"
HTTP_TEXT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-http-text"
LAKEHOUSE_TEXT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-lakehouse-text"
LAKEHOUSE_FILE_FORMATS_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-lakehouse-file-formats"
ONELAKE_SHORTCUT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-onelake-shortcut"
AUTH_REST_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-rest"
AUTH_REST_VARIANTS_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-rest-variants"
AUTH_REST_OAUTH_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-rest-oauth"
AUTH_HTTP_JSON_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-http-json"
AUTH_HTTP_JSON_VARIANTS_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-http-json-variants"
AUTH_HTTP_CSV_VARIANTS_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-http-csv-variants"
AUTH_HTTP_TEXT_BASIC_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-http-text-basic"
AUTH_HTTP_TEXT_BEARER_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-http-text-bearer"
AUTH_HTTP_TEXT_API_KEY_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-auth-http-text-api-key"
SQLSERVER_JDBC_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-sqlserver-jdbc"
POSTGRES_JDBC_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-postgres-jdbc"
AZURE_BLOB_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-azure-blob"
PRIVATE_AZURE_BLOB_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-private-azure-blob"
EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT = (
    ROOT / "examples" / "source-expansion" / "fabric-external-azure-blob-shortcut"
)
ADLS_SHORTCUT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-adls-shortcut"
GCS_SHORTCUT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-gcs-shortcut"
EXTERNAL_S3_SHORTCUT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-external-s3-shortcut"
S3_COMPATIBLE_SHORTCUT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-s3-compatible-shortcut"
ICEBERG_TABLE_SHORTCUT_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-iceberg-table-shortcut"
ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT = (
    ROOT / "examples" / "source-expansion" / "fabric-adls-iceberg-table-shortcut"
)
GCS_ICEBERG_TABLE_SHORTCUT_PROJECT = (
    ROOT / "examples" / "source-expansion" / "fabric-gcs-iceberg-table-shortcut"
)
CONFLUENT_KAFKA_PROJECT = ROOT / "examples" / "source-expansion" / "fabric-confluent-kafka-bounded"
CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT = (
    ROOT / "examples" / "source-expansion" / "fabric-confluent-kafka-available-now"
)
EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT = (
    ROOT / "examples" / "source-expansion" / "fabric-eventhubs-kafka-available-now"
)


def test_fabric_http_json_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((PROJECT / "project.yaml").read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "http_json"
    assert project["source_expansion"]["authentication"] == "none"
    assert project["source_expansion"]["expected_probe_checks"] == 5
    assert len(project["execution_order"]) == 2
    assert project["execution_order"][0]["name"] == "http_json_usgs_geojson"
    assert project["execution_order"][1]["name"] == "http_json_evidence_probe"


def test_fabric_http_json_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "SUPPORTED_WITH_WARNINGS"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "def _cf_http_file_dataframe(spark, source):" in notebook
    assert "read_http_file_payload(source)" in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
    compile(notebook, "fabric_http_json_source_expansion.fabric.notebook.py", "exec")


def test_fabric_http_json_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(PROJECT / "contracts" / "02_http_json_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.http_json_usgs_geojson" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 5


def test_fabric_http_json_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-http-json-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_json"
    assert manifest["authentication"] == "none"
    assert manifest["project"] == "examples/source-expansion/fabric-http-json/project.yaml"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_http_csv_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((HTTP_CSV_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(HTTP_CSV_PROJECT / "contracts" / "01_http_csv_orders").contract

    assert project["source_expansion"]["source_family"] == "http_csv"
    assert project["source_expansion"]["authentication"] == "none"
    assert project["source_expansion"]["expected_probe_checks"] == 5
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "http_csv"
    assert contract["source"]["options"]["header"] == "true"
    assert "auth" not in contract["source"]


def test_fabric_http_csv_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((HTTP_CSV_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((HTTP_CSV_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = HTTP_CSV_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "SUPPORTED_WITH_WARNINGS"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "read_http_file_payload(source)" in notebook
    assert "return reader.csv(rdd)" in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
    compile(notebook, "fabric_http_csv_source_expansion.fabric.notebook.py", "exec")


def test_fabric_http_csv_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(HTTP_CSV_PROJECT / "contracts" / "02_http_csv_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.http_csv_orders" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 5


def test_fabric_http_csv_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((HTTP_CSV_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-http-csv-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_csv"
    assert manifest["authentication"] == "none"
    assert manifest["project"] == "examples/source-expansion/fabric-http-csv/project.yaml"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_http_text_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((HTTP_TEXT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(HTTP_TEXT_PROJECT / "contracts" / "01_http_text_payload").contract

    assert project["source_expansion"]["source_family"] == "http_text"
    assert project["source_expansion"]["authentication"] == "none"
    assert project["source_expansion"]["expected_probe_checks"] == 5
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "http_text"
    assert "auth" not in contract["source"]


def test_fabric_http_text_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((HTTP_TEXT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((HTTP_TEXT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = HTTP_TEXT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "SUPPORTED_WITH_WARNINGS"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "read_http_file_payload(source)" in notebook
    assert "return rdd.map(lambda value: (value,)).toDF(['value'])" in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
    compile(notebook, "fabric_http_text_source_expansion.fabric.notebook.py", "exec")


def test_fabric_http_text_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(HTTP_TEXT_PROJECT / "contracts" / "02_http_text_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.http_text_payload" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 5


def test_fabric_http_text_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((HTTP_TEXT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-http-text-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_text"
    assert manifest["authentication"] == "none"
    assert manifest["project"] == "examples/source-expansion/fabric-http-text/project.yaml"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_lakehouse_text_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((LAKEHOUSE_TEXT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        LAKEHOUSE_TEXT_PROJECT / "contracts" / "01_lakehouse_text_orders"
    ).contract

    assert project["source_expansion"]["source_family"] == "lakehouse_text"
    assert project["source_expansion"]["authentication"] == "fabric_lakehouse_files"
    assert project["source_expansion"]["expected_probe_checks"] == 5
    assert project["source_expansion"]["fixture_path"] == "Files/source-expansion/lakehouse-text/orders.txt"
    assert len(project["execution_order"]) == 2
    assert contract["source"] == {
        "type": "text",
        "path": "Files/source-expansion/lakehouse-text/orders.txt",
    }


def test_fabric_lakehouse_text_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((LAKEHOUSE_TEXT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (LAKEHOUSE_TEXT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = LAKEHOUSE_TEXT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "SUPPORTED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert 'spark.read.format("text").load("Files/source-expansion/lakehouse-text/orders.txt")' in notebook
    compile(notebook, "fabric_lakehouse_text_source_expansion.fabric.notebook.py", "exec")


def test_fabric_lakehouse_text_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        LAKEHOUSE_TEXT_PROJECT / "contracts" / "02_lakehouse_text_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.lakehouse_text_orders" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 5


def test_fabric_lakehouse_text_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((LAKEHOUSE_TEXT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-lakehouse-text-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "lakehouse_text"
    assert manifest["authentication"] == "fabric_lakehouse_files"
    assert manifest["project"] == "examples/source-expansion/fabric-lakehouse-text/project.yaml"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["source_infrastructure"]["fixture_path"] == project["source_expansion"]["fixture_path"]
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_lakehouse_file_formats_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((LAKEHOUSE_FILE_FORMATS_PROJECT / "project.yaml").read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "lakehouse_file_formats"
    assert project["source_expansion"]["formats"] == ["orc", "avro", "xml"]
    assert project["source_expansion"]["authentication"] == "fabric_lakehouse_files"
    assert project["source_expansion"]["expected_probe_checks"] == 10
    assert len(project["execution_order"]) == 4

    expected = {
        "01_lakehouse_orc_orders": ("orc", "Files/source-expansion/lakehouse-file-formats/orc_orders"),
        "02_lakehouse_avro_orders": ("avro", "Files/source-expansion/lakehouse-file-formats/avro_orders"),
        "03_lakehouse_xml_orders": ("xml", "Files/source-expansion/lakehouse-file-formats/xml_orders"),
    }
    for contract_name, (source_type, path) in expected.items():
        contract = load_contract_bundle(LAKEHOUSE_FILE_FORMATS_PROJECT / "contracts" / contract_name).contract
        assert contract["source"]["type"] == source_type
        assert contract["source"]["path"] == path
        if source_type == "xml":
            assert contract["source"]["options"]["rowTag"] == "order"


def test_fabric_lakehouse_file_formats_source_expansion_plans_and_renders_notebooks() -> None:
    project = yaml.safe_load((LAKEHOUSE_FILE_FORMATS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (LAKEHOUSE_FILE_FORMATS_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    expected_snippets = {
        "lakehouse_orc_orders": 'spark.read.format("orc").load("Files/source-expansion/lakehouse-file-formats/orc_orders")',
        "lakehouse_avro_orders": 'spark.read.format("avro").load("Files/source-expansion/lakehouse-file-formats/avro_orders")',
        "lakehouse_xml_orders": (
            'spark.read.format("xml").option("rowTag", "order")'
            '.load("Files/source-expansion/lakehouse-file-formats/xml_orders")'
        ),
    }
    for step in project["execution_order"][:3]:
        contract_path = LAKEHOUSE_FILE_FORMATS_PROJECT / step["contracts"]["fabric"]
        contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract
        support = fabric_source_support(contract["source"])
        planning = plan_fabric_contract(contract, environment=environment)
        artifacts = render_fabric_contract(contract, environment=environment).artifacts
        notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

        assert support["status"] == "SUPPORTED"
        assert support["renderable"] is True
        assert planning.status == "SUPPORTED_WITH_WARNINGS"
        assert not planning.blockers
        assert expected_snippets[step["name"]] in notebook
        compile(notebook, f"{step['name']}.fabric.notebook.py", "exec")


def test_fabric_lakehouse_file_formats_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        LAKEHOUSE_FILE_FORMATS_PROJECT / "contracts" / "04_lakehouse_file_formats_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.lakehouse_orc_orders" in query
    assert "cf_fabric_source_expansion.lakehouse_avro_orders" in query
    assert "cf_fabric_source_expansion.lakehouse_xml_orders" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 10


def test_fabric_lakehouse_file_formats_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((LAKEHOUSE_FILE_FORMATS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-lakehouse-file-formats-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "lakehouse_file_formats"
    assert manifest["formats"] == ["orc", "avro", "xml"]
    assert manifest["authentication"] == "fabric_lakehouse_files"
    assert manifest["project"] == "examples/source-expansion/fabric-lakehouse-file-formats/project.yaml"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["source_infrastructure"]["fixture_paths"] == project["source_expansion"]["fixture_paths"]
    assert manifest["coverage"]["probe_checks"] == [
        "orc_target_rows",
        "avro_target_rows",
        "xml_target_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
        "orc_amount_sum",
        "avro_amount_sum",
        "xml_amount_sum",
    ]


def test_fabric_onelake_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((ONELAKE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        ONELAKE_SHORTCUT_PROJECT / "contracts" / "01_onelake_shortcut_orc_orders"
    ).contract

    assert project["source_expansion"]["source_family"] == "onelake_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "internal_onelake_files"
    assert project["source_expansion"]["source_format"] == "orc"
    assert project["source_expansion"]["expected_probe_checks"] == 5
    assert len(project["execution_order"]) == 2
    assert contract["source"] == {
        "type": "orc",
        "path": "Files/source-expansion/onelake-shortcuts/source_expansion_shortcut/lakehouse-file-formats/orc_orders",
    }


def test_fabric_onelake_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((ONELAKE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((ONELAKE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = ONELAKE_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "SUPPORTED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert (
        'spark.read.format("orc").load("Files/source-expansion/onelake-shortcuts/source_expansion_shortcut/lakehouse-file-formats/orc_orders")'
        in notebook
    )
    compile(notebook, "fabric_onelake_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_onelake_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        ONELAKE_SHORTCUT_PROJECT / "contracts" / "02_onelake_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.onelake_shortcut_orc_orders" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 5


def test_fabric_onelake_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((ONELAKE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-onelake-shortcut-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "onelake_shortcut"
    assert manifest["shortcut_kind"] == "internal_onelake_files"
    assert manifest["project"] == "examples/source-expansion/fabric-onelake-shortcut/project.yaml"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["source_infrastructure"]["shortcut"] == project["source_expansion"]["shortcut"]
    assert manifest["coverage"]["probe_checks"] == [
        "shortcut_target_rows",
        "shortcut_amount_sum",
        "run_rows",
        "quality_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_rest_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_REST_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(AUTH_REST_PROJECT / "contracts" / "01_authenticated_rest_basic").contract
    environment = yaml.safe_load((AUTH_REST_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "rest_api"
    assert project["source_expansion"]["authentication"] == "basic_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["auth"]["password"] == "{{ secret:fabric/postman-basic-password }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_rest_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((AUTH_REST_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_REST_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = AUTH_REST_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "def _cf_resolve_secret(scope, key):" in notebook
    assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
    assert "_cf_resolve_secret('fabric', 'postman-basic-password')" in notebook
    assert "{{ secret:fabric/postman-basic-password }}" not in notebook
    assert "'password': 'password'" not in notebook
    assert "postman:password" not in notebook
    assert "df = _cf_rest_dataframe(spark, _cf_rest_source)" in notebook
    compile(notebook, "fabric_authenticated_rest_source_expansion.fabric.notebook.py", "exec")


def test_fabric_authenticated_rest_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(AUTH_REST_PROJECT / "contracts" / "02_authenticated_rest_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_rest_basic" in query
    assert "target_authenticated_true" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_authenticated_rest_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_REST_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-auth-rest-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "rest_api"
    assert manifest["authentication"] == "basic_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-rest/project.yaml"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_reference"] == "{{ secret:fabric/postman-basic-password }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_authenticated_true",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_rest_variants_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_REST_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    bearer = load_contract_bundle(AUTH_REST_VARIANTS_PROJECT / "contracts" / "01_authenticated_rest_bearer").contract
    api_key = load_contract_bundle(AUTH_REST_VARIANTS_PROJECT / "contracts" / "02_authenticated_rest_api_key").contract
    environment = yaml.safe_load((AUTH_REST_VARIANTS_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "rest_api"
    assert project["source_expansion"]["authentication"] == "bearer_and_api_key_vault_placeholders"
    assert project["source_expansion"]["expected_probe_checks"] == 8
    assert len(project["execution_order"]) == 3
    assert bearer["source"]["auth"]["type"] == "bearer_token"
    assert bearer["source"]["auth"]["token"] == "{{ secret:fabric/rest-bearer-token }}"
    assert api_key["source"]["auth"]["type"] == "api_key"
    assert api_key["source"]["auth"]["value"] == "{{ secret:fabric/rest-api-key }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_rest_variants_source_expansion_plans_and_renders_notebooks() -> None:
    project = yaml.safe_load((AUTH_REST_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_REST_VARIANTS_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    for step in project["execution_order"][:2]:
        contract_path = AUTH_REST_VARIANTS_PROJECT / step["contracts"]["fabric"]
        contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract
        support = fabric_source_support(contract["source"])
        planning = plan_fabric_contract(contract, environment=environment)
        artifacts = render_fabric_contract(contract, environment=environment).artifacts
        notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

        assert support["status"] == "REVIEW_REQUIRED"
        assert support["renderable"] is True
        assert planning.status == "SUPPORTED_WITH_WARNINGS"
        assert not planning.blockers
        assert "def _cf_resolve_secret(scope, key):" in notebook
        assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
        assert "{{ secret:fabric/" not in notebook
        assert "cf-fabric-" not in notebook
        assert "df = _cf_rest_dataframe(spark, _cf_rest_source)" in notebook
        compile(notebook, f"{step['name']}.fabric.notebook.py", "exec")


def test_fabric_authenticated_rest_variants_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        AUTH_REST_VARIANTS_PROJECT / "contracts" / "03_authenticated_rest_variants_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_rest_bearer" in query
    assert "cf_fabric_source_expansion.auth_rest_api_key" in query
    assert "bearer_header_present" in query
    assert "api_key_header_present" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 8


def test_fabric_authenticated_rest_variants_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_REST_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-auth-rest-variants-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "rest_api"
    assert manifest["authentication"] == "bearer_and_api_key_vault_placeholders"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-rest-variants/project.yaml"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_references"] == [
        "{{ secret:fabric/rest-bearer-token }}",
        "{{ secret:fabric/rest-api-key }}",
    ]
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "bearer_target_rows",
        "bearer_header_present",
        "api_key_target_rows",
        "api_key_header_present",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_rest_oauth_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_REST_OAUTH_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(AUTH_REST_OAUTH_PROJECT / "contracts" / "01_authenticated_rest_oauth").contract
    environment = yaml.safe_load((AUTH_REST_OAUTH_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "rest_api"
    assert project["source_expansion"]["authentication"] == "oauth_client_credentials_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["auth"]["type"] == "oauth_client_credentials"
    assert contract["source"]["auth"]["client_id"] == "00000000-0000-0000-0000-000000000000"
    assert contract["source"]["auth"]["client_secret"] == "{{ secret:fabric/oauth-client-secret }}"
    assert contract["source"]["auth"]["scope"] == "https://management.azure.com/.default"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_rest_oauth_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((AUTH_REST_OAUTH_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_REST_OAUTH_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = AUTH_REST_OAUTH_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "oauth_client_credentials" in notebook
    assert "_cf_resolve_secret('fabric', 'oauth-client-secret')" in notebook
    assert "{{ secret:fabric/oauth-client-secret }}" not in notebook
    assert "df = _cf_rest_dataframe(spark, _cf_rest_source)" in notebook
    compile(notebook, "fabric_authenticated_rest_oauth_source_expansion.fabric.notebook.py", "exec")


def test_fabric_authenticated_rest_oauth_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(AUTH_REST_OAUTH_PROJECT / "contracts" / "02_authenticated_rest_oauth_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_rest_oauth" in query
    assert "oauth_bearer_header_present" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_authenticated_rest_oauth_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_REST_OAUTH_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-auth-rest-oauth-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "rest_api"
    assert manifest["authentication"] == "oauth_client_credentials_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-rest-oauth/project.yaml"
    assert manifest["source_infrastructure"]["identity_provider"] == "microsoft_entra_id"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_reference"] == "{{ secret:fabric/oauth-client-secret }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "oauth_bearer_header_present",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_http_json_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_HTTP_JSON_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(AUTH_HTTP_JSON_PROJECT / "contracts" / "01_authenticated_http_json_basic").contract
    environment = yaml.safe_load((AUTH_HTTP_JSON_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "http_json"
    assert project["source_expansion"]["authentication"] == "basic_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["auth"]["password"] == "{{ secret:fabric/postman-basic-password }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_http_json_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((AUTH_HTTP_JSON_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_HTTP_JSON_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = AUTH_HTTP_JSON_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "def _cf_resolve_secret(scope, key):" in notebook
    assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
    assert "_cf_resolve_secret('fabric', 'postman-basic-password')" in notebook
    assert "{{ secret:fabric/postman-basic-password }}" not in notebook
    assert "'password': 'password'" not in notebook
    assert "postman:password" not in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
    compile(notebook, "fabric_authenticated_http_json_source_expansion.fabric.notebook.py", "exec")


def test_fabric_authenticated_http_json_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(AUTH_HTTP_JSON_PROJECT / "contracts" / "02_authenticated_http_json_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_http_json_basic" in query
    assert "target_authenticated_true" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_authenticated_http_json_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_HTTP_JSON_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-auth-http-json-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_json"
    assert manifest["authentication"] == "basic_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-http-json/project.yaml"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_reference"] == "{{ secret:fabric/postman-basic-password }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_authenticated_true",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_http_json_variants_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_HTTP_JSON_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    bearer = load_contract_bundle(
        AUTH_HTTP_JSON_VARIANTS_PROJECT / "contracts" / "01_authenticated_http_json_bearer"
    ).contract
    api_key = load_contract_bundle(
        AUTH_HTTP_JSON_VARIANTS_PROJECT / "contracts" / "02_authenticated_http_json_api_key"
    ).contract
    environment = yaml.safe_load((AUTH_HTTP_JSON_VARIANTS_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "http_json"
    assert project["source_expansion"]["authentication"] == "bearer_and_api_key_vault_placeholders"
    assert project["source_expansion"]["expected_probe_checks"] == 8
    assert len(project["execution_order"]) == 3
    assert bearer["source"]["auth"]["type"] == "bearer_token"
    assert bearer["source"]["auth"]["token"] == "{{ secret:fabric/rest-bearer-token }}"
    assert api_key["source"]["auth"]["type"] == "api_key"
    assert api_key["source"]["auth"]["value"] == "{{ secret:fabric/rest-api-key }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_http_json_variants_source_expansion_plans_and_renders_notebooks() -> None:
    project = yaml.safe_load((AUTH_HTTP_JSON_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_HTTP_JSON_VARIANTS_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    for step in project["execution_order"][:2]:
        contract_path = AUTH_HTTP_JSON_VARIANTS_PROJECT / step["contracts"]["fabric"]
        contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract
        support = fabric_source_support(contract["source"])
        planning = plan_fabric_contract(contract, environment=environment)
        artifacts = render_fabric_contract(contract, environment=environment).artifacts
        notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

        assert support["status"] == "REVIEW_REQUIRED"
        assert support["renderable"] is True
        assert planning.status == "SUPPORTED_WITH_WARNINGS"
        assert not planning.blockers
        assert "def _cf_resolve_secret(scope, key):" in notebook
        assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
        assert "{{ secret:fabric/" not in notebook
        assert "cf-fabric-" not in notebook
        assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
        compile(notebook, f"{step['name']}.fabric.notebook.py", "exec")


def test_fabric_authenticated_http_json_variants_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        AUTH_HTTP_JSON_VARIANTS_PROJECT / "contracts" / "03_authenticated_http_json_variants_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_http_json_bearer" in query
    assert "cf_fabric_source_expansion.auth_http_json_api_key" in query
    assert "bearer_header_present" in query
    assert "api_key_header_present" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 8


def test_fabric_authenticated_http_json_variants_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_HTTP_JSON_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-auth-http-json-variants-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_json"
    assert manifest["authentication"] == "bearer_and_api_key_vault_placeholders"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-http-json-variants/project.yaml"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_references"] == [
        "{{ secret:fabric/rest-bearer-token }}",
        "{{ secret:fabric/rest-api-key }}",
    ]
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "bearer_target_rows",
        "bearer_header_present",
        "api_key_target_rows",
        "api_key_header_present",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_http_csv_variants_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_HTTP_CSV_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    basic = load_contract_bundle(
        AUTH_HTTP_CSV_VARIANTS_PROJECT / "contracts" / "01_authenticated_http_csv_basic"
    ).contract
    bearer = load_contract_bundle(
        AUTH_HTTP_CSV_VARIANTS_PROJECT / "contracts" / "02_authenticated_http_csv_bearer"
    ).contract
    api_key = load_contract_bundle(
        AUTH_HTTP_CSV_VARIANTS_PROJECT / "contracts" / "03_authenticated_http_csv_api_key"
    ).contract
    environment = yaml.safe_load((AUTH_HTTP_CSV_VARIANTS_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "http_csv"
    assert project["source_expansion"]["authentication"] == "basic_bearer_api_key_vault_placeholders"
    assert project["source_expansion"]["expected_probe_checks"] == 8
    assert len(project["execution_order"]) == 4
    assert basic["source"]["auth"]["type"] == "basic"
    assert basic["source"]["auth"]["password"] == "{{ secret:fabric/postman-basic-password }}"
    assert bearer["source"]["auth"]["type"] == "bearer_token"
    assert bearer["source"]["auth"]["token"] == "{{ secret:fabric/rest-bearer-token }}"
    assert api_key["source"]["auth"]["type"] == "api_key"
    assert api_key["source"]["auth"]["value"] == "{{ secret:fabric/rest-api-key }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_http_csv_variants_source_expansion_plans_and_renders_notebooks() -> None:
    project = yaml.safe_load((AUTH_HTTP_CSV_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_HTTP_CSV_VARIANTS_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    for step in project["execution_order"][:3]:
        contract_path = AUTH_HTTP_CSV_VARIANTS_PROJECT / step["contracts"]["fabric"]
        contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract
        support = fabric_source_support(contract["source"])
        planning = plan_fabric_contract(contract, environment=environment)
        artifacts = render_fabric_contract(contract, environment=environment).artifacts
        notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

        assert support["status"] == "REVIEW_REQUIRED"
        assert support["renderable"] is True
        assert planning.status == "SUPPORTED_WITH_WARNINGS"
        assert not planning.blockers
        assert "def _cf_resolve_secret(scope, key):" in notebook
        assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
        assert "{{ secret:fabric/" not in notebook
        assert "cf-fabric-" not in notebook
        assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
        compile(notebook, f"{step['name']}.fabric.notebook.py", "exec")


def test_fabric_authenticated_http_csv_variants_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        AUTH_HTTP_CSV_VARIANTS_PROJECT / "contracts" / "04_authenticated_http_csv_variants_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_http_csv_basic" in query
    assert "cf_fabric_source_expansion.auth_http_csv_bearer" in query
    assert "cf_fabric_source_expansion.auth_http_csv_api_key" in query
    assert "positive_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 8


def test_fabric_authenticated_http_csv_variants_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_HTTP_CSV_VARIANTS_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-auth-http-csv-variants-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_csv"
    assert manifest["authentication"] == "basic_bearer_api_key_vault_placeholders"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-http-csv-variants/project.yaml"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_references"] == [
        "{{ secret:fabric/postman-basic-password }}",
        "{{ secret:fabric/rest-bearer-token }}",
        "{{ secret:fabric/rest-api-key }}",
    ]
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "basic_target_rows",
        "bearer_target_rows",
        "api_key_target_rows",
        "positive_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_http_text_basic_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_BASIC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        AUTH_HTTP_TEXT_BASIC_PROJECT / "contracts" / "01_authenticated_http_text_basic"
    ).contract
    environment = yaml.safe_load((AUTH_HTTP_TEXT_BASIC_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "http_text"
    assert project["source_expansion"]["authentication"] == "endpoint_enforced_basic_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["auth"]["type"] == "basic"
    assert contract["source"]["auth"]["password"] == "{{ secret:fabric/postman-basic-password }}"
    assert contract["quality_rules"]["expressions"][0]["expression"] == 'value LIKE \'%"authenticated":true%\''
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_http_text_basic_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_BASIC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_HTTP_TEXT_BASIC_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = AUTH_HTTP_TEXT_BASIC_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "def _cf_resolve_secret(scope, key):" in notebook
    assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
    assert "_cf_resolve_secret('fabric', 'postman-basic-password')" in notebook
    assert "{{ secret:fabric/postman-basic-password }}" not in notebook
    assert "'password': 'password'" not in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
    compile(notebook, "fabric_authenticated_http_text_basic_source_expansion.fabric.notebook.py", "exec")


def test_fabric_authenticated_http_text_basic_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        AUTH_HTTP_TEXT_BASIC_PROJECT / "contracts" / "02_authenticated_http_text_basic_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_http_text_basic" in query
    assert "target_authenticated_payload" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_authenticated_http_text_basic_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_BASIC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-auth-http-text-basic-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_text"
    assert manifest["authentication"] == "endpoint_enforced_basic_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-http-text-basic/project.yaml"
    assert manifest["source_infrastructure"]["unauthenticated_status"] == 401
    assert manifest["source_infrastructure"]["wrong_password_status"] == 401
    assert manifest["source_infrastructure"]["authenticated_status"] == 200
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_reference"] == "{{ secret:fabric/postman-basic-password }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_authenticated_payload",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_http_text_bearer_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_BEARER_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        AUTH_HTTP_TEXT_BEARER_PROJECT / "contracts" / "01_authenticated_http_text_bearer"
    ).contract
    environment = yaml.safe_load((AUTH_HTTP_TEXT_BEARER_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "http_text"
    assert project["source_expansion"]["authentication"] == "endpoint_enforced_bearer_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["auth"]["type"] == "bearer_token"
    assert contract["source"]["auth"]["token"] == "{{ secret:fabric/rest-bearer-token }}"
    assert contract["quality_rules"]["expressions"][0]["expression"] == 'value LIKE \'%"authenticated": true%\''
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_http_text_bearer_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_BEARER_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_HTTP_TEXT_BEARER_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = AUTH_HTTP_TEXT_BEARER_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "def _cf_resolve_secret(scope, key):" in notebook
    assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
    assert "_cf_resolve_secret('fabric', 'rest-bearer-token')" in notebook
    assert "{{ secret:fabric/rest-bearer-token }}" not in notebook
    assert "cf-fabric-" not in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
    compile(notebook, "fabric_authenticated_http_text_bearer_source_expansion.fabric.notebook.py", "exec")


def test_fabric_authenticated_http_text_bearer_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        AUTH_HTTP_TEXT_BEARER_PROJECT / "contracts" / "02_authenticated_http_text_bearer_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_http_text_bearer" in query
    assert "target_authenticated_payload" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_authenticated_http_text_bearer_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_BEARER_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-auth-http-text-bearer-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_text"
    assert manifest["authentication"] == "endpoint_enforced_bearer_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-http-text-bearer/project.yaml"
    assert manifest["source_infrastructure"]["unauthenticated_status"] == 401
    assert manifest["source_infrastructure"]["bearer_header_status"] == 200
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_reference"] == "{{ secret:fabric/rest-bearer-token }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_authenticated_payload",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_authenticated_http_text_api_key_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_API_KEY_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        AUTH_HTTP_TEXT_API_KEY_PROJECT / "contracts" / "01_authenticated_http_text_api_key"
    ).contract
    environment = yaml.safe_load((AUTH_HTTP_TEXT_API_KEY_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "http_text"
    assert project["source_expansion"]["authentication"] == "endpoint_enforced_api_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["auth"]["type"] == "api_key"
    assert contract["source"]["auth"]["header"] == "x-api-key"
    assert contract["source"]["auth"]["value"] == "{{ secret:fabric/rest-api-key }}"
    assert contract["quality_rules"]["expressions"][0]["expression"] == "value = 'contractforge_api_key_authenticated=true'"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_authenticated_http_text_api_key_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_API_KEY_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AUTH_HTTP_TEXT_API_KEY_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = AUTH_HTTP_TEXT_API_KEY_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "def _cf_resolve_secret(scope, key):" in notebook
    assert "notebookutils.credentials.getSecret(vault_url, key)" in notebook
    assert "_cf_resolve_secret('fabric', 'rest-api-key')" in notebook
    assert "{{ secret:fabric/rest-api-key }}" not in notebook
    assert "df = _cf_http_file_dataframe(spark, _cf_http_source)" in notebook
    compile(notebook, "fabric_authenticated_http_text_api_key_source_expansion.fabric.notebook.py", "exec")


def test_fabric_authenticated_http_text_api_key_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        AUTH_HTTP_TEXT_API_KEY_PROJECT / "contracts" / "02_authenticated_http_text_api_key_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.auth_http_text_api_key" in query
    assert "target_authenticated_payload" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_authenticated_http_text_api_key_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AUTH_HTTP_TEXT_API_KEY_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-auth-http-text-api-key-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "http_text"
    assert manifest["authentication"] == "endpoint_enforced_api_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-auth-http-text-api-key/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_functions"
    assert manifest["source_infrastructure"]["missing_key_status"] == 401
    assert manifest["source_infrastructure"]["wrong_key_status"] == 403
    assert manifest["source_infrastructure"]["valid_key_status"] == 200
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_reference"] == "{{ secret:fabric/rest-api-key }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_authenticated_payload",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_sqlserver_jdbc_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((SQLSERVER_JDBC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(SQLSERVER_JDBC_PROJECT / "contracts" / "01_sqlserver_jdbc_orders").contract
    environment = yaml.safe_load((SQLSERVER_JDBC_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "jdbc_sqlserver"
    assert project["source_expansion"]["authentication"] == "basic_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "sqlserver"
    assert contract["source"]["auth"]["password"] == "{{ secret:fabric/sqlserver-admin-password }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_sqlserver_jdbc_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((SQLSERVER_JDBC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((SQLSERVER_JDBC_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = SQLSERVER_JDBC_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "spark.read.format('jdbc').options(**_cf_jdbc_options).load()" in notebook
    assert "'driver': 'com.microsoft.sqlserver.jdbc.SQLServerDriver'" in notebook
    assert "_cf_resolve_secret('fabric', 'sqlserver-admin-password')" in notebook
    assert "{{ secret:fabric/sqlserver-admin-password }}" not in notebook
    assert "'password': '" not in notebook
    compile(notebook, "fabric_sqlserver_jdbc_source_expansion.fabric.notebook.py", "exec")


def test_fabric_sqlserver_jdbc_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(SQLSERVER_JDBC_PROJECT / "contracts" / "02_sqlserver_jdbc_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.sqlserver_jdbc_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_sqlserver_jdbc_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((SQLSERVER_JDBC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-sqlserver-jdbc-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "jdbc_sqlserver"
    assert manifest["authentication"] == "basic_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-sqlserver-jdbc/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_sql_database"
    assert manifest["source_infrastructure"]["firewall"]["local_seed_rule_removed"] is True
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["secret_reference"] == "{{ secret:fabric/sqlserver-admin-password }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_postgres_jdbc_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((POSTGRES_JDBC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(POSTGRES_JDBC_PROJECT / "contracts" / "01_postgres_jdbc_orders").contract
    environment = yaml.safe_load((POSTGRES_JDBC_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))

    assert project["source_expansion"]["source_family"] == "jdbc_postgres"
    assert project["source_expansion"]["authentication"] == "basic_key_vault_placeholders"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "postgres"
    assert contract["source"]["url"] == "{{ secret:fabric/fabric-postgres-jdbc-url }}"
    assert contract["source"]["auth"]["username"] == "{{ secret:fabric/fabric-postgres-user }}"
    assert contract["source"]["auth"]["password"] == "{{ secret:fabric/fabric-postgres-password }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_postgres_jdbc_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((POSTGRES_JDBC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((POSTGRES_JDBC_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = POSTGRES_JDBC_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "spark.read.format('jdbc').options(**_cf_jdbc_options).load()" in notebook
    assert "'driver': 'org.postgresql.Driver'" in notebook
    assert "_cf_resolve_secret('fabric', 'fabric-postgres-jdbc-url')" in notebook
    assert "_cf_resolve_secret('fabric', 'fabric-postgres-user')" in notebook
    assert "_cf_resolve_secret('fabric', 'fabric-postgres-password')" in notebook
    assert "{{ secret:fabric/" not in notebook
    assert review["source_redacted"]["auth"]["password"] == "***REDACTED***"
    compile(notebook, "fabric_postgres_jdbc_source_expansion.fabric.notebook.py", "exec")


def test_fabric_postgres_jdbc_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(POSTGRES_JDBC_PROJECT / "contracts" / "02_postgres_jdbc_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.postgres_jdbc_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_postgres_jdbc_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((POSTGRES_JDBC_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-postgres-jdbc-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "jdbc_postgres"
    assert manifest["authentication"] == "basic_key_vault_placeholders"
    assert manifest["project"] == "examples/source-expansion/fabric-postgres-jdbc/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "postgresql_compatible"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["jdbc_url_secret_reference"] == "{{ secret:fabric/fabric-postgres-jdbc-url }}"
    assert manifest["contract_source"]["username_secret_reference"] == "{{ secret:fabric/fabric-postgres-user }}"
    assert manifest["contract_source"]["password_secret_reference"] == "{{ secret:fabric/fabric-postgres-password }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["contract_source"]["driver"] == "org.postgresql.Driver"
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_azure_blob_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((AZURE_BLOB_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(AZURE_BLOB_PROJECT / "contracts" / "01_azure_blob_orders").contract

    assert project["source_expansion"]["source_family"] == "azure_blob"
    assert project["source_expansion"]["authentication"] == "public_blob"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "azure_blob"
    assert contract["source"]["path"].startswith("https://cffabricf11obj65687.blob.core.windows.net/")
    assert contract["extensions"]["fabric"]["source_runtime_path"].startswith("wasbs://cf-fabric-f11@cffabricf11obj65687.blob.core.windows.net/")


def test_fabric_azure_blob_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((AZURE_BLOB_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((AZURE_BLOB_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8"))
    contract_path = AZURE_BLOB_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "wasbs://cf-fabric-f11@cffabricf11obj65687.blob.core.windows.net/object-storage/orders.csv" in notebook
    assert '.load("https://cffabricf11obj65687.blob.core.windows.net/cf-fabric-f11/object-storage/orders.csv")' not in notebook
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    compile(notebook, "fabric_azure_blob_source_expansion.fabric.notebook.py", "exec")


def test_fabric_azure_blob_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(AZURE_BLOB_PROJECT / "contracts" / "02_azure_blob_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.azure_blob_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_azure_blob_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((AZURE_BLOB_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-azure-blob-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "azure_blob"
    assert manifest["authentication"] == "public_blob"
    assert manifest["project"] == "examples/source-expansion/fabric-azure-blob/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_blob_storage"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_private_azure_blob_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((PRIVATE_AZURE_BLOB_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        PRIVATE_AZURE_BLOB_PROJECT / "contracts" / "01_private_azure_blob_orders"
    ).contract
    environment = yaml.safe_load(
        (PRIVATE_AZURE_BLOB_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "azure_blob"
    assert project["source_expansion"]["authentication"] == "private_blob_account_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "azure_blob"
    assert contract["source"]["path"].startswith("https://cffabpriv65687.blob.core.windows.net/")
    assert contract["extensions"]["fabric"]["source_runtime_path"].startswith(
        "wasbs://cf-fabric-private@cffabpriv65687.blob.core.windows.net/"
    )
    assert (
        contract["extensions"]["fabric"]["storage_account_key_secret"]
        == "{{ secret:fabric/private-blob-storage-key }}"
    )
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_private_azure_blob_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((PRIVATE_AZURE_BLOB_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (PRIVATE_AZURE_BLOB_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = PRIVATE_AZURE_BLOB_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "def _cf_resolve_secret(scope, key):" in notebook
    assert "_cf_resolve_secret('fabric', 'private-blob-storage-key')" in notebook
    assert "spark.conf.set('fs.azure.account.key.cffabpriv65687.blob.core.windows.net'" in notebook
    assert "wasbs://cf-fabric-private@cffabpriv65687.blob.core.windows.net/object-storage/orders.csv" in notebook
    assert "{{ secret:fabric/private-blob-storage-key }}" not in notebook
    assert '.load("https://cffabpriv65687.blob.core.windows.net/cf-fabric-private/object-storage/orders.csv")' not in notebook
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    assert review["source_redacted"]["extensions"]["fabric"]["storage_account_key_secret"] == "***REDACTED***"
    compile(notebook, "fabric_private_azure_blob_source_expansion.fabric.notebook.py", "exec")


def test_fabric_private_azure_blob_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        PRIVATE_AZURE_BLOB_PROJECT / "contracts" / "02_private_azure_blob_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.private_azure_blob_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_private_azure_blob_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((PRIVATE_AZURE_BLOB_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "docs" / "reports" / "fabric-private-azure-blob-source-smoke.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "azure_blob"
    assert manifest["authentication"] == "private_blob_account_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-private-azure-blob/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_blob_storage"
    assert manifest["source_infrastructure"]["storage_account"] == "cffabpriv65687"
    assert manifest["source_infrastructure"]["public_blob_read"] is False
    assert manifest["source_infrastructure"]["public_http_status"] == 409
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert (
        manifest["contract_source"]["storage_account_key_secret_reference"]
        == "{{ secret:fabric/private-blob-storage-key }}"
    )
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_external_azure_blob_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT
        / "contracts"
        / "01_external_azure_blob_shortcut_orders"
    ).contract
    environment = yaml.safe_load(
        (EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "azure_blob_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_azure_blob"
    assert project["source_expansion"]["authentication"] == "fabric_connection_key"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    assert project["fabric_setup"]["shortcuts"][0]["target"]["azureBlobStorage"]["connectionId"] == (
        "{{ parameter:fabric.connections.azure_blob_shortcut_connection_id }}"
    )
    assert (
        environment["parameters"]["fabric"]["connections"]["azure_blob_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {
        "type": "csv",
        "path": "Files/source-expansion/external-azure-blob-shortcuts/private_blob_orders/orders.csv",
        "options": {"header": True, "inferSchema": True},
    }


def test_fabric_external_azure_blob_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "SUPPORTED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert (
        'spark.read.format("csv").option("header", "True").option("inferSchema", "True").load('
        '"Files/source-expansion/external-azure-blob-shortcuts/private_blob_orders/orders.csv")'
    ) in notebook
    assert review["status"] == "SUPPORTED"
    assert review["runtime_path"] == "Fabric Lakehouse notebook source read"
    compile(notebook, "fabric_external_azure_blob_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_external_azure_blob_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT
        / "contracts"
        / "02_external_azure_blob_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.external_azure_blob_shortcut_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_external_azure_blob_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (EXTERNAL_AZURE_BLOB_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-external-azure-blob-shortcut-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "azure_blob_shortcut"
    assert manifest["shortcut_kind"] == "external_azure_blob"
    assert manifest["authentication"] == "fabric_connection_key"
    assert manifest["project"] == "examples/source-expansion/fabric-external-azure-blob-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_blob_storage"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["azure_blob_shortcut_connection_id"]
    )
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_path"] == project["source_expansion"]["shortcut"]["read_path"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_adls_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((ADLS_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(ADLS_SHORTCUT_PROJECT / "contracts" / "01_adls_shortcut_orders").contract
    environment = yaml.safe_load(
        (ADLS_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "adls_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_adls_gen2"
    assert project["source_expansion"]["authentication"] == "fabric_connection_key"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    assert project["fabric_setup"]["shortcuts"][0]["target"]["adlsGen2"]["connectionId"] == (
        "{{ parameter:fabric.connections.adls_shortcut_connection_id }}"
    )
    assert (
        environment["parameters"]["fabric"]["connections"]["adls_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {
        "type": "csv",
        "path": "Files/source-expansion/adls-shortcuts/adls_orders/orders.csv",
        "options": {"header": True, "inferSchema": True},
    }


def test_fabric_adls_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((ADLS_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (ADLS_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = ADLS_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "SUPPORTED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert (
        'spark.read.format("csv").option("header", "True").option("inferSchema", "True").load('
        '"Files/source-expansion/adls-shortcuts/adls_orders/orders.csv")'
    ) in notebook
    assert review["status"] == "SUPPORTED"
    assert review["runtime_path"] == "Fabric Lakehouse notebook source read"
    compile(notebook, "fabric_adls_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_adls_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        ADLS_SHORTCUT_PROJECT / "contracts" / "02_adls_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.adls_shortcut_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_adls_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((ADLS_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (ADLS_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-adls-shortcut-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "adls_shortcut"
    assert manifest["shortcut_kind"] == "external_adls_gen2"
    assert manifest["authentication"] == "fabric_connection_key"
    assert manifest["project"] == "examples/source-expansion/fabric-adls-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_data_lake_storage_gen2"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["adls_shortcut_connection_id"]
    )
    assert manifest["source_infrastructure"]["fabric_connection"]["secret_value_recorded"] is False
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_path"] == project["source_expansion"]["shortcut"]["read_path"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_gcs_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((GCS_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(GCS_SHORTCUT_PROJECT / "contracts" / "01_gcs_shortcut_orders").contract
    environment = yaml.safe_load(
        (GCS_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "gcs_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_google_cloud_storage"
    assert project["source_expansion"]["authentication"] == "fabric_connection_basic_hmac"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    assert project["fabric_setup"]["shortcuts"][0]["target"]["googleCloudStorage"]["connectionId"] == (
        "{{ parameter:fabric.connections.gcs_shortcut_connection_id }}"
    )
    assert (
        environment["parameters"]["fabric"]["connections"]["gcs_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {
        "type": "csv",
        "path": "Files/source-expansion/gcs-shortcuts/gcs_orders/orders.csv",
        "options": {"header": True, "inferSchema": True},
    }


def test_fabric_gcs_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((GCS_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (GCS_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = GCS_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "SUPPORTED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert (
        'spark.read.format("csv").option("header", "True").option("inferSchema", "True").load('
        '"Files/source-expansion/gcs-shortcuts/gcs_orders/orders.csv")'
    ) in notebook
    assert review["status"] == "SUPPORTED"
    assert review["runtime_path"] == "Fabric Lakehouse notebook source read"
    compile(notebook, "fabric_gcs_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_gcs_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(GCS_SHORTCUT_PROJECT / "contracts" / "02_gcs_shortcut_evidence_probe").contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.gcs_shortcut_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_gcs_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((GCS_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (GCS_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-gcs-shortcut-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "gcs_shortcut"
    assert manifest["shortcut_kind"] == "external_google_cloud_storage"
    assert manifest["authentication"] == "fabric_connection_basic_hmac"
    assert manifest["project"] == "examples/source-expansion/fabric-gcs-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "google_cloud_storage"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["gcs_shortcut_connection_id"]
    )
    assert manifest["source_infrastructure"]["fabric_connection"]["secret_value_recorded"] is False
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_path"] == project["source_expansion"]["shortcut"]["read_path"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_external_s3_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((EXTERNAL_S3_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        EXTERNAL_S3_SHORTCUT_PROJECT / "contracts" / "01_external_s3_shortcut_orders"
    ).contract
    environment = yaml.safe_load(
        (EXTERNAL_S3_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "s3_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_amazon_s3"
    assert project["source_expansion"]["authentication"] == "fabric_connection_basic_iam_user"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    assert project["fabric_setup"]["shortcuts"][0]["target"]["amazonS3"]["connectionId"] == (
        "{{ parameter:fabric.connections.amazon_s3_shortcut_connection_id }}"
    )
    assert (
        environment["parameters"]["fabric"]["connections"]["amazon_s3_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {
        "type": "csv",
        "path": "Files/source-expansion/external-s3-shortcuts/s3_orders/orders.csv",
        "options": {"header": True, "inferSchema": True},
    }


def test_fabric_external_s3_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((EXTERNAL_S3_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (EXTERNAL_S3_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = EXTERNAL_S3_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "SUPPORTED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert (
        'spark.read.format("csv").option("header", "True").option("inferSchema", "True").load('
        '"Files/source-expansion/external-s3-shortcuts/s3_orders/orders.csv")'
    ) in notebook
    assert review["status"] == "SUPPORTED"
    assert review["runtime_path"] == "Fabric Lakehouse notebook source read"
    compile(notebook, "fabric_external_s3_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_external_s3_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        EXTERNAL_S3_SHORTCUT_PROJECT / "contracts" / "02_external_s3_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.external_s3_shortcut_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_external_s3_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((EXTERNAL_S3_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (EXTERNAL_S3_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-external-s3-shortcut-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "s3_shortcut"
    assert manifest["shortcut_kind"] == "external_amazon_s3"
    assert manifest["authentication"] == "fabric_connection_basic_iam_user"
    assert manifest["project"] == "examples/source-expansion/fabric-external-s3-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "amazon_s3"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["amazon_s3_shortcut_connection_id"]
    )
    assert manifest["source_infrastructure"]["fabric_connection"]["secret_value_recorded"] is False
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_path"] == project["source_expansion"]["shortcut"]["read_path"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_s3_compatible_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((S3_COMPATIBLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        S3_COMPATIBLE_SHORTCUT_PROJECT / "contracts" / "01_s3_compatible_shortcut_orders"
    ).contract
    environment = yaml.safe_load(
        (S3_COMPATIBLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "s3_compatible_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_s3_compatible"
    assert project["source_expansion"]["authentication"] == "fabric_connection_basic_iam_user"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    shortcut = project["fabric_setup"]["shortcuts"][0]
    assert shortcut["target"]["s3Compatible"]["connectionId"] == (
        "{{ parameter:fabric.connections.s3_compatible_shortcut_connection_id }}"
    )
    assert shortcut["target"]["s3Compatible"]["bucket"] == "contractforge-aws-smoke-000000000000-us-east-1"
    assert (
        environment["parameters"]["fabric"]["connections"]["s3_compatible_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {
        "type": "csv",
        "path": "Files/source-expansion/s3-compatible-shortcuts/s3_compatible_orders/orders.csv",
        "options": {"header": True, "inferSchema": True},
    }


def test_fabric_s3_compatible_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((S3_COMPATIBLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (S3_COMPATIBLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = S3_COMPATIBLE_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "SUPPORTED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert (
        'spark.read.format("csv").option("header", "True").option("inferSchema", "True").load('
        '"Files/source-expansion/s3-compatible-shortcuts/s3_compatible_orders/orders.csv")'
    ) in notebook
    assert review["status"] == "SUPPORTED"
    assert review["runtime_path"] == "Fabric Lakehouse notebook source read"
    compile(notebook, "fabric_s3_compatible_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_s3_compatible_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        S3_COMPATIBLE_SHORTCUT_PROJECT / "contracts" / "02_s3_compatible_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.s3_compatible_shortcut_orders" in query
    assert "target_amount_rows" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_s3_compatible_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((S3_COMPATIBLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (S3_COMPATIBLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-s3-compatible-shortcut-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "s3_compatible_shortcut"
    assert manifest["shortcut_kind"] == "external_s3_compatible"
    assert manifest["authentication"] == "fabric_connection_basic_iam_user"
    assert manifest["project"] == "examples/source-expansion/fabric-s3-compatible-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "amazon_s3_compatible_endpoint"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["s3_compatible_shortcut_connection_id"]
    )
    assert manifest["source_infrastructure"]["fabric_connection"]["secret_value_recorded"] is False
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_path"] == project["source_expansion"]["shortcut"]["read_path"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_amount_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_iceberg_table_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        ICEBERG_TABLE_SHORTCUT_PROJECT / "contracts" / "01_iceberg_table_shortcut_orders"
    ).contract
    environment = yaml.safe_load(
        (ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "iceberg_table_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_amazon_s3_iceberg_table"
    assert project["source_expansion"]["authentication"] == "fabric_connection_basic_iam_user"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    assert project["fabric_setup"]["shortcuts"][0]["path"] == "Tables"
    assert project["fabric_setup"]["shortcuts"][0]["target"]["amazonS3"]["connectionId"] == (
        "{{ parameter:fabric.connections.amazon_s3_shortcut_connection_id }}"
    )
    assert (
        environment["parameters"]["fabric"]["connections"]["amazon_s3_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {"type": "iceberg_table", "table": "cf_fabric_iceberg_orders"}


def test_fabric_iceberg_table_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = ICEBERG_TABLE_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "Iceberg" in support["native_mapping"]
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert 'df = spark.table("cf_fabric_iceberg_orders")' in notebook
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    compile(notebook, "fabric_iceberg_table_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_iceberg_table_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        ICEBERG_TABLE_SHORTCUT_PROJECT / "contracts" / "02_iceberg_table_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.iceberg_table_shortcut_orders" in query
    assert "target_payload_rows" in query
    assert "contractforge_fabric_iceberg_20260613" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_iceberg_table_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-iceberg-table-shortcut-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "iceberg_table_shortcut"
    assert manifest["shortcut_kind"] == "external_amazon_s3_iceberg_table"
    assert manifest["authentication"] == "fabric_connection_basic_iam_user"
    assert manifest["project"] == "examples/source-expansion/fabric-iceberg-table-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "amazon_s3_iceberg_table"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["amazon_s3_shortcut_connection_id"]
    )
    assert manifest["source_infrastructure"]["fabric_connection"]["secret_value_recorded"] is False
    assert manifest["source_infrastructure"]["shortcut"]["path"] == "Tables"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_type"] == "iceberg_table"
    assert manifest["contract_source"]["source_table"] == project["source_expansion"]["shortcut"]["read_table"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_payload_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_adls_iceberg_table_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / "contracts" / "01_adls_iceberg_table_shortcut_orders"
    ).contract
    environment = yaml.safe_load(
        (ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "iceberg_table_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_adls_gen2_iceberg_table"
    assert project["source_expansion"]["authentication"] == "fabric_connection_key"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    assert project["fabric_setup"]["shortcuts"][0]["path"] == "Tables"
    assert project["fabric_setup"]["shortcuts"][0]["target"]["adlsGen2"]["connectionId"] == (
        "{{ parameter:fabric.connections.adls_shortcut_connection_id }}"
    )
    assert (
        environment["parameters"]["fabric"]["connections"]["adls_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {"type": "iceberg_table", "table": "cf_fabric_adls_iceberg_orders"}


def test_fabric_adls_iceberg_table_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "Iceberg" in support["native_mapping"]
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert 'df = spark.table("cf_fabric_adls_iceberg_orders")' in notebook
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    compile(notebook, "fabric_adls_iceberg_table_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_adls_iceberg_table_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / "contracts" / "02_adls_iceberg_table_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.adls_iceberg_table_shortcut_orders" in query
    assert "target_payload_rows" in query
    assert "contractforge_fabric_iceberg_20260613" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_adls_iceberg_table_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (ADLS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-adls-iceberg-table-shortcut-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "iceberg_table_shortcut"
    assert manifest["shortcut_kind"] == "external_adls_gen2_iceberg_table"
    assert manifest["authentication"] == "fabric_connection_key"
    assert manifest["project"] == "examples/source-expansion/fabric-adls-iceberg-table-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_data_lake_storage_gen2_iceberg_table"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["adls_shortcut_connection_id"]
    )
    assert manifest["source_infrastructure"]["fabric_connection"]["secret_value_recorded"] is False
    assert manifest["source_infrastructure"]["shortcut"]["path"] == "Tables"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_type"] == "iceberg_table"
    assert manifest["contract_source"]["source_table"] == project["source_expansion"]["shortcut"]["read_table"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_payload_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_gcs_iceberg_table_shortcut_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / "contracts" / "01_gcs_iceberg_table_shortcut_orders"
    ).contract
    environment = yaml.safe_load(
        (GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "iceberg_table_shortcut"
    assert project["source_expansion"]["shortcut_kind"] == "external_google_cloud_storage_iceberg_table"
    assert project["source_expansion"]["authentication"] == "fabric_connection_basic_hmac"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["fabric_setup"]["shortcuts"]) == 1
    assert project["fabric_setup"]["shortcuts"][0]["path"] == "Tables"
    assert project["fabric_setup"]["shortcuts"][0]["target"]["googleCloudStorage"]["connectionId"] == (
        "{{ parameter:fabric.connections.gcs_shortcut_connection_id }}"
    )
    assert (
        environment["parameters"]["fabric"]["connections"]["gcs_shortcut_connection_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert contract["source"] == {"type": "iceberg_table", "table": "cf_fabric_gcs_iceberg_orders"}


def test_fabric_gcs_iceberg_table_shortcut_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "Iceberg" in support["native_mapping"]
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert 'df = spark.table("cf_fabric_gcs_iceberg_orders")' in notebook
    assert review["status"] == "REVIEW_REQUIRED"
    assert review["renderable"] is True
    compile(notebook, "fabric_gcs_iceberg_table_shortcut_source_expansion.fabric.notebook.py", "exec")


def test_fabric_gcs_iceberg_table_shortcut_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / "contracts" / "02_gcs_iceberg_table_shortcut_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.gcs_iceberg_table_shortcut_orders" in query
    assert "target_payload_rows" in query
    assert "contractforge_fabric_iceberg_20260613" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_gcs_iceberg_table_shortcut_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (GCS_ICEBERG_TABLE_SHORTCUT_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-gcs-iceberg-table-shortcut-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "iceberg_table_shortcut"
    assert manifest["shortcut_kind"] == "external_google_cloud_storage_iceberg_table"
    assert manifest["authentication"] == "fabric_connection_basic_hmac"
    assert manifest["project"] == "examples/source-expansion/fabric-gcs-iceberg-table-shortcut/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "google_cloud_storage_iceberg_table"
    assert manifest["source_infrastructure"]["fabric_connection"]["id"] == (
        environment["parameters"]["fabric"]["connections"]["gcs_shortcut_connection_id"]
    )
    assert manifest["source_infrastructure"]["fabric_connection"]["secret_value_recorded"] is False
    assert manifest["source_infrastructure"]["shortcut"]["path"] == "Tables"
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["source_type"] == "iceberg_table"
    assert manifest["contract_source"]["source_table"] == project["source_expansion"]["shortcut"]["read_table"]
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_payload_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_confluent_kafka_bounded_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((CONFLUENT_KAFKA_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        CONFLUENT_KAFKA_PROJECT / "contracts" / "01_confluent_kafka_bounded_orders"
    ).contract
    environment = yaml.safe_load(
        (CONFLUENT_KAFKA_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "confluent_kafka_bounded"
    assert project["source_expansion"]["authentication"] == "sasl_plain_key_vault_placeholder"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "kafka_bounded"
    assert contract["source"]["system"] == "confluent_cloud"
    assert contract["source"]["bootstrap_servers"] == "pkc-redacted.region.confluent.cloud:9092"
    assert contract["source"]["topic"] == "cf-fabric-orders"
    assert contract["source"]["options"]["kafka.sasl.jaas.config"] == "{{ secret:fabric/fabric-confluent-kafka-jaas-config }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_confluent_kafka_bounded_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((CONFLUENT_KAFKA_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (CONFLUENT_KAFKA_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = CONFLUENT_KAFKA_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert ".format('kafka')" in notebook
    assert ".option('kafka.bootstrap.servers', 'pkc-redacted.region.confluent.cloud:9092')" in notebook
    assert ".option('subscribe', 'cf-fabric-orders')" in notebook
    assert "_cf_resolve_secret('fabric', 'fabric-confluent-kafka-jaas-config')" in notebook
    assert "{{ secret:fabric/" not in notebook
    assert "F.from_json(F.col('value').cast('string')" in notebook
    assert "payload.order_id" in notebook
    assert review["source_redacted"]["options"]["kafka.sasl.jaas.config"] == "***REDACTED***"
    compile(notebook, "fabric_confluent_kafka_bounded_source_expansion.fabric.notebook.py", "exec")


def test_fabric_confluent_kafka_bounded_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        CONFLUENT_KAFKA_PROJECT / "contracts" / "02_confluent_kafka_bounded_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.confluent_kafka_bounded_orders" in query
    assert "target_payload_rows" in query
    assert "contractforge_fabric_confluent" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_confluent_kafka_bounded_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((CONFLUENT_KAFKA_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-confluent-kafka-bounded-source-smoke.json").read_text(encoding="utf-8")
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "confluent_kafka_bounded"
    assert manifest["authentication"] == "sasl_plain_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-confluent-kafka-bounded/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "confluent_cloud_kafka"
    assert manifest["source_infrastructure"]["cluster_id"] == "lkc-dokqkxo"
    assert manifest["source_infrastructure"]["topic"] == "cf-fabric-orders"
    assert manifest["source_infrastructure"]["cluster_scoped_key_created"] is True
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["jaas_secret_reference"] == "{{ secret:fabric/fabric-confluent-kafka-jaas-config }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_payload_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_confluent_kafka_available_now_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / "contracts" / "01_confluent_kafka_available_now_orders"
    ).contract
    environment = yaml.safe_load(
        (CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "confluent_kafka_available_now"
    assert project["source_expansion"]["authentication"] == "sasl_plain_key_vault_placeholder"
    assert project["source_expansion"]["trigger"] == "available_now"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "kafka_available_now"
    assert contract["source"]["system"] == "confluent_cloud"
    assert contract["source"]["checkpoint_location"] == project["source_expansion"]["checkpoint_location"]
    assert contract["source"]["options"]["kafka.sasl.jaas.config"] == "{{ secret:fabric/fabric-confluent-kafka-jaas-config }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_confluent_kafka_available_now_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "spark.readStream" in notebook
    assert ".format('kafka')" in notebook
    assert ".trigger(availableNow=True)" in notebook
    assert ".option('checkpointLocation', _cf_available_now_checkpoint)" in notebook
    assert ".option('path', _cf_available_now_materialized_path)" in notebook
    assert "spark.read.format('delta').load(_cf_available_now_materialized_path)" in notebook
    assert "_cf_resolve_secret('fabric', 'fabric-confluent-kafka-jaas-config')" in notebook
    assert "{{ secret:fabric/" not in notebook
    assert "F.from_json(F.col('value').cast('string')" in notebook
    assert "payload.order_id" in notebook
    assert review["source_redacted"]["options"]["kafka.sasl.jaas.config"] == "***REDACTED***"
    compile(notebook, "fabric_confluent_kafka_available_now_source_expansion.fabric.notebook.py", "exec")


def test_fabric_confluent_kafka_available_now_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / "contracts" / "02_confluent_kafka_available_now_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.confluent_kafka_available_now_orders" in query
    assert "target_payload_rows" in query
    assert "contractforge_fabric_available_now" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_confluent_kafka_available_now_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((CONFLUENT_KAFKA_AVAILABLE_NOW_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-confluent-kafka-available-now-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "confluent_kafka_available_now"
    assert manifest["authentication"] == "sasl_plain_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-confluent-kafka-available-now/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "confluent_cloud_kafka"
    assert manifest["source_infrastructure"]["topic"] == "cf-fabric-orders"
    assert manifest["source_infrastructure"]["checkpoint_location"] == project["source_expansion"]["checkpoint_location"]
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["jaas_secret_reference"] == "{{ secret:fabric/fabric-confluent-kafka-jaas-config }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_payload_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]


def test_fabric_eventhubs_kafka_available_now_source_expansion_project_is_contract_only() -> None:
    project = yaml.safe_load((EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    contract = load_contract_bundle(
        EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / "contracts" / "01_eventhubs_kafka_available_now_orders"
    ).contract
    environment = yaml.safe_load(
        (EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )

    assert project["source_expansion"]["source_family"] == "eventhubs_kafka_available_now"
    assert project["source_expansion"]["authentication"] == "sasl_plain_key_vault_placeholder"
    assert project["source_expansion"]["trigger"] == "available_now"
    assert project["source_expansion"]["expected_probe_checks"] == 6
    assert len(project["execution_order"]) == 2
    assert contract["source"]["type"] == "kafka_available_now"
    assert contract["source"]["system"] == "azure_eventhubs"
    assert contract["source"]["bootstrap_servers"] == "cfstreameh0601135444.servicebus.windows.net:9093"
    assert contract["source"]["topic"] == "cf-orders"
    assert contract["source"]["checkpoint_location"] == project["source_expansion"]["checkpoint_location"]
    assert contract["source"]["options"]["kafka.sasl.jaas.config"] == "{{ secret:fabric/fabric-eventhubs-kafka-jaas-config }}"
    assert environment["secrets"]["scopes"]["fabric"] == "https://cffabricf11kv.vault.azure.net/"


def test_fabric_eventhubs_kafka_available_now_source_expansion_plans_and_renders_notebook() -> None:
    project = yaml.safe_load((EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load(
        (EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / project["environments"]["fabric"]).read_text(encoding="utf-8")
    )
    contract_path = EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / project["execution_order"][0]["contracts"]["fabric"]
    contract = load_contract_bundle(contract_path.with_name(contract_path.name.removesuffix(".ingestion.yaml"))).contract

    support = fabric_source_support(contract["source"])
    planning = plan_fabric_contract(contract, environment=environment)
    artifacts = render_fabric_contract(contract, environment=environment).artifacts
    notebook = next(body for name, body in artifacts.items() if name.endswith(".fabric.notebook.py"))
    review = json.loads(next(body for name, body in artifacts.items() if name.endswith(".fabric.source_review.json")))

    assert support["status"] == "REVIEW_REQUIRED"
    assert support["renderable"] is True
    assert "Event Hubs Kafka-compatible available-now" in support["native_mapping"]
    assert planning.status == "SUPPORTED_WITH_WARNINGS"
    assert not planning.blockers
    assert "spark.readStream" in notebook
    assert ".format('kafka')" in notebook
    assert ".option('kafka.bootstrap.servers', 'cfstreameh0601135444.servicebus.windows.net:9093')" in notebook
    assert ".trigger(availableNow=True)" in notebook
    assert "spark.read.format('delta').load(_cf_available_now_materialized_path)" in notebook
    assert "_cf_resolve_secret('fabric', 'fabric-eventhubs-kafka-jaas-config')" in notebook
    assert "{{ secret:fabric/" not in notebook
    assert "payload.event_id" in notebook
    assert review["source_redacted"]["options"]["kafka.sasl.jaas.config"] == "***REDACTED***"
    compile(notebook, "fabric_eventhubs_kafka_available_now_source_expansion.fabric.notebook.py", "exec")


def test_fabric_eventhubs_kafka_available_now_source_expansion_probe_checks_control_tables() -> None:
    contract = load_contract_bundle(
        EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / "contracts" / "02_eventhubs_kafka_available_now_evidence_probe"
    ).contract
    query = contract["source"]["query"]

    assert "cf_fabric_source_expansion.eventhubs_kafka_available_now_orders" in query
    assert "target_payload_rows" in query
    assert "contractforge_fabric_eventhubs_available_now_20260613" in query
    assert "contractforge.ctrl_ingestion_runs" in query
    assert "contractforge.ctrl_ingestion_quality" in query
    assert "contractforge.ctrl_ingestion_schema_changes" in query
    assert "contractforge.ctrl_ingestion_metadata" in query
    assert contract["quality_rules"]["min_rows"] == 6


def test_fabric_eventhubs_kafka_available_now_source_expansion_evidence_manifest_matches_project() -> None:
    project = yaml.safe_load((EVENTHUBS_KAFKA_AVAILABLE_NOW_PROJECT / "project.yaml").read_text(encoding="utf-8"))
    manifest = json.loads(
        (ROOT / "docs" / "reports" / "fabric-eventhubs-kafka-available-now-source-smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["status"] == "SUCCEEDED"
    assert manifest["source_family"] == "eventhubs_kafka_available_now"
    assert manifest["authentication"] == "sasl_plain_key_vault_placeholder"
    assert manifest["project"] == "examples/source-expansion/fabric-eventhubs-kafka-available-now/project.yaml"
    assert manifest["source_infrastructure"]["provider"] == "azure_eventhubs_kafka_endpoint"
    assert manifest["source_infrastructure"]["event_hub"] == "cf-orders"
    assert manifest["source_infrastructure"]["checkpoint_location"] == project["source_expansion"]["checkpoint_location"]
    assert manifest["source_infrastructure"]["secret_value_recorded"] is False
    assert manifest["contract_source"]["workaround_code_used"] is False
    assert manifest["contract_source"]["jaas_secret_reference"] == "{{ secret:fabric/fabric-eventhubs-kafka-jaas-config }}"
    assert manifest["contract_source"]["secret_value_recorded"] is False
    assert manifest["result_summary"]["submitted_steps"] == len(project["execution_order"])
    assert manifest["result_summary"]["fabric_job_status_completed"] == len(project["execution_order"])
    assert manifest["result_summary"]["evidence_probe_checks"] == project["source_expansion"]["expected_probe_checks"]
    assert {step["name"] for step in manifest["steps"]} == {step["name"] for step in project["execution_order"]}
    assert manifest["coverage"]["probe_checks"] == [
        "target_rows",
        "target_payload_rows",
        "run_rows",
        "quality_rows",
        "schema_rows",
        "source_metadata_rows",
    ]
