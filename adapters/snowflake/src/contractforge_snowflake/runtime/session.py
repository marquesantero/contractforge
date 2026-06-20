"""Snowflake connector session adapter for the library runner."""

from __future__ import annotations

import re
import tempfile
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_STAGE_ARTIFACT_RE = re.compile(r'^@[A-Za-z0-9_.$/"\-/]+$')


@dataclass(frozen=True)
class SnowflakeConnectorField:
    name: str
    datatype: str


@dataclass(frozen=True)
class SnowflakeConnectorSchema:
    fields: tuple[SnowflakeConnectorField, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)


class SnowflakeConnectorResult:
    def __init__(
        self,
        rows: list[Any],
        fields: tuple[SnowflakeConnectorField, ...],
        *,
        query_id: str | None = None,
        rowcount: int | None = None,
    ) -> None:
        self._rows = rows
        self.schema = SnowflakeConnectorSchema(fields) if fields else None
        self.query_id = query_id
        self.rowcount = rowcount

    def collect(self) -> list[Any]:
        return self._rows


class SnowflakeConnectorSession:
    """Adapt a snowflake-connector-python connection to the runner session API."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.file = SnowflakeConnectorFileAccessor(connection)

    def sql(self, command: str) -> SnowflakeConnectorResult:
        cursor = self.connection.cursor()
        try:
            cursor.execute(command)
            fields = _fields(cursor)
            rows = list(cursor.fetchall()) if getattr(cursor, "description", None) else []
            return SnowflakeConnectorResult(
                rows=rows,
                fields=fields,
                query_id=_query_id(cursor),
                rowcount=_rowcount(cursor),
            )
        finally:
            cursor.close()


class SnowflakeConnectorFileAccessor:
    """Snowpark-like file accessor backed by snowflake-connector-python GET."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def get_stream(self, uri: str) -> BytesIO:
        _validate_stage_artifact_uri(uri)
        with tempfile.TemporaryDirectory(prefix="contractforge-snowflake-get-") as tmpdir:
            target = _file_uri(Path(tmpdir))
            cursor = self.connection.cursor()
            try:
                cursor.execute(f"GET {uri} {target} PARALLEL=1")
            finally:
                cursor.close()
            files = tuple(path for path in Path(tmpdir).rglob("*") if path.is_file())
            if not files:
                raise FileNotFoundError(f"Snowflake stage artifact was not downloaded: {uri}")
            return BytesIO(files[0].read_bytes())


def _fields(cursor: Any) -> tuple[SnowflakeConnectorField, ...]:
    description = getattr(cursor, "description", None) or ()
    fields: list[SnowflakeConnectorField] = []
    for item in description:
        name = str(getattr(item, "name", None) or item[0])
        datatype = _datatype(item)
        fields.append(SnowflakeConnectorField(name=name, datatype=datatype))
    return tuple(fields)


def _datatype(item: Any) -> str:
    for attribute in ("datatype", "data_type", "type_name", "type_code"):
        value = getattr(item, attribute, None)
        if value is not None:
            return _normalize_type(str(value))
    try:
        return _normalize_type(str(item[1]))
    except (TypeError, IndexError, KeyError):
        return "VARIANT"


def _normalize_type(value: str) -> str:
    text = value.upper().strip()
    if not text:
        return "VARIANT"
    numeric_aliases = {
        "0": "NUMBER",
        "1": "FLOAT",
        "2": "VARCHAR",
        "3": "DATE",
        "4": "TIMESTAMP_NTZ",
        "5": "VARIANT",
        "6": "TIMESTAMP_NTZ",
        "7": "TIMESTAMP_NTZ",
        "8": "TIMESTAMP_NTZ",
        "9": "OBJECT",
        "10": "ARRAY",
        "11": "BINARY",
        "12": "TIME",
        "13": "BOOLEAN",
    }
    if text.isdigit():
        return numeric_aliases.get(text, "VARIANT")
    aliases = {
        "FIXED": "NUMBER",
        "TEXT": "VARCHAR",
        "REAL": "FLOAT",
        "TIMESTAMP_LTZ": "TIMESTAMP_NTZ",
        "TIMESTAMP_TZ": "TIMESTAMP_NTZ",
    }
    return aliases.get(text, text)


def _query_id(cursor: Any) -> str | None:
    value = getattr(cursor, "sfqid", None) or getattr(cursor, "query_id", None)
    return str(value) if value else None


def _rowcount(cursor: Any) -> int | None:
    value = getattr(cursor, "rowcount", None)
    if value is None:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count >= 0 else None


def _validate_stage_artifact_uri(uri: str) -> None:
    if not _STAGE_ARTIFACT_RE.match(uri) or ".." in uri.split("/"):
        raise ValueError(f"Unsafe Snowflake stage artifact URI: {uri}")


def _file_uri(path: Path) -> str:
    text = "file://" + path.resolve().as_posix().replace("'", "''")
    return text if text.endswith("/") else text + "/"


__all__ = [
    "SnowflakeConnectorFileAccessor",
    "SnowflakeConnectorField",
    "SnowflakeConnectorResult",
    "SnowflakeConnectorSchema",
    "SnowflakeConnectorSession",
]
