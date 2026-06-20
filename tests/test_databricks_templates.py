from contractforge_databricks.templates import (
    contract_template_details,
    contract_template_files,
    list_contract_templates,
    recommend_contract_templates,
)
from contractforge_core.contracts import validate_shape_contract
from contractforge_core.contracts.source_validation import validate_source_semantics


def test_databricks_templates_cover_catalog_scenarios() -> None:
    names = set(list_contract_templates())

    assert {
        "bronze_rest_api_incremental",
        "bronze_http_file_csv_snapshot",
        "bronze_autoloader_json",
        "bronze_autoloader_available_now_json",
        "bronze_autoloader_governed_delta",
        "bronze_blob_partitioned_files",
        "bronze_object_storage_nested_json_shape",
        "bronze_object_storage_small_files",
        "silver_jdbc_scd1_upsert",
        "silver_jdbc_rds_iam_hash_diff",
        "silver_lakeflow_auto_cdc_scd1_preview",
        "silver_lakeflow_auto_cdc_scd2_preview",
        "silver_raw_json_payload_shape",
        "silver_parallel_arrays_shape",
        "silver_scd1_hash_diff",
        "silver_snapshot_soft_delete",
        "silver_scd2_history",
        "gold_full_refresh_kpi",
    } <= names


def test_databricks_template_details_and_files_are_split_contracts() -> None:
    details = contract_template_details("silver_jdbc_scd1_upsert")
    files = contract_template_files("silver_jdbc_scd1_upsert")

    assert details["category"] == "silver"
    assert details["source"] == "postgres"
    assert details["files"] == ["ingestion", "annotations", "operations", "access"]
    assert files["ingestion"]["target"]["schema"] == "curated"
    assert files["access"]["grants"][0]["principal"] == "sales-analytics"


def test_databricks_templates_are_defensive_copies() -> None:
    files = contract_template_files("gold_full_refresh_kpi")
    files["ingestion"]["target"]["table"] = "changed"

    assert contract_template_files("gold_full_refresh_kpi")["ingestion"]["target"]["table"] == "g_daily_orders"


def test_databricks_template_recommendations_find_real_patterns() -> None:
    http = recommend_contract_templates(layer="bronze", source="http_csv", pattern="csv", limit=1)
    native = recommend_contract_templates(layer="silver", pattern="lakeflow", limit=2)
    jdbc = recommend_contract_templates(layer="silver", source="jdbc", pattern="rds_iam", limit=1)

    assert http[0]["name"] == "bronze_http_file_csv_snapshot"
    assert {item["name"] for item in native} == {
        "silver_lakeflow_auto_cdc_scd1_preview",
        "silver_lakeflow_auto_cdc_scd2_preview",
    }
    assert jdbc[0]["name"] == "silver_jdbc_rds_iam_hash_diff"


def test_databricks_template_parity_ports_partitioned_files_and_hash_diff() -> None:
    bronze = contract_template_files("bronze_blob_partitioned_files")
    silver = contract_template_files("silver_scd1_hash_diff")

    assert bronze["ingestion"]["source"]["type"] == "s3"
    assert bronze["ingestion"]["source"]["read"]["file_regex_scope"] == "relative_path"
    assert silver["ingestion"]["mode"] == "scd1_hash_diff"
    assert silver["ingestion"]["hash_exclude_columns"] == ["updated_at"]
    assert "ingestion_date" not in silver["ingestion"]["hash_exclude_columns"]


def test_databricks_templates_use_mature_parameters_canonically() -> None:
    rest = contract_template_files("bronze_rest_api_incremental")["ingestion"]
    jdbc = contract_template_files("silver_jdbc_scd1_upsert")["ingestion"]
    scd2 = contract_template_files("silver_scd2_history")["ingestion"]

    assert rest["source"]["type"] == "rest_api"
    assert rest["source"]["pagination"]["type"] == "cursor"
    assert rest["source"]["incremental"]["watermark_param"] == "updated_after"
    assert jdbc["source"]["type"] == "postgres"
    assert jdbc["source"]["read"]["num_partitions"] == 16
    assert jdbc["transform"]["deduplicate"]["order_by"] == "updated_at DESC NULLS LAST"
    assert scd2["transform"]["deduplicate"]["keys"] == ["customer_id"]
    assert "ingestion_date" not in scd2["hash_exclude_columns"]


def test_databricks_template_sources_validate_against_core_connector_semantics() -> None:
    for name in list_contract_templates():
        source = contract_template_files(name)["ingestion"]["source"]
        if isinstance(source, dict):
            validate_source_semantics(source)


def test_databricks_template_shape_blocks_validate_against_core_contracts() -> None:
    for name in list_contract_templates():
        files = contract_template_files(name)
        if files["ingestion"].get("shape"):
            validate_shape_contract(files["ingestion"]["shape"])
