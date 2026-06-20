import json

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_snowflake import plan_snowflake_contract, run_snowflake_contract
from contractforge_snowflake.preparation import apply_preparation_sql


def _contract(payload: dict | None = None):
    base = {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "ORDERS"},
        "mode": "scd0_append",
    }
    if payload:
        base.update(payload)
    return semantic_contract_from_mapping(base)


def test_snowflake_preparation_applies_metadata_projection_and_column_mapping() -> None:
    contract = _contract(
        {
            "select_columns": ["id", "amount", "is_valid"],
            "column_mapping": {"id": "order_id", "amount": "total_amount"},
        }
    )

    sql = apply_preparation_sql(contract, 'SELECT * FROM "raw"."orders"')

    assert 'SELECT "id" AS "order_id", "amount" AS "total_amount", "is_valid" AS "is_valid"' in sql


def test_snowflake_preparation_rejects_invalid_column_mapping_targets() -> None:
    contract = _contract({"column_mapping": {"id": "row_hash"}})

    with pytest.raises(ValueError, match="column_mapping cannot produce reserved control columns"):
        apply_preparation_sql(contract, 'SELECT * FROM "raw"."orders"')


def test_snowflake_preparation_renders_cast_standardize_derive_filter_and_deduplicate() -> None:
    contract = _contract(
        {
            "filter_expression": "is_valid = true",
            "shape": {
                "columns": {
                    "id": {"alias": "order_id", "cast": "NUMBER"},
                    "email": "email",
                    "updated_at": "updated_at",
                    "is_valid": "is_valid",
                }
            },
            "transform": {
                "cast": {"amount": "NUMBER(10,2)"},
                "standardize": {"email": {"trim": True, "lower": True, "empty_as_null": True}},
                "derive": {"email_domain": "SPLIT_PART(email, '@', 2)"},
                "deduplicate": {
                    "keys": ["order_id"],
                    "order_by": [{"column": "updated_at", "direction": "desc", "nulls": "last"}],
                },
            },
        }
    )

    sql = apply_preparation_sql(contract, 'SELECT * FROM "raw"."orders"')

    assert 'CAST("id" AS NUMBER) AS "order_id"' in sql
    assert 'SELECT * REPLACE (CAST("amount" AS NUMBER(10,2)) AS "amount")' in sql
    assert 'CAST("amount" AS NUMBER(10,2)) AS "amount"' in sql
    assert 'SELECT * REPLACE (NULLIF(LOWER(TRIM("email")), \'\') AS "email")' in sql
    assert 'NULLIF(LOWER(TRIM("email")), \'\') AS "email"' in sql
    assert 'SPLIT_PART("email", \'@\', 2) AS "email_domain"' in sql
    assert 'WHERE "is_valid" = true' in sql
    assert 'QUALIFY ROW_NUMBER() OVER (PARTITION BY "order_id" ORDER BY "updated_at" DESC NULLS LAST) = 1' in sql


def test_snowflake_preparation_quotes_known_columns_in_derive_expressions() -> None:
    contract = _contract(
        {
            "source": {
                "type": "staged_files",
                "path": "@RAW/customers",
                "options": {
                    "columns": {
                        "customer_id": "$1:customer_id::STRING",
                        "lifetime_value": "$1:lifetime_value::STRING",
                    }
                },
            },
            "transform": {
                "cast": {"lifetime_value": "DOUBLE"},
                "derive": {"customer_band": "CASE WHEN lifetime_value >= 1000 THEN 'VIP' ELSE 'STANDARD' END"},
            },
        }
    )

    sql = apply_preparation_sql(contract, 'SELECT "customer_id", "lifetime_value" FROM @RAW/customers')

    assert 'CASE WHEN "lifetime_value" >= 1000 THEN \'VIP\' ELSE \'STANDARD\' END AS "customer_band"' in sql


def test_snowflake_preparation_requires_deterministic_deduplicate_ordering() -> None:
    with pytest.raises(ValueError, match="deduplicate.order_by"):
        _contract({"transform": {"deduplicate": {"keys": ["order_id"]}}})


def test_snowflake_preparation_keeps_complex_nested_shape_review_required() -> None:
    result = plan_snowflake_contract(
        {
            "source": {"type": "table", "table": "raw.orders"},
            "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "ORDERS"},
            "mode": "scd0_append",
            "shape": {"parse_json": [{"column": "payload", "schema": "id STRING"}]},
        }
    )

    assert result.status == "REVIEW_REQUIRED"
    assert "SNOWFLAKE_PREPARATION_REVIEW_REQUIRED" in {warning.code for warning in result.warnings}


def test_snowflake_runtime_applies_filter_expression_before_write(tmp_path) -> None:
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps(
            {
                "source": {"type": "table", "table": "raw.orders"},
                "target": {"catalog": "ANALYTICS", "schema": "BRONZE", "table": "ORDERS"},
                "mode": "scd0_append",
                "filter_expression": "amount > 0",
            }
        ),
        encoding="utf-8",
    )
    session = _ExecutingSession()

    result = run_snowflake_contract(contract_uri=str(contract_path), session=session)

    assert result["status"] == "SUCCESS"
    assert any("WHERE amount > 0" in command for command in session.commands)


class _ExecutingSession:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def sql(self, command: str):
        self.commands.append(command)
        if command.startswith("SELECT CURRENT_WAREHOUSE()"):
            return _Result([("COMPUTE_WH", "ROLE", "DB", "PUBLIC", "10.19")])
        if " LIMIT 0" in command:
            return _Result([], schema=_Schema(("order_id", "amount")))
        if command.startswith("SELECT COUNT(*)"):
            return _Result([(2,)])
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
