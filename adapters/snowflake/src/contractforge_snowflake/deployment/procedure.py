"""Render the Snowflake runtime procedure deployment artifact.

The procedure is a stable entry point that delegates all ingestion behavior to
the installed ContractForge Snowflake library. It is deployment code only; it
does not render per-contract ingestion logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier
from contractforge_snowflake.sql import sql_string
from contractforge_snowflake.values import mapping_view as _mapping
from contractforge_snowflake.values import text_bool as _bool


DEFAULT_RUNTIME_DATABASE = "CONTRACTFORGE"
DEFAULT_RUNTIME_SCHEMA = "CF_RUNTIME"
DEFAULT_RUNNER_PROCEDURE_NAME = "RUN_CONTRACTFORGE_CONTRACT"
DEFAULT_PYTHON_RUNTIME_VERSION = "3.10"
DEFAULT_SNOWPARK_PACKAGE = "snowflake-snowpark-python"
DEFAULT_RUNTIME_PACKAGES = (DEFAULT_SNOWPARK_PACKAGE, "pydantic", "pyyaml", "eval-type-backport")
DEFAULT_HANDLER = "contractforge_snowflake.runtime.snowpark_handler.run"
_STAGE_IMPORT_RE = re.compile(r'^@[A-Za-z0-9_.$/"\-/]+$')
_PYTHON_CODE_IMPORT_SUFFIXES = (".py", ".zip")
_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_.\-]+([<>=!~]=?[A-Za-z0-9_.*+\-]+)?$")


@dataclass(frozen=True)
class SnowflakeRuntimeProcedureSettings:
    database: str
    schema: str
    procedure_name: str
    runtime_version: str
    packages: tuple[str, ...]
    imports: tuple[str, ...]
    external_access_integrations: tuple[str, ...]
    secrets: tuple[tuple[str, str], ...]
    handler: str
    execute_as: str
    create_database: bool
    create_schema: bool


def render_runtime_procedure_sql(environment: Mapping[str, Any] | None) -> str:
    """Render SQL that creates the stable Snowflake runtime procedure."""

    settings = runtime_procedure_settings(environment or {})
    lines = [
        "-- ContractForge Snowflake runtime procedure deployment artifact.",
        "-- The procedure invokes the adapter library runner and keeps ingestion logic inside the wheel.",
    ]
    if settings.create_database:
        lines.append(f"CREATE DATABASE IF NOT EXISTS {quote_identifier(settings.database)};")
    if settings.create_schema:
        lines.append(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(settings.database)}.{quote_identifier(settings.schema)};")
    lines.extend(
        [
            f"CREATE OR REPLACE PROCEDURE {_procedure_identifier(settings)}(contract_uri STRING, environment_uri STRING)",
            "RETURNS STRING",
            "LANGUAGE PYTHON",
            f"RUNTIME_VERSION = {sql_string(settings.runtime_version)}",
            f"PACKAGES = ({_sql_string_list(settings.packages)})",
            *_external_access_lines(settings),
            f"IMPORTS = ({_sql_string_list(settings.imports)})",
            f"HANDLER = {sql_string(settings.handler)}",
            f"EXECUTE AS {settings.execute_as}",
            ";",
        ]
    )
    return "\n".join(lines) + "\n"


def runtime_procedure_settings(environment: Mapping[str, Any]) -> SnowflakeRuntimeProcedureSettings:
    snowflake = _snowflake_parameters(environment)
    database, schema, procedure_name = _procedure_parts(_text(snowflake.get("runner_procedure")))
    imports = _runtime_imports(snowflake)
    packages = _runtime_packages(snowflake)
    return SnowflakeRuntimeProcedureSettings(
        database=_text(snowflake.get("runtime_database")) or database,
        schema=_text(snowflake.get("runtime_schema")) or schema,
        procedure_name=procedure_name,
        runtime_version=_text(snowflake.get("python_runtime_version")) or DEFAULT_PYTHON_RUNTIME_VERSION,
        packages=packages,
        imports=imports,
        external_access_integrations=_identifier_sequence(snowflake.get("external_access_integrations")),
        secrets=_secret_bindings(snowflake.get("secrets")),
        handler=_text(snowflake.get("runtime_handler")) or DEFAULT_HANDLER,
        execute_as=_execute_as(snowflake),
        create_database=_bool(snowflake.get("runtime_create_database"), default=True),
        create_schema=_bool(snowflake.get("runtime_create_schema"), default=True),
    )


def _procedure_parts(value: str | None) -> tuple[str, str, str]:
    if not value:
        return DEFAULT_RUNTIME_DATABASE, DEFAULT_RUNTIME_SCHEMA, DEFAULT_RUNNER_PROCEDURE_NAME
    parts = [part for part in value.split(".") if part]
    if len(parts) != 3:
        raise ValueError("parameters.snowflake.runner_procedure must be a three-part Snowflake identifier")
    return parts[0], parts[1], parts[2]


def _runtime_imports(snowflake: Mapping[str, Any]) -> tuple[str, ...]:
    explicit = _string_sequence(snowflake.get("runtime_imports"))
    wheel = _text(snowflake.get("runtime_wheel_uri"))
    imports = (*explicit, *((wheel,) if wheel else ()))
    if not imports:
        raise ValueError(
            "Snowflake scheduled project deployment requires parameters.snowflake.runtime_wheel_uri "
            "or parameters.snowflake.runtime_imports"
        )
    validated = tuple(_validated_stage_import(value) for value in imports)
    if not any(_is_python_code_import(value) for value in validated):
        raise ValueError(
            "Snowflake runtime imports must include at least one staged .py or .zip file; "
            ".whl files are not valid Python procedure imports. Upload wheels as .zip archives "
            "or provide Python handler files."
        )
    return validated


def _runtime_packages(snowflake: Mapping[str, Any]) -> tuple[str, ...]:
    packages = _string_sequence(snowflake.get("runtime_packages"))
    return tuple(_validated_package(value) for value in (packages or DEFAULT_RUNTIME_PACKAGES))


def _execute_as(snowflake: Mapping[str, Any]) -> str:
    value = (_text(snowflake.get("execute_as")) or "OWNER").upper()
    if value not in {"OWNER", "CALLER"}:
        raise ValueError("parameters.snowflake.execute_as must be OWNER or CALLER")
    return value


def _validated_stage_import(value: str) -> str:
    text = value.strip()
    if not _STAGE_IMPORT_RE.match(text) or ".." in text.split("/"):
        raise ValueError(f"Unsafe Snowflake runtime import URI: {value}")
    return text


def _is_python_code_import(value: str) -> bool:
    path = value.rsplit("/", maxsplit=1)[-1].strip('"').lower()
    return path.endswith(_PYTHON_CODE_IMPORT_SUFFIXES)


def _validated_package(value: str) -> str:
    text = value.strip()
    if not _PACKAGE_RE.match(text):
        raise ValueError(f"Unsafe Snowflake runtime package specifier: {value}")
    return text


def _external_access_lines(settings: SnowflakeRuntimeProcedureSettings) -> tuple[str, ...]:
    lines: list[str] = []
    if settings.external_access_integrations:
        integrations = ", ".join(quote_multipart_identifier(value) for value in settings.external_access_integrations)
        lines.append(f"EXTERNAL_ACCESS_INTEGRATIONS = ({integrations})")
    if settings.secrets:
        secrets = ", ".join(f"{sql_string(alias)} = {quote_multipart_identifier(name)}" for alias, name in settings.secrets)
        lines.append(f"SECRETS = ({secrets})")
    return tuple(lines)


def _identifier_sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = tuple(_text(item) for item in value)
    else:
        raise ValueError("Snowflake external_access_integrations must be a string or list of strings")
    result = tuple(str(item) for item in items if item)
    for item in result:
        quote_multipart_identifier(item)
    return result


def _secret_bindings(value: Any) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError("Snowflake secrets must be a mapping of alias to secret name")
    bindings: list[tuple[str, str]] = []
    for alias, name in value.items():
        alias_text = _text(alias)
        name_text = _text(name)
        if not alias_text or not name_text:
            raise ValueError("Snowflake secret aliases and names cannot be empty")
        quote_multipart_identifier(name_text)
        bindings.append((alias_text, name_text))
    return tuple(bindings)


def _procedure_identifier(settings: SnowflakeRuntimeProcedureSettings) -> str:
    return ".".join(
        (
            quote_identifier(settings.database),
            quote_identifier(settings.schema),
            quote_identifier(settings.procedure_name),
        )
    )


def _snowflake_parameters(environment: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(_mapping(environment.get("parameters")).get("snowflake"))


def _string_sequence(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = tuple(_text(item) for item in value)
        if all(items):
            return tuple(str(item) for item in items)
    raise ValueError("Snowflake runtime imports/packages must be strings or lists of strings")


def _sql_string_list(values: tuple[str, ...]) -> str:
    return ", ".join(sql_string(value) for value in values)


def _text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


__all__ = [
    "DEFAULT_RUNNER_PROCEDURE_NAME",
    "DEFAULT_RUNTIME_DATABASE",
    "DEFAULT_RUNTIME_SCHEMA",
    "SnowflakeRuntimeProcedureSettings",
    "render_runtime_procedure_sql",
    "runtime_procedure_settings",
]
