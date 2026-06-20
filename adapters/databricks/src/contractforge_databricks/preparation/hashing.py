"""Hash expression helpers for Databricks staging."""

from __future__ import annotations

from contractforge_core.preparation import HASH_DELIMITER, HASH_NULL_SENTINEL
from contractforge_databricks.sql import quote_identifier

ROW_HASH_COLUMN = "row_hash"


def render_row_hash_expression(columns: tuple[str, ...], *, exclude: tuple[str, ...] = ()) -> str:
    included = tuple(column for column in columns if column not in set(exclude))
    if not included:
        raise ValueError("row hash requires at least one included column")
    payload = ", ".join(
        f"coalesce(cast({quote_identifier(column)} as string), '{HASH_NULL_SENTINEL}')" for column in included
    )
    return f"sha2(concat_ws('{HASH_DELIMITER}', {payload}), 256)"
