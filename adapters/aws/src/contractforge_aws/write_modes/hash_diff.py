"""Render AWS Glue/Iceberg SCD1 hash-diff writes."""

from __future__ import annotations

from contractforge_core.preparation import HASH_DELIMITER, HASH_NULL_SENTINEL, resolved_hash_exclude_columns
from contractforge_core.semantic import SemanticContract
from contractforge_aws.rendering.names import iceberg_table_name
from contractforge_aws.write_modes.writer import bootstrap_or_write_lines, iceberg_table_properties

ROW_HASH_COLUMN = "row_hash"


def render_hash_diff_write(contract: SemanticContract, dataframe_name: str) -> str:
    table = iceberg_table_name(contract)
    merge_keys = tuple(contract.write.merge_keys)
    if not merge_keys:
        raise ValueError("AWS Glue Iceberg scd1_hash_diff rendering requires merge_keys")
    declared_hash_keys = tuple(contract.write.hash_keys)
    if contract.write.hash_strategy != "all_columns_except" and not declared_hash_keys:
        raise ValueError("AWS Glue Iceberg scd1_hash_diff rendering requires hash_keys")
    return "\n".join(
        [
            f"target_table = {table!r}",
            "source_view = 'contractforge_source'",
            "target_hash_view = 'contractforge_target_hashes'",
            f"merge_keys = {list(merge_keys)!r}",
            f"hash_strategy = {contract.write.hash_strategy!r}",
            f"declared_hash_keys = {list(declared_hash_keys)!r}",
            f"hash_exclude_columns = {list(contract.write.hash_exclude_columns)!r}",
            f"resolved_hash_exclude_columns = {list(resolved_hash_exclude_columns(contract))!r}",
            f"row_hash_column = {ROW_HASH_COLUMN!r}",
            *_key_guard_lines("merge_keys", "scd1_hash_diff"),
            "",
            "# Compute a content row_hash over stable columns to skip no-op updates.",
            "hash_keys = df.columns if hash_strategy == 'all_columns_except' else declared_hash_keys",
            "missing_hash_columns = [column for column in hash_keys if column not in df.columns]",
            "if missing_hash_columns:",
            "    raise ValueError(f'Missing hash_keys in source DataFrame: {missing_hash_columns}')",
            "hash_excluded = set(merge_keys) | set(resolved_hash_exclude_columns)",
            "hash_input_columns = [column for column in hash_keys if column not in hash_excluded]",
            "if not hash_input_columns:",
            "    raise ValueError('scd1_hash_diff requires at least one stable non-key hash column after exclusions')",
            f"hash_payload = [F.coalesce(F.col(column).cast('string'), F.lit({HASH_NULL_SENTINEL!r})) for column in hash_input_columns]",
            f"df = df.withColumn(row_hash_column, F.sha2(F.concat_ws({HASH_DELIMITER!r}, *hash_payload), 256))",
            "globals()['_cf_hash_input_columns'] = list(hash_input_columns)",
            "",
            *bootstrap_or_write_lines(
                dataframe_name,
                _hash_diff_merge_lines(),
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


def _hash_diff_merge_lines() -> list[str]:
    return [
        "target_columns = _cf_describe_table_schema(spark, target_table)",
        "target_projection_columns = [column for column in [*merge_keys, row_hash_column] if column in target_columns]",
        "if row_hash_column in target_projection_columns and all(key in target_projection_columns for key in merge_keys):",
        "    quoted_projection = ', '.join(_quote_identifier(column) for column in target_projection_columns)",
        "    spark.sql(f'SELECT {quoted_projection} FROM {target_table}').createOrReplaceTempView(target_hash_view)",
        "    join_condition = ' AND '.join(",
        "        f'source.{_quote_identifier(key)} = target_hash.{_quote_identifier(key)}'",
        "        for key in merge_keys",
        "    )",
        "    df.createOrReplaceTempView(source_view)",
        "    df = spark.sql(f'''",
        "        SELECT source.*",
        "        FROM {source_view} AS source",
        "        LEFT JOIN {target_hash_view} AS target_hash",
        "        ON {join_condition}",
        "        WHERE target_hash.{_quote_identifier(row_hash_column)} IS NULL",
        "           OR target_hash.{_quote_identifier(row_hash_column)} <> source.{_quote_identifier(row_hash_column)}",
        "    ''')",
        "_cf_hash_diff_candidate_count = int(df.count())",
        "globals()['_cf_hash_diff_candidate_rows'] = _cf_hash_diff_candidate_count",
        "if _cf_hash_diff_candidate_count == 0:",
        "    _cf_run_status = 'SKIPPED'",
        "    _cf_write_engine_status = 'SKIPPED'",
        "    _cf_write_engine_reason = 'No hash changes detected for scd1_hash_diff'",
        "    _cf_skip_reason = 'no_hash_changes'",
        "else:",
        "    df.createOrReplaceTempView(source_view)",
        "    columns = df.columns",
        "    on_clause = ' AND '.join(",
        "        f'target.{_quote_identifier(key)} = source.{_quote_identifier(key)}'",
        "        for key in merge_keys",
        "    )",
        "    assignments = ', '.join(",
        "        f'target.{_quote_identifier(column)} = source.{_quote_identifier(column)}'",
        "        for column in columns",
        "    )",
        "    insert_columns = ', '.join(_quote_identifier(column) for column in columns)",
        "    insert_values = ', '.join(f'source.{_quote_identifier(column)}' for column in columns)",
        "    row_hash_identifier = _quote_identifier(row_hash_column)",
        "",
        "    spark.sql(f'''",
        "    MERGE INTO {target_table} AS target",
        "    USING {source_view} AS source",
        "    ON {on_clause}",
        "    WHEN MATCHED AND (target.{row_hash_identifier} IS NULL OR target.{row_hash_identifier} <> source.{row_hash_identifier}) THEN UPDATE SET {assignments}",
        "    WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
        "    ''')",
    ]
