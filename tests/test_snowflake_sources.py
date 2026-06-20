import json

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_snowflake import plan_snowflake_contract, run_snowflake_contract
from contractforge_snowflake.sources import render_snowflake_source
from contractforge_snowflake.sources.table_refs import contract_with_snowflake_source_refs


def test_snowflake_table_source_sql_is_unchanged() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "raw.customers"},
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
            "mode": "scd0_append",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == 'SELECT * FROM "raw"."customers"'
    assert plan.metadata == {"type": "table", "table": "raw.customers"}


def test_snowflake_source_resolves_logical_table_ref_to_layer_namespace() -> None:
    contract = contract_with_snowflake_source_refs(
        semantic_contract_from_mapping(
            {
                "source": {"type": "table", "ref": "bronze.b_products_jdbc"},
                "target": {"catalog": "ANALYTICS", "schema": "CF_SUPABASE_SILVER", "table": "S_PRODUCT_TAGS"},
                "layer": "silver",
                "mode": "scd0_overwrite",
            }
        )
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == 'SELECT * FROM "ANALYTICS"."CF_SUPABASE_BRONZE"."b_products_jdbc"'
    assert plan.metadata == {"type": "table", "table": "ANALYTICS.CF_SUPABASE_BRONZE.b_products_jdbc"}


def test_snowflake_sql_source_resolves_logical_table_ref_placeholders() -> None:
    contract = contract_with_snowflake_source_refs(
        semantic_contract_from_mapping(
            {
                "source": {
                    "type": "sql",
                    "query": "SELECT * FROM {{ table_ref:silver.s_product_tags }}",
                },
                "target": {"catalog": "ANALYTICS", "schema": "CF_SUPABASE_GOLD", "table": "G_BRAND_INVENTORY"},
                "layer": "gold",
                "mode": "scd0_overwrite",
            }
        )
    )

    plan = render_snowflake_source(contract)

    assert "ANALYTICS.CF_SUPABASE_SILVER.s_product_tags" in plan.sql
    assert "{{ table_ref:" not in plan.sql


def test_snowflake_view_source_uses_table_renderer() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "view", "table": "raw.active_customers"},
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
            "mode": "scd0_append",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == 'SELECT * FROM "raw"."active_customers"'
    assert plan.metadata == {"type": "view", "table": "raw.active_customers"}


def test_snowflake_sql_source_sql_is_unchanged() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "sql", "query": "select * from raw.customers;"},
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
            "mode": "scd0_overwrite",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == "select * from raw.customers"
    assert plan.metadata == {"type": "sql", "query_present": True}


def test_snowflake_stage_source_sql_is_unchanged() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW_STAGE/customers/",
                "options": {
                    "file_format": "RAW_CSV_FORMAT",
                    "pattern": ".*[.]csv",
                    "columns": {"customer_id": "$1::NUMBER", "name": "$2::STRING"},
                },
            },
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
            "mode": "scd0_append",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == (
        'SELECT $1::NUMBER AS "customer_id", $2::STRING AS "name"\n'
        "FROM @RAW_STAGE/customers/ (FILE_FORMAT => 'RAW_CSV_FORMAT', PATTERN => '.*[.]csv') AS _CF_STAGE"
    )
    assert plan.metadata == {
        "type": "staged_files",
        "stage": "@RAW_STAGE/customers/",
        "file_format": "RAW_CSV_FORMAT",
        "pattern_present": True,
    }


def test_snowflake_stage_csv_source_renders_named_file_format_and_list_columns() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW_STAGE/orders/",
                "format": "csv",
                "options": {
                    "file_format": "RAW_CSV_FORMAT",
                    "columns": ["order_id", "status", "amount"],
                },
            },
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == (
        'SELECT $1 AS "order_id", $2 AS "status", $3 AS "amount"\n'
        "FROM @RAW_STAGE/orders/ (FILE_FORMAT => 'RAW_CSV_FORMAT') AS _CF_STAGE"
    )
    assert plan.metadata == {
        "type": "staged_files",
        "stage": "@RAW_STAGE/orders/",
        "file_format": "RAW_CSV_FORMAT",
        "pattern_present": False,
        "format": "csv",
    }


def test_snowflake_stage_json_source_defaults_to_payload_variant() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW_STAGE/orders/",
                "format": "json",
                "options": {"file_format": "RAW_JSON_FORMAT"},
            },
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == 'SELECT $1 AS "payload"\nFROM @RAW_STAGE/orders/ (FILE_FORMAT => \'RAW_JSON_FORMAT\') AS _CF_STAGE'


def test_snowflake_stage_json_source_projects_columns() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW_STAGE/orders/",
                "format": "json",
                "options": {
                    "file_format": "RAW_JSON_FORMAT",
                    "columns": {
                        "order_id": "$1:order_id::NUMBER",
                        "status": "$1:status::STRING",
                    }
                },
            },
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == (
        'SELECT $1:order_id::NUMBER AS "order_id", $1:status::STRING AS "status"\n'
        "FROM @RAW_STAGE/orders/ (FILE_FORMAT => 'RAW_JSON_FORMAT') AS _CF_STAGE"
    )


