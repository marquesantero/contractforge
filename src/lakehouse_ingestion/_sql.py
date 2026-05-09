"""Helpers de manipulação de SQL e identificadores."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional, Union

from pyspark.sql import DataFrame

from .config import CONFIG


def q(identifier: str) -> str:
    """Quota um identificador SQL escapando crases internas."""
    return f"`{identifier.replace('`', '``')}`"


def qt(table_name: str) -> str:
    """Quota um nome de tabela com pontos preservando partes."""
    return ".".join(q(part) for part in table_name.split("."))


def full_table_name(catalog: str, schema: str, table: str) -> str:
    return f"{catalog}.{schema}.{table}"


def utc_now_ts() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_str() -> str:
    return utc_now_ts().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return utc_now_ts().strftime("%Y-%m-%d")


def new_run_id() -> str:
    return str(uuid.uuid4())


def safe_truncate(text: Optional[str], max_len: int = CONFIG.max_error_len) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n...TRUNCATED..."


def sql_lit(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "'" + str(value).replace("'", "''") + "'"


def sql_int(value: Optional[int]) -> str:
    return "NULL" if value is None else str(int(value))


def to_json(value: Any) -> str:
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def as_list(value: Optional[Union[str, Iterable[str]]], sep: str = "|") -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [x.strip() for x in value.split(sep) if x.strip()]
    return [str(x).strip() for x in value if str(x).strip()]


def validate_cols(df: DataFrame, cols: List[str], context: str = "columns") -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{context} não encontradas: {missing}")
