"""Render Iceberg write operations for AWS Glue Spark."""

from __future__ import annotations

from collections.abc import Callable

from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.names import iceberg_table_name
from contractforge_aws.write_modes.hash_diff import render_hash_diff_write
from contractforge_aws.write_modes.writer import (
    bootstrap_or_write_lines,
    iceberg_table_properties,
    writer_action_lines,
)

RENDERABLE_WRITE_MODES = frozenset({"scd0_append", "scd0_overwrite", "scd1_upsert", "scd1_hash_diff"})


def write_requires_functions(contract: SemanticContract) -> bool:
    """Return whether the write rendering needs ``pyspark.sql.functions``."""

    return contract.write.mode == "scd1_hash_diff"


def render_iceberg_write(contract: SemanticContract, *, dataframe_name: str = "df") -> str:
    renderer = _WRITE_MODE_RENDERERS.get(contract.write.mode)
    if renderer is None:
        raise ValueError(f"AWS Glue renderer does not generate runtime code for write mode {contract.write.mode!r} yet")
    return renderer(contract, dataframe_name)


def _append_write(contract: SemanticContract, dataframe_name: str) -> str:
    table = iceberg_table_name(contract)
    return "\n".join(
        [
            f"target_table = {table!r}",
            *bootstrap_or_write_lines(
                dataframe_name,
                _append_lines(dataframe_name),
                table_properties=iceberg_table_properties(contract),
            ),
            "",
        ]
    )


def _overwrite_write(contract: SemanticContract, dataframe_name: str) -> str:
    table = iceberg_table_name(contract)
    return "\n".join(
        [
            f"target_table = {table!r}",
            *writer_action_lines(
                dataframe_name,
                "createOrReplace",
                table_properties=iceberg_table_properties(contract),
            ),
            "",
        ]
    )


def _upsert_write(contract: SemanticContract, dataframe_name: str) -> str:
    table = iceberg_table_name(contract)
    merge_keys = tuple(contract.write.merge_keys)
    if not merge_keys:
        raise ValueError("AWS Glue Iceberg scd1_upsert rendering requires merge_keys")
    return "\n".join(
        [
            f"target_table = {table!r}",
            "source_view = 'contractforge_source'",
            f"merge_keys = {list(merge_keys)!r}",
            *_key_guard_lines("merge_keys", "scd1_upsert"),
            *bootstrap_or_write_lines(
                dataframe_name,
                _upsert_merge_lines(),
                table_properties=iceberg_table_properties(contract),
            ),
            "",
        ]
    )


def _key_guard_lines(key_variable: str, write_mode: str) -> list[str]:
    return [
        "",
        "def _quote_identifier(value):",
        "    return '`' + str(value).replace('`', '``') + '`'",
        "",
        "",
        f"missing_keys = [key for key in {key_variable} if key not in df.columns]",
        "if missing_keys:",
        f"    raise ValueError(f'Missing {key_variable} in source DataFrame: {{missing_keys}}')",
        "",
        f"null_predicate = ' OR '.join(f'{{_quote_identifier(key)}} IS NULL' for key in {key_variable})",
        "if null_predicate and df.filter(null_predicate).limit(1).count() > 0:",
        f"    raise ValueError(f'{write_mode} source contains null {key_variable}: {{{key_variable}}}')",
        "",
        "duplicate_keys = (",
        f"    df.groupBy(*{key_variable})",
        "    .count()",
        "    .filter('`count` > 1')",
        "    .limit(1)",
        "    .count()",
        ")",
        "if duplicate_keys:",
        f"    raise ValueError(f'{write_mode} source contains duplicate {key_variable}: {{{key_variable}}}')",
        "",
    ]


def _append_lines(dataframe_name: str) -> list[str]:
    return [
        "(",
        f"    {dataframe_name}.writeTo(target_table)",
        "    .using('iceberg')",
        "    .append()",
        ")",
    ]


def _upsert_merge_lines() -> list[str]:
    return [
        "df.createOrReplaceTempView(source_view)",
        "columns = df.columns",
        "on_clause = ' AND '.join(",
        "    f'target.{_quote_identifier(key)} = source.{_quote_identifier(key)}'",
        "    for key in merge_keys",
        ")",
        "assignments = ', '.join(",
        "    f'target.{_quote_identifier(column)} = source.{_quote_identifier(column)}'",
        "    for column in columns",
        ")",
        "insert_columns = ', '.join(_quote_identifier(column) for column in columns)",
        "insert_values = ', '.join(f'source.{_quote_identifier(column)}' for column in columns)",
        "",
        "spark.sql(f'''",
        "MERGE INTO {target_table} AS target",
        "USING {source_view} AS source",
        "ON {on_clause}",
        "WHEN MATCHED THEN UPDATE SET {assignments}",
        "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
        "''')",
    ]


_WRITE_MODE_RENDERERS: dict[str, Callable[[SemanticContract, str], str]] = {
    "scd0_append": _append_write,
    "scd0_overwrite": _overwrite_write,
    "scd1_upsert": _upsert_write,
    "scd1_hash_diff": render_hash_diff_write,
}