def test_snowflake_stage_parquet_source_projects_columns() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW_STAGE/orders/",
                "format": "parquet",
                "options": {
                    "file_format": "RAW_PARQUET_FORMAT",
                    "columns": {
                        "order_id": "$1:order_id::NUMBER",
                        "status": "$1:status::STRING",
                    }
                },
            },
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    plan = render_snowflake_source(contract)

    assert plan.sql == (
        'SELECT $1:order_id::NUMBER AS "order_id", $1:status::STRING AS "status"\n'
        "FROM @RAW_STAGE/orders/ (FILE_FORMAT => 'RAW_PARQUET_FORMAT') AS _CF_STAGE"
    )


def test_snowflake_stage_source_rejects_inline_file_format_mapping() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW_STAGE/orders/",
                "format": "csv",
                "options": {"file_format": {"type": "csv", "skip_header": 1}},
            },
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    with pytest.raises(ValueError, match="requires a named file_format"):
        render_snowflake_source(contract)


def test_snowflake_stage_source_rejects_unsafe_column_expression() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW_STAGE/orders/",
                "format": "csv",
                "options": {"columns": {"order_id": "$1; DROP TABLE x"}},
            },
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    with pytest.raises(ValueError, match="Unsafe Snowflake staged file source column expression"):
        render_snowflake_source(contract)


def test_snowflake_stage_source_rejects_unsafe_stage_path() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "staged_files", "path": "@RAW_STAGE/../orders/", "format": "csv"},
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    with pytest.raises(ValueError, match="Unsafe Snowflake stage reference"):
        render_snowflake_source(contract)


def test_snowflake_plan_marks_unknown_staged_file_format_review_required() -> None:
    result = plan_snowflake_contract(
        {
            "source": {"type": "staged_files", "path": "@RAW_STAGE/orders/", "format": "avro"},
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "REVIEW_REQUIRED"
    assert "SNOWFLAKE_STAGED_FILE_FORMAT_REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_snowflake_source_registry_rejects_unsupported_source() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "kafka", "topic": "events"},
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
            "mode": "scd0_append",
        }
    )

    with pytest.raises(NotImplementedError, match="Snowflake runtime source is not implemented: kafka"):
        render_snowflake_source(contract)


def test_snowflake_unsupported_source_planner_status_is_unchanged() -> None:
    result = plan_snowflake_contract(
        {
            "source": {"type": "autoloader", "path": "s3://landing/customers/", "format": "json"},
            "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
            "mode": "scd0_append",
        }
    )

    assert result.status == "UNSUPPORTED"
    assert [blocker.code for blocker in result.blockers] == ["SNOWFLAKE_SOURCE_AUTOLOADER_UNSUPPORTED"]


def test_snowflake_runtime_metrics_include_source_metadata(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "raw.customers"},
                "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "CUSTOMERS"},
                "mode": "scd0_append",
            }
        ),
        encoding="utf-8",
    )
    session = _ExecutingSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["metrics"]["source"] == {"type": "table", "table": "raw.customers"}
    run_insert = next(command for command in session.commands if '"ctrl_ingestion_runs"' in command and "INSERT INTO" in command)
    assert '"source":{"table":"raw.customers","type":"table"}' in run_insert


def test_snowflake_runtime_materializes_rest_api_source(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contractforge_snowflake.sources import rest_api as rest_source

    monkeypatch.setattr(
        rest_source,
        "read_rest_api_records",
        lambda _source: [{"raw_response": '{"ok": true}', "response_page_number": 1}],
    )
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps(
            {
                "source": {
                    "type": "rest_api",
                    "request": {"method": "GET", "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"},
                    "response": {"mode": "raw", "raw_column": "raw_response"},
                },
                "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "USGS_RAW"},
                "mode": "scd0_overwrite",
            }
        ),
        encoding="utf-8",
    )
    session = _ExecutingSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session, run_id="run-rest-1")

    assert result["status"] == "SUCCESS"
    assert result["metrics"]["source"]["type"] == "rest_api"
    assert result["metrics"]["source"]["records_materialized"] == 1
    assert any('CREATE OR REPLACE TEMPORARY TABLE "CF_REST_ANALYTICS_BRONZE_USGS_RAW_run_rest_1"' in command for command in session.commands)
    assert any('INSERT INTO "CF_REST_ANALYTICS_BRONZE_USGS_RAW_run_rest_1"' in command and '{"ok": true}' in command for command in session.commands)
    assert any('SELECT * FROM "CF_REST_ANALYTICS_BRONZE_USGS_RAW_run_rest_1"' in command for command in session.commands)


class _ExecutingSession:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def sql(self, command: str):
        self.commands.append(command)
        if command.startswith("SELECT CURRENT_WAREHOUSE()"):
            return _Result([("COMPUTE_WH", "ROLE", "DB", "PUBLIC", "10.19")])
        if " LIMIT 0" in command:
            return _Result([], schema=_Schema(("customer_id", "name")))
        if command.startswith("SELECT COUNT(*)"):
            return _Result([(3,)])
        return _Result([])


class _Result:
    query_id = "qid"
    rowcount = None

    def __init__(self, rows, *, schema=None):
        self._rows = rows
        self.schema = schema

    def collect(self):
        return self._rows


class _Schema:
    def __init__(self, names):
        self.names = names
