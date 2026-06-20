"""Real-world USGS REST medallion contracts shared by all stable adapters."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from contractforge_aws import plan_aws_contract, render_aws_contract
from contractforge_databricks import plan_databricks_contract, render_databricks_contract
from contractforge_core.contracts import load_contract_bundle
from contractforge_fabric import plan_fabric_contract, render_fabric_contract
from contractforge_gcp import plan_gcp_contract, render_gcp_contract
from contractforge_snowflake import deploy_snowflake_project, plan_snowflake_contract, render_snowflake_contract, run_snowflake_contract
from tools.rest_medallion.usgs import platform_contracts, portability_report, write_project_contracts

PROJECT = Path("examples/real-world/usgs-earthquake-rest-medallion")


def test_usgs_rest_medallion_portability_report_marks_intent_equal() -> None:
    report = portability_report(project_prefix="cf_usgs_rest_test")

    assert report["kind"] == "contractforge_usgs_rest_medallion_portability"
    assert len(report["steps"]) == 4
    assert all(step["portable_intent_equal"] for step in report["steps"])


def test_usgs_rest_medallion_plans_on_databricks_and_aws() -> None:
    dbx = platform_contracts("databricks", target_catalog="workspace", project_prefix="cf_usgs_rest_test")
    aws = platform_contracts(
        "aws",
        target_catalog="contractforge",
        project_prefix="cf_usgs_rest_test",
        aws_warehouse="s3://contractforge-test/warehouse/",
    )

    for step in dbx:
        result = plan_databricks_contract(
            step.contract,
            runtime_type="serverless",
            spark_conf={"spark.databricks.serverless.enabled": "true"},
        )
        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}
    for step in aws:
        result = plan_aws_contract(step.contract)
        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}


def test_usgs_rest_medallion_renders_runtime_artifacts() -> None:
    dbx = platform_contracts("databricks", target_catalog="workspace", project_prefix="cf_usgs_rest_test")
    aws = platform_contracts(
        "aws",
        target_catalog="contractforge",
        project_prefix="cf_usgs_rest_test",
        aws_warehouse="s3://contractforge-test/warehouse/",
    )

    dbx_bronze = render_databricks_contract(dbx[0].contract, runtime_type="serverless").artifacts
    aws_bronze = render_aws_contract(aws[0].contract).artifacts
    aws_silver = render_aws_contract(aws[1].contract).artifacts

    assert any(name.endswith(".source_rest_api_review.json") for name in dbx_bronze)
    assert any(name.endswith(".databricks.yml") for name in dbx_bronze)
    assert any(name.endswith(".glue_job.py") for name in aws_bronze)
    assert any(name.endswith(".glue_job_definition.json") for name in aws_bronze)
    assert "read_rest_api_records" in next(body for name, body in aws_bronze.items() if name.endswith(".glue_job.py"))
    assert "payload.features" in next(body for name, body in aws_silver.items() if name.endswith(".glue_job.py"))


def test_write_usgs_rest_medallion_project_contracts(tmp_path) -> None:
    written = write_project_contracts(
        tmp_path,
        "aws",
        target_catalog="contractforge",
        project_prefix="cf_usgs_rest_test",
        aws_warehouse="s3://contractforge-test/warehouse/",
    )

    assert set(written) == {
        "bronze_usgs_geojson",
        "silver_usgs_events",
        "gold_usgs_daily_summary",
        "gold_usgs_magnitude_bands",
    }
    for path in written.values():
        assert path.endswith(".ingestion.json")


def test_usgs_rest_medallion_yaml_project_loads_split_bundles() -> None:
    ingestion_files = sorted((PROJECT / "contracts").glob("*/*/*/*.ingestion.yaml"))

    assert len(ingestion_files) == 20
    for path in ingestion_files:
        bundle = load_contract_bundle(path)
        assert bundle.semantic.target.name
        assert bundle.metadata["paths"]["ingestion"].endswith(".ingestion.yaml")
        assert "annotations" in bundle.contract
        assert "operations" in bundle.contract


def test_usgs_rest_medallion_project_yaml_declares_execution_order() -> None:
    project = _load_yaml(PROJECT / "project.yaml")

    assert list(project["environments"]) == ["databricks", "aws", "snowflake", "fabric", "gcp"]
    assert [step["name"] for step in project["execution_order"]] == [
        "bronze_usgs_geojson",
        "silver_usgs_events",
        "gold_usgs_daily_summary",
        "gold_usgs_magnitude_bands",
    ]
    for step in project["execution_order"]:
        assert set(step["contracts"]) == {"databricks", "aws", "snowflake", "fabric", "gcp"}
        for platform, relative_path in step["contracts"].items():
            assert platform in {"databricks", "aws", "snowflake", "fabric", "gcp"}
            assert (PROJECT / relative_path).exists()


def test_usgs_rest_medallion_bronze_uses_same_rest_api_source_on_all_adapters() -> None:
    project = _load_yaml(PROJECT / "project.yaml")
    bronze = project["execution_order"][0]["contracts"]
    sources = {
        platform: load_contract_bundle(PROJECT / relative_path).contract["source"]
        for platform, relative_path in bronze.items()
    }

    assert set(sources) == {"databricks", "aws", "snowflake", "fabric", "gcp"}
    assert sources["databricks"] == sources["aws"] == sources["snowflake"] == sources["fabric"] == sources["gcp"]
    assert sources["gcp"]["type"] == "rest_api"
    assert sources["gcp"]["response"]["mode"] == "raw"


def test_usgs_rest_medallion_yaml_project_renders_on_all_adapters() -> None:
    databricks_env = _load_yaml(PROJECT / "environments/databricks.environment.yaml")
    aws_env = _load_yaml(PROJECT / "environments/aws.environment.yaml")
    snowflake_env = _load_yaml(PROJECT / "environments/snowflake.environment.yaml")
    fabric_env = _load_yaml(PROJECT / "environments/fabric.environment.yaml")
    gcp_env = _load_yaml(PROJECT / "environments/gcp.environment.yaml")
    databricks_contract = load_contract_bundle(
        PROJECT / "contracts/databricks/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml"
    ).contract
    aws_contract = load_contract_bundle(
        PROJECT / "contracts/aws/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml"
    ).contract
    snowflake_contract = load_contract_bundle(
        PROJECT / "contracts/snowflake/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml"
    ).contract
    fabric_contract = load_contract_bundle(
        PROJECT / "contracts/fabric/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml"
    ).contract
    gcp_contract = load_contract_bundle(
        PROJECT / "contracts/gcp/bronze/bronze_usgs_geojson/bronze_usgs_geojson.ingestion.yaml"
    ).contract

    dbx_artifacts = render_databricks_contract(
        databricks_contract,
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
        environment=databricks_env,
    ).artifacts
    aws_artifacts = render_aws_contract(aws_contract, environment=aws_env).artifacts
    snowflake_artifacts = render_snowflake_contract(snowflake_contract, environment=snowflake_env).artifacts
    fabric_artifacts = render_fabric_contract(fabric_contract, environment=fabric_env).artifacts
    gcp_artifacts = render_gcp_contract(gcp_contract, environment=gcp_env).artifacts

    assert any(name.endswith(".source_rest_api_review.json") for name in dbx_artifacts)
    assert any(name.endswith(".glue_job.py") for name in aws_artifacts)
    assert any(name.endswith(".contract.json") for name in snowflake_artifacts)
    assert any(name.endswith(".fabric.notebook.py") for name in fabric_artifacts)
    assert any(name.endswith(".gcp.source_materialization.json") for name in gcp_artifacts)


def test_usgs_rest_medallion_gcp_contracts_plan_and_render_without_workarounds() -> None:
    project = _load_yaml(PROJECT / "project.yaml")
    environment = _load_yaml(PROJECT / "environments/gcp.environment.yaml")

    for step in project["execution_order"]:
        contract = load_contract_bundle(PROJECT / step["contracts"]["gcp"]).contract
        result = plan_gcp_contract(contract, environment=environment)
        artifacts = render_gcp_contract(contract, environment=environment).artifacts

        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}
        assert not result.blockers
        assert any(name.endswith(".gcp.write.sql") for name in artifacts)
        assert "extensions" not in contract or "databricks" not in contract.get("extensions", {})

    bronze = load_contract_bundle(PROJECT / project["execution_order"][0]["contracts"]["gcp"]).contract
    assert bronze["source"]["type"] == "rest_api"
    silver = load_contract_bundle(PROJECT / project["execution_order"][1]["contracts"]["gcp"]).contract
    assert "JSON_QUERY_ARRAY(payload, '$.features')" in silver["source"]["query"]
    gold_daily = load_contract_bundle(PROJECT / project["execution_order"][2]["contracts"]["gcp"]).contract
    assert "FROM `midyear-system-499521-p3.contractforge_gcp_usgs_rest_silver.s_usgs_earthquake_events`" in gold_daily["source"]["query"]


def test_usgs_rest_medallion_fabric_contracts_plan_and_render_without_workarounds() -> None:
    project = _load_yaml(PROJECT / "project.yaml")
    environment = _load_yaml(PROJECT / "environments/fabric.environment.yaml")

    for step in project["execution_order"]:
        contract = load_contract_bundle(PROJECT / step["contracts"]["fabric"]).contract
        result = plan_fabric_contract(contract, environment=environment)
        artifacts = render_fabric_contract(contract, environment=environment).artifacts

        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}
        assert not result.blockers
        assert any(name.endswith(".fabric.notebook.py") for name in artifacts)
        assert "extensions" not in contract or "databricks" not in contract.get("extensions", {})

    silver = load_contract_bundle(PROJECT / project["execution_order"][1]["contracts"]["fabric"]).contract
    assert silver["source"]["table"] == "cf_usgs_rest_bronze.b_usgs_earthquake_geojson"
    gold_daily = load_contract_bundle(PROJECT / project["execution_order"][2]["contracts"]["fabric"]).contract
    assert "FROM cf_usgs_rest_silver.s_usgs_earthquake_events" in gold_daily["source"]["query"]


def test_usgs_rest_medallion_snowflake_project_dry_run_is_bronze_to_gold() -> None:
    result = deploy_snowflake_project(PROJECT / "project.yaml", dry_run=True, summary_only=True)

    assert [step.name for step in result.steps] == [
        "bronze_usgs_geojson",
        "silver_usgs_events",
        "gold_usgs_daily_summary",
        "gold_usgs_magnitude_bands",
    ]
    assert all(not step.blocker_codes for step in result.steps)
    assert result.steps[0].planning_status == "SUPPORTED"
    assert all(step.planning_status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"} for step in result.steps)
    assert "deployment/snowflake_runtime_procedure.sql" in result.deployment_artifacts
    assert "deployment/snowflake_task_graph.sql" in result.deployment_artifacts
    assert 'EXTERNAL_ACCESS_INTEGRATIONS = ("CF_USGS_REST_ACCESS")' in result.deployment_artifacts["deployment/snowflake_runtime_procedure.sql"]


def test_usgs_rest_medallion_snowflake_runtime_runs_declared_bronze_to_gold_contracts(tmp_path, monkeypatch) -> None:
    from contractforge_snowflake.sources import rest_api as rest_source

    monkeypatch.setattr(
        rest_source,
        "read_rest_api_records",
        lambda _source: [{"raw_response": '{"type":"FeatureCollection","metadata":{"count":0},"features":[]}', "response_page_number": 1}],
    )
    project = _load_yaml(PROJECT / "project.yaml")
    environment = _load_yaml(PROJECT / "environments/snowflake.environment.yaml")
    environment_path = tmp_path / "snowflake.environment.json"
    environment_path.write_text(json.dumps(environment), encoding="utf-8")
    session = _SnowflakeExecutingSession()

    results = []
    for step in project["execution_order"]:
        contract = load_contract_bundle(PROJECT / step["contracts"]["snowflake"]).contract
        contract_path = tmp_path / f"{step['name']}.contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        results.append(
            run_snowflake_contract(
                contract_uri=str(contract_path),
                environment_uri=str(environment_path),
                session=session,
                run_id=f"test-{step['name']}",
            )
        )

    assert [result["status"] for result in results] == ["SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS"]
    assert any("CREATE OR REPLACE TEMPORARY TABLE" in command and "CF_REST_CONTRACTFORGE_TEST_DB_PUBLIC_CF_USGS_REST_BRONZE" in command for command in session.commands)
    assert any("INSERT INTO" in command and "FeatureCollection" in command for command in session.commands)
    assert any("CF_USGS_REST_BRONZE" in command for command in session.commands)
    assert any("CF_USGS_REST_SILVER" in command for command in session.commands)
    assert any("CF_USGS_REST_GOLD_DAILY" in command for command in session.commands)
    assert any("CF_USGS_REST_GOLD_BANDS" in command for command in session.commands)
    assert not any("CF_USGS_GEOJSON_DATA" in command or "frozen" in command for command in session.commands)


def test_usgs_rest_medallion_snowflake_contracts_plan_without_source_workarounds() -> None:
    project = _load_yaml(PROJECT / "project.yaml")
    environment = _load_yaml(PROJECT / "environments/snowflake.environment.yaml")

    for step in project["execution_order"]:
        contract = load_contract_bundle(PROJECT / step["contracts"]["snowflake"]).contract
        result = plan_snowflake_contract(contract, environment=environment)
        assert result.status in {"SUPPORTED", "SUPPORTED_WITH_WARNINGS"}
        assert not result.blockers
    bronze = load_contract_bundle(PROJECT / project["execution_order"][0]["contracts"]["snowflake"]).contract
    assert bronze["source"]["type"] == "rest_api"
    assert "CF_USGS_GEOJSON_DATA" not in yaml.safe_dump(bronze)


def _load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


class _SnowflakeExecutingSession:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def sql(self, command: str):
        self.commands.append(command)
        if command.startswith("SELECT CURRENT_WAREHOUSE()"):
            return _SnowflakeResult([("COMPUTE_WH", "ROLE", "DB", "PUBLIC", "10.19")])
        if "INFORMATION_SCHEMA.COLUMNS" in command:
            return _SnowflakeResult([])
        if " LIMIT 0" in command:
            return _SnowflakeResult([], schema=_SnowflakeSchema(_USGS_COLUMNS))
        if command.startswith("SELECT COUNT(*)") and (" HAVING COUNT(*) > 1" in command or "\nWHERE " in command):
            return _SnowflakeResult([(0,)])
        if command.startswith("SELECT COUNT(*)"):
            return _SnowflakeResult([(1,)])
        if command.startswith("SELECT IFF("):
            return _SnowflakeResult([(0,)])
        return _SnowflakeResult([])


class _SnowflakeResult:
    query_id = "qid"
    rowcount = None

    def __init__(self, rows, *, schema=None):
        self._rows = rows
        self.schema = schema

    def collect(self):
        return self._rows


class _SnowflakeSchema:
    def __init__(self, names):
        self.names = names


_USGS_COLUMNS = (
    "raw_response",
    "response_page_number",
    "feed_generated_epoch_ms",
    "feed_title",
    "feed_event_count",
    "feed_api_version",
    "feed_bbox",
    "earthquake_id",
    "geojson_feature_type",
    "event_title",
    "place",
    "magnitude",
    "magnitude_type",
    "event_epoch_ms",
    "updated_epoch_ms",
    "event_status",
    "event_type",
    "alert_level",
    "tsunami_flag",
    "significance",
    "network",
    "network_event_code",
    "event_url",
    "detail_url",
    "felt_reports",
    "community_intensity",
    "instrumental_intensity",
    "geometry_type",
    "coordinates",
    "longitude",
    "latitude",
    "depth_km",
    "event_time",
    "updated_at",
    "feed_generated_at",
    "event_date",
    "magnitude_band",
    "is_tsunami_related",
    "normalized_at_utc",
    "earthquake_count",
    "tsunami_related_count",
    "avg_magnitude",
    "max_magnitude",
    "avg_depth_km",
    "reporting_networks",
    "last_event_update_at",
    "computed_at_utc",
    "event_count",
    "min_magnitude",
    "first_event_time",
    "latest_event_time",
)
