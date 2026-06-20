"""Unity Catalog access drift inspection helpers."""

from __future__ import annotations

from typing import Any

from contractforge_databricks.rendering.names import target_full_name
from contractforge_databricks.sql import quote_table_name


def current_table_grants(runner: Any, target_table: str) -> set[tuple[str, str]] | None:
    """Return current table grants when the runner exposes a query interface."""

    query = getattr(runner, "query", None)
    if not callable(query):
        return None
    rows = query(f"SHOW GRANTS ON TABLE {quote_table_name(target_table)}")
    return {_grant_tuple(row) for row in rows if _grant_tuple(row) != (None, None)}  # type: ignore[misc]


def current_contract_grants(runner: Any, contract: Any) -> set[tuple[str, str]] | None:
    return current_table_grants(runner, target_full_name(contract))


def _grant_tuple(row: Any) -> tuple[str | None, str | None]:
    principal = _row_value(row, "Principal", "principal", "grantee")
    privilege = _row_value(row, "ActionType", "actionType", "Privilege", "privilege")
    if principal is None or privilege is None:
        return (None, None)
    return (str(principal), str(privilege).upper())


def _row_value(row: Any, *names: str) -> Any:
    if isinstance(row, dict):
        data = row
    elif hasattr(row, "asDict"):
        data = row.asDict(recursive=True)
    else:
        try:
            data = dict(row)
        except Exception:
            data = {}
    lower = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name in data:
            return data[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return None
