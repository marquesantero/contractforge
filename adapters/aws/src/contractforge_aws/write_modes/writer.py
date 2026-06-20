"""Shared AWS Iceberg writer rendering helpers."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.contract_extensions import aws_extensions
from contractforge_aws.security import contains_secret_placeholder


def bootstrap_or_write_lines(
    dataframe_name: str,
    write_lines: list[str],
    *,
    table_properties: dict[str, str],
) -> list[str]:
    return [
        "_cf_target_schema_for_write = _cf_describe_table_schema(spark, target_table) if '_cf_describe_table_schema' in globals() else {}",
        "if not _cf_target_schema_for_write:",
        *_indent(writer_action_lines(dataframe_name, "create", table_properties=table_properties)),
        "else:",
        *_indent(write_lines),
    ]


def writer_action_lines(dataframe_name: str, action: str, *, table_properties: dict[str, str]) -> list[str]:
    return [
        f"_cf_table_properties = {table_properties!r}",
        f"_cf_writer = {dataframe_name}.writeTo(target_table).using('iceberg')",
        "for _cf_property_name, _cf_property_value in _cf_table_properties.items():",
        "    _cf_writer = _cf_writer.tableProperty(str(_cf_property_name), str(_cf_property_value))",
        f"_cf_writer.{action}()",
    ]


def iceberg_table_properties(contract: SemanticContract) -> dict[str, str]:
    iceberg = aws_extensions(contract).get("iceberg")
    if not isinstance(iceberg, dict):
        return {}
    raw = iceberg.get("table_properties")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("extensions.aws.iceberg.table_properties must be a map")
    if contains_secret_placeholder(raw):
        raise ValueError("extensions.aws.iceberg.table_properties must not contain secret placeholders")
    properties = {str(key).strip(): str(value) for key, value in raw.items()}
    if any(not key for key in properties):
        raise ValueError("extensions.aws.iceberg.table_properties keys must be non-empty")
    return properties


def _indent(lines: list[str]) -> list[str]:
    return [f"    {line}" if line else "" for line in lines]
