from dataclasses import replace

import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_snowflake.write_modes import prewrite_validation_commands, render_write_sql
from contractforge_snowflake.write_modes.models import SnowflakeWriteContext


def _contract(payload: dict | None = None):
    base = {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "ANALYTICS", "schema": "SILVER", "table": "ORDERS"},
        "mode": "scd0_append",
    }
    if payload:
        base.update(payload)
    return semantic_contract_from_mapping(base)


def _context(contract, *, columns=("id", "name", "updated_at"), scalar_int=None) -> SnowflakeWriteContext:
    return SnowflakeWriteContext(
        contract=contract,
        session=_Session(),
        source_sql='SELECT * FROM "raw"."orders"',
        source_columns=columns,
        target='"ANALYTICS"."SILVER"."ORDERS"',
        scalar_int=scalar_int or (lambda _session, _sql: 0),
    )


def test_snowflake_append_write_sql_is_unchanged() -> None:
    sql = render_write_sql(_context(_contract()))

    assert sql == 'INSERT INTO "ANALYTICS"."SILVER"."ORDERS"\nSELECT * FROM (\nSELECT * FROM "raw"."orders"\n) AS _CF_SOURCE'


def test_snowflake_overwrite_write_sql_is_unchanged() -> None:
    sql = render_write_sql(_context(_contract({"mode": "scd0_overwrite"})))

    assert sql == (
        'CREATE OR REPLACE TABLE "ANALYTICS"."SILVER"."ORDERS" AS\n'
        'SELECT * FROM (\nSELECT * FROM "raw"."orders"\n) AS _CF_SOURCE'
    )


def test_snowflake_upsert_validates_null_and_duplicate_keys() -> None:
    contract = _contract({"mode": "scd1_upsert", "merge_keys": ["id"]})
    seen: list[str] = []

    def scalar_int(_session, sql: str) -> int:
        seen.append(sql)
        return 0

    commands = prewrite_validation_commands(_context(contract, scalar_int=scalar_int))

    assert len(commands) == 2
    assert commands == tuple(seen)
    assert 'WHERE "id" IS NULL' in commands[0]
    assert 'GROUP BY "id"' in commands[1]


def test_snowflake_upsert_rejects_null_merge_keys() -> None:
    contract = _contract({"mode": "scd1_upsert", "merge_keys": ["id"]})

    with pytest.raises(ValueError, match="source contains 1 rows with null merge_keys"):
        prewrite_validation_commands(_context(contract, scalar_int=lambda _session, sql: 1 if 'WHERE "id" IS NULL' in sql else 0))


def test_snowflake_upsert_rejects_duplicate_merge_keys() -> None:
    contract = _contract({"mode": "scd1_upsert", "merge_keys": ["id"]})

    with pytest.raises(ValueError, match="source contains duplicate merge_keys"):
        prewrite_validation_commands(_context(contract, scalar_int=lambda _session, sql: 1 if "HAVING COUNT" in sql else 0))


def test_snowflake_hash_diff_excludes_declared_columns() -> None:
    contract = _contract(
        {
            "mode": "scd1_hash_diff",
            "merge_keys": ["id"],
            "hash_strategy": "all_columns_except",
            "hash_exclude_columns": ["updated_at"],
        }
    )

    sql = render_write_sql(_context(contract))

    assert 'HASH(target."name") <> HASH(source."name")' in sql
    assert 'HASH(target."id"' not in sql
    assert 'HASH(target."updated_at"' not in sql


def test_snowflake_unsupported_write_mode_cannot_execute_silently() -> None:
    contract = _contract()
    unsupported = replace(contract, write=replace(contract.write, mode="custom:archive"))

    with pytest.raises(NotImplementedError, match="custom:archive"):
        render_write_sql(_context(unsupported))


class _Session:
    pass
