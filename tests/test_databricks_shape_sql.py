from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.shapes import render_shape_sql


def test_render_shape_sql_for_json_arrays_and_projection() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.events"},
            "target": {"table": "events"},
            "shape": {
                "parse_json": [{"column": "payload", "schema": "STRUCT<id: STRING>", "alias": "payload_obj"}],
                "arrays": [{"path": "payload_obj.items", "mode": "size", "alias": "item_count"}],
                "columns": {
                    "payload_obj.id": {"alias": "event_id", "cast": "STRING"},
                    "item_count": "item_count",
                    "ingested_at": {"expression": "current_timestamp()", "alias": "ingested_at"},
                },
            },
        }
    )

    sql = render_shape_sql(contract, source_view="tmp.raw_events", output_view="tmp.shaped_events")

    assert "CREATE OR REPLACE TEMP VIEW `tmp`.`shaped_events` AS" in sql
    assert "CAST(`payload_obj`.`id` AS STRING) AS `event_id`" in sql
    assert "`item_count` AS `item_count`" in sql
    assert "current_timestamp() AS `ingested_at`" in sql


def test_render_shape_sql_for_parse_json_and_zip_arrays_without_projection() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.weather"},
            "target": {"table": "weather"},
            "shape": {
                "parse_json": [{"column": "payload", "schema_ref": "weather_payload", "alias": "payload_obj"}],
                "zip_arrays": [{"alias": "hour", "columns": {"time": "time", "temperature": "temperature"}}],
                "arrays": [{"path": "hour", "mode": "explode_outer", "alias": "hour"}],
            },
        }
    )

    sql = render_shape_sql(contract)

    assert "from_json(`payload`, '${schema:weather_payload}') AS `payload_obj`" in sql
    assert "arrays_zip(`time`, `temperature`) AS `hour`" in sql
    assert "explode_outer(`hour`) AS `hour`" in sql
    assert "cardinality review" in sql


def test_render_shape_sql_for_flatten_review_note() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.events"},
            "target": {"table": "events"},
            "shape": {"flatten": {"enabled": True, "separator": "__"}},
        }
    )

    sql = render_shape_sql(contract)

    assert "flatten requires schema-aware expansion" in sql
    assert "flatten: enabled with separator '__'" in sql


def test_render_shape_sql_applies_parse_json_cast_input_string() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.events"},
            "target": {"table": "events"},
            "shape": {
                "parse_json": [
                    {
                        "column": "value",
                        "alias": "payload",
                        "schema": "STRUCT<id: STRING>",
                        "cast_input": "STRING",
                    }
                ]
            },
        }
    )

    sql = render_shape_sql(contract)

    assert "from_json(CAST(`value` AS STRING), 'STRUCT<id: STRING>') AS `payload`" in sql


def test_render_shape_sql_without_shape() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.events"},
            "target": {"table": "events"},
        }
    )

    assert render_shape_sql(contract) == "-- No shape declared.\n"
