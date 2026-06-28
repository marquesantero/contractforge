"""Apply ContractForge annotations to Snowflake objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.security.redaction import redact_text
from contractforge_core.semantic import SemanticContract
from contractforge_snowflake.contract_extensions import snowflake_extensions
from contractforge_snowflake.environment import SnowflakeEnvironment
from contractforge_snowflake.evidence import record_annotation_evidence
from contractforge_snowflake.naming import quote_identifier, quote_multipart_identifier, snowflake_target_name
from contractforge_snowflake.session_ops import execute
from contractforge_snowflake.sql import sql_string
from contractforge_snowflake.values import dict_mapping as _mapping
from contractforge_snowflake.values import pipe_string_list as _as_list


@dataclass(frozen=True)
class SnowflakeAnnotationStep:
    scope: str
    annotation_type: str
    column_name: str | None
    key: str
    value: str
    sql: str


@dataclass(frozen=True)
class SnowflakeAnnotationResult:
    status: str
    applied: int
    failed: int
    commands: tuple[str, ...]


@dataclass(frozen=True)
class _TagExtractor:
    prefix: str
    extract: Callable[[dict[str, Any]], dict[str, str]]


def apply_snowflake_annotations(
    *,
    session: Any,
    environment: SnowflakeEnvironment,
    contract: SemanticContract,
    run_id: str,
) -> SnowflakeAnnotationResult:
    """Apply annotations and record canonical annotation evidence."""

    steps = annotation_steps(contract)
    if not steps:
        return SnowflakeAnnotationResult(status="NOOP", applied=0, failed=0, commands=())
    policy = _annotation_policy(contract)
    if policy == "ignore":
        return SnowflakeAnnotationResult(status="IGNORED", applied=0, failed=0, commands=())
    tag_mode = _tag_mode(contract)
    commands: list[str] = []
    applied = 0
    failed = 0
    for step in steps:
        if step.annotation_type == "tag" and tag_mode == "validate_only":
            evidence = record_annotation_evidence(
                session,
                environment=environment,
                contract=contract,
                run_id=run_id,
                step=step.__dict__,
                status="VALIDATED",
                error_message=None,
            )
            applied += 1
            commands.extend(evidence.commands)
            continue
        try:
            execute(session, step.sql)
        except Exception as exc:
            failed += 1
            evidence = record_annotation_evidence(
                session,
                environment=environment,
                contract=contract,
                run_id=run_id,
                step=step.__dict__,
                status="FAILED",
                error_message=redact_text(str(exc)),
            )
            commands.extend((step.sql, *evidence.commands))
            if policy == "fail":
                raise
        else:
            applied += 1
            evidence = record_annotation_evidence(
                session,
                environment=environment,
                contract=contract,
                run_id=run_id,
                step=step.__dict__,
                status="APPLIED",
                error_message=None,
            )
            commands.extend((step.sql, *evidence.commands))
    status = "SUCCESS" if failed == 0 else "WARNED"
    return SnowflakeAnnotationResult(status=status, applied=applied, failed=failed, commands=tuple(commands))


def annotation_steps(contract: SemanticContract) -> tuple[SnowflakeAnnotationStep, ...]:
    annotations = contract.governance.annotations if contract.governance else None
    if not isinstance(annotations, dict):
        return ()
    target = snowflake_target_name(contract)
    steps: list[SnowflakeAnnotationStep] = []
    table = _mapping(annotations.get("table"))
    description = table.get("description")
    if description:
        steps.append(_step("table", "description", None, "description", str(description), f"COMMENT ON TABLE {target} IS {sql_string(description)}"))
    steps.extend(_tag_steps(target=target, column=None, tags=_table_tags(table)))
    for column, config in _mapping(annotations.get("columns")).items():
        steps.extend(_column_steps(target=target, column=str(column), config=_mapping(config)))
    return tuple(steps)


def _column_steps(*, target: str, column: str, config: dict[str, Any]) -> tuple[SnowflakeAnnotationStep, ...]:
    steps: list[SnowflakeAnnotationStep] = []
    description = config.get("description")
    if description:
        quoted_column = _qualified_column(target, column)
        steps.append(
            _step(
                "column",
                "description",
                column,
                "description",
                str(description),
                f"COMMENT ON COLUMN {quoted_column} IS {sql_string(description)}",
            )
        )
    steps.extend(_tag_steps(target=target, column=column, tags=_column_tags(config)))
    return tuple(steps)


def _tag_steps(*, target: str, column: str | None, tags: dict[str, str]) -> tuple[SnowflakeAnnotationStep, ...]:
    builder = _column_tag_sql if column else _table_tag_sql
    scope = "column" if column else "table"
    return tuple(
        _step(scope, "tag", column, key, value, builder(target, column, key, value))
        for key, value in tags.items()
    )


def _table_tag_sql(target: str, _column: str | None, key: str, value: str) -> str:
    return f"ALTER TABLE {target} SET TAG {_tag_name(key)} = {sql_string(value)}"


def _column_tag_sql(target: str, column: str | None, key: str, value: str) -> str:
    if column is None:
        raise ValueError("column tag SQL requires a column")
    return f"ALTER TABLE {target} ALTER COLUMN {quote_identifier(column)} SET TAG {_tag_name(key)} = {sql_string(value)}"


def _step(scope: str, annotation_type: str, column: str | None, key: str, value: str, sql: str) -> SnowflakeAnnotationStep:
    return SnowflakeAnnotationStep(
        scope=scope,
        annotation_type=annotation_type,
        column_name=column,
        key=key,
        value=value,
        sql=sql,
    )


def _qualified_column(target: str, column: str) -> str:
    return f"{target}.{quote_identifier(column)}"


def _annotation_policy(contract: SemanticContract) -> str:
    annotations = contract.governance.annotations if contract.governance else None
    value = annotations.get("policy") if isinstance(annotations, dict) else None
    return str(value or "warn").lower()


def _tag_mode(contract: SemanticContract) -> str:
    annotations = contract.governance.annotations if contract.governance else None
    snowflake = snowflake_extensions(contract)
    value = snowflake.get("annotation_tag_mode") or snowflake.get("tag_mode")
    if value is not None:
        return str(value).lower()
    if not isinstance(annotations, dict):
        return "apply"
    return str(annotations.get("tags_mode") or "apply").lower()


def _tag_name(key: str) -> str:
    return quote_multipart_identifier(key) if "." in key else quote_identifier(key)


def _table_tags(table: dict[str, Any]) -> dict[str, str]:
    return _tags(table, _TABLE_TAG_EXTRACTORS)


def _column_tags(config: dict[str, Any]) -> dict[str, str]:
    return _tags(config, _COLUMN_TAG_EXTRACTORS)


def _tags(data: dict[str, Any], extractors: tuple[_TagExtractor, ...]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for extractor in extractors:
        tags.update({f"{extractor.prefix}{key}": value for key, value in extractor.extract(data).items()})
    return tags


def _str_map(value: object) -> dict[str, str]:
    return {str(key): _tag_value(item) for key, item in _mapping(value).items()}


def _indexed_tags(value: object) -> dict[str, str]:
    return {str(idx): item for idx, item in enumerate(_as_list(value), start=1)}


def _deprecated_tags(value: object) -> dict[str, str]:
    deprecated = _mapping(value)
    if not deprecated:
        return {}
    payload = {"enabled": "true"}
    payload.update({key: str(deprecated[key]) for key in ("since", "replacement", "removal_date") if deprecated.get(key)})
    return payload


def _pii_tags(value: object) -> dict[str, str]:
    pii = _mapping(value)
    if not pii:
        return {}
    return {
        "enabled": _tag_value(pii.get("enabled", True)),
        "type": str(pii.get("type", "unknown")),
        "sensitivity": str(pii.get("sensitivity", "internal")),
    }


def _tag_value(value: object) -> str:
    return str(value).lower() if isinstance(value, bool) else str(value)


_TABLE_TAG_EXTRACTORS: tuple[_TagExtractor, ...] = (
    _TagExtractor("", lambda data: _str_map(data.get("tags"))),
    _TagExtractor("alias_", lambda data: _indexed_tags(data.get("aliases"))),
    _TagExtractor("deprecated_", lambda data: _deprecated_tags(data.get("deprecated"))),
)
_COLUMN_TAG_EXTRACTORS: tuple[_TagExtractor, ...] = (
    *_TABLE_TAG_EXTRACTORS,
    _TagExtractor("pii_", lambda data: _pii_tags(data.get("pii"))),
)


__all__ = ["SnowflakeAnnotationResult", "annotation_steps", "apply_snowflake_annotations"]
