"""Connector source contract model."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from contractforge_core.contracts.base import ExtensibleContractModel, StrictContractModel


class ConnectorExtensionMap(ExtensibleContractModel):
    """Connector-specific extension map."""


class ConnectorSourceContract(StrictContractModel):
    """Generic declarative connector source contract."""

    type: Literal["connector"]
    connector: str
    name: str | None = None
    provider: str | None = None
    system: str | None = None
    protocol: str | None = None
    mode: str | None = None
    connection: str | None = None
    format: str | None = None
    path: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    mailbox: str | None = None
    object: str | None = None
    account_url: str | None = None
    container: str | None = None
    site: str | None = None
    drive: str | None = None
    url: str | None = None
    environment_url: str | None = None
    entity: str | None = None
    index: str | None = None
    uri: str | None = None
    database: str | None = None
    collection: str | None = None
    table: str | None = None
    query: Any = None
    select: Any = None
    filter: str | None = None
    expand: Any = None
    orderby: Any = None
    top: int | None = Field(default=None, gt=0)
    pipeline: Any = None
    options: dict[str, Any] = Field(default_factory=dict)
    read: dict[str, Any] = Field(default_factory=dict)
    request: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    pagination: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    incremental: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)

    @field_validator("connector")
    @classmethod
    def _connector_name(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator(
        "name",
        "provider",
        "system",
        "protocol",
        "mode",
        "connection",
        "format",
        "path",
        "host",
        "mailbox",
        "object",
        "account_url",
        "container",
        "site",
        "drive",
        "url",
        "environment_url",
        "entity",
        "index",
        "uri",
        "database",
        "collection",
        "table",
        "filter",
        mode="after",
    )
    @classmethod
    def _empty_string_to_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def _validate_connector(self) -> "ConnectorSourceContract":
        if self.connector in {
            "jdbc",
            "mysql",
            "mariadb",
            "oracle",
            "postgres",
            "redshift",
            "sqlserver",
            "db2",
            "snowflake_jdbc",
            "bigquery_jdbc",
        }:
            if self.table is not None and self.query is not None:
                raise ValueError("JDBC connector accepts source.table or source.query, not both")
        return self
