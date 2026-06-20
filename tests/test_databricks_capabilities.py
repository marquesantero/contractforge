from contractforge_databricks.capabilities import evaluate_databricks_capabilities, to_core_capabilities, uc_capability_issues
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.runtime import detect_databricks_capabilities


def test_capabilities_classify_serverless_databricks_runtime() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_version="4.1.0",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    assert caps.runtime_kind == "databricks_serverless"
    assert caps.supports("databricks_runtime")
    assert caps.supports("serverless_runtime")
    assert caps.supports("unity_catalog_table")
    assert caps.supports("uc_table_tags")
    assert caps.supports("uc_grants")
    assert caps.supports("uc_row_filters")
    assert caps.supports("autoloader_cloudfiles")
    assert caps.status("databricks_connections") == "unknown"
    assert caps.status("lakeflow_declarative_pipelines") == "unknown"
    assert caps.status("lakeflow_auto_cdc") == "unknown"
    assert "CDC source semantics" in caps.capabilities["lakeflow_auto_cdc"].requires
    assert caps.as_dict()["spark_version"] == "4.1.0"


def test_capabilities_classify_serverless_from_job_metadata_without_cluster() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        spark_conf={"spark.databricks.job.id": "42", "spark.databricks.job.runId": "99"},
    )

    assert caps.runtime_kind == "databricks_serverless"
    assert caps.supports("serverless_runtime")


def test_capabilities_do_not_misclassify_classic_cluster_job_as_serverless() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        spark_conf={
            "spark.databricks.job.id": "42",
            "spark.databricks.job.runId": "99",
            "spark.databricks.clusterUsageTags.clusterId": "cluster-1",
        },
    )

    assert caps.runtime_kind == "databricks_classic"
    assert not caps.supports("serverless_runtime")


def test_capabilities_classify_serverless_from_environment_evidence() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        environment={"DATABRICKS_ENV_VERSION": "serverless-2026"},
    )

    assert caps.runtime_kind == "databricks_serverless"
    assert any(item.source == "environment" for item in caps.capabilities["databricks_runtime"].evidence)


def test_detect_databricks_capabilities_collects_environment_evidence(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_ENV_VERSION", "serverless-2026")

    caps = detect_databricks_capabilities(target_table="main.silver.orders")

    assert caps.runtime_kind == "databricks_serverless"
    assert any(item.source == "environment" for item in caps.capabilities["databricks_runtime"].evidence)


def test_databricks_environment_accepts_runtime_type_alias() -> None:
    env = DatabricksEnvironment.from_contract(
        {
            "name": "dev",
            "adapter": "databricks",
            "runtime": {"runtime_type": "serverless"},
            "evidence": {"catalog": "main", "schema": "ops"},
        }
    )

    assert env.runtime_kind == "serverless"


def test_databricks_environment_accepts_adapter_runtime_parameter_fallback() -> None:
    env = DatabricksEnvironment.from_contract(
        {
            "name": "dev",
            "adapter": "databricks",
            "parameters": {"databricks": {"runtime": "classic_existing_cluster"}},
        }
    )

    assert env.runtime_kind == "classic_existing_cluster"


def test_capabilities_remain_conservative_outside_databricks() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="classic",
        spark_conf={},
    )

    assert caps.runtime_kind == "spark"
    assert not caps.supports("databricks_runtime")
    assert caps.supports("unity_catalog_table")
    assert caps.status("uc_row_filters") == "unknown"
    assert caps.status("autoloader_cloudfiles") == "unsupported"
    assert caps.status("lakeflow_auto_cdc") == "unsupported"
    assert any(item.name == "databricks_runtime" for item in caps.unsupported())
    assert any(item.name == "uc_table_tags" for item in caps.unknown())


def test_capabilities_classify_classic_existing_cluster_runtime() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="classic_existing_cluster",
    )
    core_caps = to_core_capabilities(caps)

    assert caps.runtime_kind == "databricks_classic"
    assert core_caps.supports_append
    assert core_caps.supports_overwrite
    assert core_caps.evidence_stores == ("delta_control_tables",)


def test_capabilities_do_not_claim_uc_sql_support_for_two_part_target() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    assert caps.runtime_kind == "databricks_serverless"
    assert not caps.supports("unity_catalog_table")
    assert caps.status("uc_table_tags") == "unsupported"
    assert caps.status("uc_external_locations") == "unknown"
    assert "Workspace configuration and permissions were not probed" in caps.capabilities["uc_external_locations"].reason


def test_mapping_to_core_capabilities() -> None:
    caps = evaluate_databricks_capabilities(
        target_table="main.silver.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )

    core_caps = to_core_capabilities(caps)

    assert core_caps.platform == "databricks"
    assert core_caps.supports_append
    assert core_caps.supports_merge
    assert core_caps.supports_scd2
    assert core_caps.supports_row_filters
    assert core_caps.supports_expression_quality
    assert core_caps.supports_shape
    assert core_caps.supports_transform
    assert core_caps.evidence_stores == ("delta_control_tables",)


def test_uc_capability_issues_match_contractforge_helper() -> None:
    issues = uc_capability_issues(
        "silver.orders",
        [("row_filters", "table", "orders", "error"), ("column_masks", "column", "email", "warn")],
    )

    assert [item["capability"] for item in issues] == ["uc_row_filters", "uc_column_masks"]
    assert issues[0]["severity"] == "error"
    assert "three-part Unity Catalog table" in issues[0]["message"]

    assert (
        uc_capability_issues(
            "main.silver.orders",
            [("row_filters", "table", "orders", "error")],
            capabilities=evaluate_databricks_capabilities(
                target_table="main.silver.orders",
                runtime_type="serverless",
                spark_conf={"spark.databricks.serverless.enabled": "true"},
            ),
        )
        == []
    )
