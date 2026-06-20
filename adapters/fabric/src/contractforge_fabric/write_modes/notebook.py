"""Render Fabric notebook write-mode statements."""

from __future__ import annotations

import json

from contractforge_core.preparation import HASH_DELIMITER, HASH_NULL_SENTINEL, resolved_hash_exclude_columns
from contractforge_core.semantic import SemanticContract


def render_notebook_write_statement(contract: SemanticContract) -> str:
    mode = contract.write.mode
    if mode in {"scd0_append", "append"}:
        return 'df.write.format("delta").mode("append").saveAsTable(TARGET_TABLE)'
    if mode in {"scd0_overwrite", "overwrite"}:
        return 'df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)'
    if mode in {"scd1_upsert", "upsert"}:
        return _upsert_statement(contract)
    if mode in {"scd1_hash_diff", "hash_diff_upsert"}:
        return _hash_diff_statement(contract)
    if mode in {"snapshot_soft_delete", "snapshot_reconcile_soft_delete"}:
        return _snapshot_soft_delete_statement(contract)
    if mode in {"scd2_historical", "historical"}:
        return _scd2_historical_statement(contract)
    return f"raise NotImplementedError({json.dumps(f'Fabric notebook runtime does not implement mode {mode}')})"


def _upsert_statement(contract: SemanticContract) -> str:
    merge_keys = tuple(contract.write.merge_keys)
    if not merge_keys:
        raise ValueError("Fabric Lakehouse upsert notebook runtime requires merge_keys")

    return "\n".join(
        [
            f"MERGE_KEYS = {json.dumps(list(merge_keys))}",
            "",
            *_merge_key_guard_lines(contract.write.mode),
            "if not spark.catalog.tableExists(TARGET_TABLE):",
            '    df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)',
            "else:",
            "    SOURCE_VIEW = 'contractforge_source'",
            "    df.createOrReplaceTempView(SOURCE_VIEW)",
            "    columns = df.columns",
            "    on_clause = ' AND '.join(",
            "        f'target.{_cf_quote_identifier(key)} = source.{_cf_quote_identifier(key)}'",
            "        for key in MERGE_KEYS",
            "    )",
            "    assignments = ', '.join(",
            "        f'target.{_cf_quote_identifier(column)} = source.{_cf_quote_identifier(column)}'",
            "        for column in columns",
            "    )",
            "    insert_columns = ', '.join(_cf_quote_identifier(column) for column in columns)",
            "    insert_values = ', '.join(f'source.{_cf_quote_identifier(column)}' for column in columns)",
            "    spark.sql(f'''",
            "MERGE INTO {TARGET_TABLE} AS target",
            "USING {SOURCE_VIEW} AS source",
            "ON {on_clause}",
            "WHEN MATCHED THEN UPDATE SET {assignments}",
            "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
            "''')",
        ]
    )


def _hash_diff_statement(contract: SemanticContract) -> str:
    merge_keys = tuple(contract.write.merge_keys)
    if not merge_keys:
        raise ValueError("Fabric Lakehouse hash_diff_upsert notebook runtime requires merge_keys")
    declared_hash_keys = tuple(contract.write.hash_keys)
    if contract.write.hash_strategy != "all_columns_except" and not declared_hash_keys:
        raise ValueError("Fabric Lakehouse hash_diff_upsert notebook runtime requires hash_keys")

    return "\n".join(
        [
            f"MERGE_KEYS = {json.dumps(list(merge_keys))}",
            f"HASH_STRATEGY = {json.dumps(contract.write.hash_strategy)}",
            f"DECLARED_HASH_KEYS = {json.dumps(list(declared_hash_keys))}",
            f"RESOLVED_HASH_EXCLUDE_COLUMNS = {json.dumps(list(resolved_hash_exclude_columns(contract)))}",
            "ROW_HASH_COLUMN = 'row_hash'",
            "",
            *_merge_key_guard_lines(contract.write.mode),
            "# Compute a deterministic content row_hash to skip no-op updates.",
            "hash_keys = df.columns if HASH_STRATEGY == 'all_columns_except' else DECLARED_HASH_KEYS",
            "missing_hash_columns = [column for column in hash_keys if column not in df.columns]",
            "if missing_hash_columns:",
            "    raise ValueError(f'Missing hash_keys in source DataFrame: {missing_hash_columns}')",
            "hash_excluded = set(MERGE_KEYS) | set(RESOLVED_HASH_EXCLUDE_COLUMNS)",
            "hash_input_columns = [column for column in hash_keys if column not in hash_excluded]",
            "if not hash_input_columns:",
            "    raise ValueError('hash_diff_upsert requires at least one stable non-key hash column after exclusions')",
            f"hash_payload = [F.coalesce(F.col(column).cast('string'), F.lit({HASH_NULL_SENTINEL!r})) for column in hash_input_columns]",
            f"df = df.withColumn(ROW_HASH_COLUMN, F.sha2(F.concat_ws({HASH_DELIMITER!r}, *hash_payload), 256))",
            "globals()['_cf_hash_input_columns'] = list(hash_input_columns)",
            "",
            "if not spark.catalog.tableExists(TARGET_TABLE):",
            '    df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)',
            "else:",
            "    SOURCE_VIEW = 'contractforge_source'",
            "    TARGET_HASH_VIEW = 'contractforge_target_hashes'",
            "    target_columns = [field.name for field in spark.table(TARGET_TABLE).schema.fields]",
            "    target_projection_columns = [column for column in [*MERGE_KEYS, ROW_HASH_COLUMN] if column in target_columns]",
            "    if ROW_HASH_COLUMN in target_projection_columns and all(key in target_projection_columns for key in MERGE_KEYS):",
            "        quoted_projection = ', '.join(_cf_quote_identifier(column) for column in target_projection_columns)",
            "        spark.sql(f'SELECT {quoted_projection} FROM {TARGET_TABLE}').createOrReplaceTempView(TARGET_HASH_VIEW)",
            "        df.createOrReplaceTempView(SOURCE_VIEW)",
            "        join_condition = ' AND '.join(",
            "            f'source.{_cf_quote_identifier(key)} = target_hash.{_cf_quote_identifier(key)}'",
            "            for key in MERGE_KEYS",
            "        )",
            "        row_hash_identifier = _cf_quote_identifier(ROW_HASH_COLUMN)",
            "        df = spark.sql(f'''",
            "            SELECT source.*",
            "            FROM {SOURCE_VIEW} AS source",
            "            LEFT JOIN {TARGET_HASH_VIEW} AS target_hash",
            "            ON {join_condition}",
            "            WHERE target_hash.{row_hash_identifier} IS NULL",
            "               OR target_hash.{row_hash_identifier} <> source.{row_hash_identifier}",
            "        ''')",
            "    _cf_hash_diff_candidate_count = int(df.count())",
            "    globals()['_cf_hash_diff_candidate_rows'] = _cf_hash_diff_candidate_count",
            "    if _cf_hash_diff_candidate_count > 0:",
            "        df.createOrReplaceTempView(SOURCE_VIEW)",
            "        columns = df.columns",
            "        on_clause = ' AND '.join(",
            "            f'target.{_cf_quote_identifier(key)} = source.{_cf_quote_identifier(key)}'",
            "            for key in MERGE_KEYS",
            "        )",
            "        assignments = ', '.join(",
            "            f'target.{_cf_quote_identifier(column)} = source.{_cf_quote_identifier(column)}'",
            "            for column in columns",
            "        )",
            "        insert_columns = ', '.join(_cf_quote_identifier(column) for column in columns)",
            "        insert_values = ', '.join(f'source.{_cf_quote_identifier(column)}' for column in columns)",
            "        row_hash_identifier = _cf_quote_identifier(ROW_HASH_COLUMN)",
            "        spark.sql(f'''",
            "MERGE INTO {TARGET_TABLE} AS target",
            "USING {SOURCE_VIEW} AS source",
            "ON {on_clause}",
            "WHEN MATCHED AND (target.{row_hash_identifier} IS NULL OR target.{row_hash_identifier} <> source.{row_hash_identifier}) THEN UPDATE SET {assignments}",
            "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
            "''')",
        ]
    )


def _snapshot_soft_delete_statement(contract: SemanticContract) -> str:
    merge_keys = tuple(contract.write.merge_keys)
    if not merge_keys:
        raise ValueError("Fabric Lakehouse snapshot_reconcile_soft_delete notebook runtime requires merge_keys")

    return "\n".join(
        [
            f"MERGE_KEYS = {json.dumps(list(merge_keys))}",
            f"RESOLVED_HASH_EXCLUDE_COLUMNS = {json.dumps(list(resolved_hash_exclude_columns(contract)))}",
            "ROW_HASH_COLUMN = 'row_hash'",
            "IS_ACTIVE_COLUMN = 'is_active'",
            "DELETED_AT_COLUMN = 'deleted_at'",
            "",
            *_merge_key_guard_lines(contract.write.mode),
            "# Stage a complete source snapshot with soft-delete metadata.",
            "snapshot_hash_excluded = set(MERGE_KEYS) | set(RESOLVED_HASH_EXCLUDE_COLUMNS)",
            "snapshot_hash_input_columns = [column for column in df.columns if column not in snapshot_hash_excluded]",
            "if not snapshot_hash_input_columns:",
            "    raise ValueError('snapshot_reconcile_soft_delete requires at least one stable non-key hash column after exclusions')",
            f"snapshot_hash_payload = [F.coalesce(F.col(column).cast('string'), F.lit({HASH_NULL_SENTINEL!r})) for column in snapshot_hash_input_columns]",
            f"df = df.withColumn(ROW_HASH_COLUMN, F.sha2(F.concat_ws({HASH_DELIMITER!r}, *snapshot_hash_payload), 256))",
            "df = df.withColumn(IS_ACTIVE_COLUMN, F.lit(True))",
            "df = df.withColumn(DELETED_AT_COLUMN, F.lit(None).cast('timestamp'))",
            "globals()['_cf_snapshot_hash_input_columns'] = list(snapshot_hash_input_columns)",
            "",
            "if not spark.catalog.tableExists(TARGET_TABLE):",
            '    df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)',
            "else:",
            "    SOURCE_VIEW = 'contractforge_snapshot_source'",
            "    df.createOrReplaceTempView(SOURCE_VIEW)",
            "    columns = df.columns",
            "    on_clause = ' AND '.join(",
            "        f'target.{_cf_quote_identifier(key)} = source.{_cf_quote_identifier(key)}'",
            "        for key in MERGE_KEYS",
            "    )",
            "    update_columns = [column for column in columns if column not in MERGE_KEYS]",
            "    assignments = ', '.join(",
            "        f'target.{_cf_quote_identifier(column)} = source.{_cf_quote_identifier(column)}'",
            "        for column in update_columns",
            "    )",
            "    insert_columns = ', '.join(_cf_quote_identifier(column) for column in columns)",
            "    insert_values = ', '.join(f'source.{_cf_quote_identifier(column)}' for column in columns)",
            "    row_hash_identifier = _cf_quote_identifier(ROW_HASH_COLUMN)",
            "    is_active_identifier = _cf_quote_identifier(IS_ACTIVE_COLUMN)",
            "    deleted_at_identifier = _cf_quote_identifier(DELETED_AT_COLUMN)",
            "    spark.sql(f'''",
            "MERGE INTO {TARGET_TABLE} AS target",
            "USING {SOURCE_VIEW} AS source",
            "ON {on_clause}",
            "WHEN MATCHED AND (target.{row_hash_identifier} IS NULL OR target.{row_hash_identifier} <> source.{row_hash_identifier} OR target.{is_active_identifier} = false) THEN UPDATE SET {assignments}",
            "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
            "WHEN NOT MATCHED BY SOURCE AND target.{is_active_identifier} = true THEN UPDATE SET",
            "  target.{is_active_identifier} = false,",
            "  target.{deleted_at_identifier} = current_timestamp()",
            "''')",
        ]
    )


def _scd2_historical_statement(contract: SemanticContract) -> str:
    merge_keys = tuple(contract.write.merge_keys)
    if not merge_keys:
        raise ValueError("Fabric Lakehouse historical notebook runtime requires merge_keys")

    return "\n".join(
        [
            f"MERGE_KEYS = {json.dumps(list(merge_keys))}",
            f"SCD2_CHANGE_COLUMNS = {json.dumps(list(contract.write.scd2_change_columns))}",
            f"SCD2_EFFECTIVE_FROM_COLUMN = {json.dumps(contract.write.scd2_effective_from_column)}",
            f"SCD2_SEQUENCE_BY = {json.dumps(contract.write.scd2_sequence_by)}",
            f"SCD2_LATE_ARRIVING_POLICY = {json.dumps(contract.write.scd2_late_arriving_policy)}",
            f"RESOLVED_HASH_EXCLUDE_COLUMNS = {json.dumps(list(resolved_hash_exclude_columns(contract)))}",
            "ROW_HASH_COLUMN = 'row_hash'",
            "VALID_FROM_COLUMN = 'valid_from'",
            "VALID_TO_COLUMN = 'valid_to'",
            "IS_CURRENT_COLUMN = 'is_current'",
            "CHANGED_COLUMNS_COLUMN = 'changed_columns'",
            "",
            *_merge_key_guard_lines(contract.write.mode),
            "# Stage source rows for SCD2 historical merge.",
            "if SCD2_SEQUENCE_BY and SCD2_SEQUENCE_BY not in df.columns:",
            "    raise ValueError(f'historical source is missing scd2_sequence_by: {SCD2_SEQUENCE_BY}')",
            "source_data_columns = list(df.columns)",
            "change_columns = SCD2_CHANGE_COLUMNS or [",
            "    column for column in source_data_columns",
            "    if column not in set(MERGE_KEYS) | set(RESOLVED_HASH_EXCLUDE_COLUMNS)",
            "]",
            "missing_change_columns = [column for column in change_columns if column not in df.columns]",
            "if missing_change_columns:",
            "    raise ValueError(f'historical source is missing scd2_change_columns: {missing_change_columns}')",
            "if not change_columns:",
            "    raise ValueError('historical requires at least one stable non-key change column')",
            f"scd2_hash_payload = [F.coalesce(F.col(column).cast('string'), F.lit({HASH_NULL_SENTINEL!r})) for column in change_columns]",
            f"df = df.withColumn(ROW_HASH_COLUMN, F.sha2(F.concat_ws({HASH_DELIMITER!r}, *scd2_hash_payload), 256))",
            "if SCD2_EFFECTIVE_FROM_COLUMN:",
            "    if SCD2_EFFECTIVE_FROM_COLUMN not in df.columns:",
            "        raise ValueError(f'historical source is missing scd2_effective_from_column: {SCD2_EFFECTIVE_FROM_COLUMN}')",
            "    df = df.withColumn(VALID_FROM_COLUMN, F.col(SCD2_EFFECTIVE_FROM_COLUMN).cast('timestamp'))",
            "else:",
            "    df = df.withColumn(VALID_FROM_COLUMN, F.current_timestamp())",
            "df = df.withColumn(VALID_TO_COLUMN, F.lit(None).cast('timestamp'))",
            "df = df.withColumn(IS_CURRENT_COLUMN, F.lit(True))",
            "df = df.withColumn(CHANGED_COLUMNS_COLUMN, F.lit(None).cast('string'))",
            "globals()['_cf_scd2_change_columns'] = list(change_columns)",
            "",
            "if not spark.catalog.tableExists(TARGET_TABLE):",
            '    df.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)',
            "else:",
            "    SOURCE_VIEW = 'contractforge_scd2_source'",
            "    STAGE_VIEW = 'contractforge_scd2_stage'",
            "    df.createOrReplaceTempView(SOURCE_VIEW)",
            "    target_keys = ', '.join(_cf_quote_identifier(key) for key in MERGE_KEYS)",
            "    sequence_select = f', {_cf_quote_identifier(SCD2_SEQUENCE_BY)} AS __tgt_sequence' if SCD2_SEQUENCE_BY else ''",
            "    key_join = ' AND '.join(",
            "        f'target_current.{_cf_quote_identifier(key)} <=> source.{_cf_quote_identifier(key)}'",
            "        for key in MERGE_KEYS",
            "    )",
            "    data_columns = df.columns",
            "    select_data = ', '.join(f'source.{_cf_quote_identifier(column)}' for column in data_columns)",
            "    null_merge_keys = ', '.join(f'NULL AS {_cf_quote_identifier(\"__merge_key_\" + key)}' for key in MERGE_KEYS)",
            "    update_merge_keys = ', '.join(f'{_cf_quote_identifier(key)} AS {_cf_quote_identifier(\"__merge_key_\" + key)}' for key in MERGE_KEYS)",
            "    stage_columns = ', '.join(_cf_quote_identifier(column) for column in [*data_columns, *(f'__merge_key_{key}' for key in MERGE_KEYS)])",
            "    late_filter = 'true'",
            "    if SCD2_SEQUENCE_BY and SCD2_LATE_ARRIVING_POLICY in {'ignore', 'reject'}:",
            "        seq = _cf_quote_identifier(SCD2_SEQUENCE_BY)",
            "        late_condition = f'__tgt_sequence IS NOT NULL AND ({seq} IS NULL OR {seq} <= __tgt_sequence)'",
            "        if SCD2_LATE_ARRIVING_POLICY == 'ignore':",
            "            late_filter = f'NOT ({late_condition})'",
            "        else:",
            "            late_count = spark.sql(f'''",
            "                SELECT count(*) AS late_count",
            "                FROM {SOURCE_VIEW} source",
            "                INNER JOIN (",
            "                  SELECT {target_keys}, {_cf_quote_identifier(SCD2_SEQUENCE_BY)} AS __tgt_sequence",
            "                  FROM {TARGET_TABLE}",
            "                  WHERE {_cf_quote_identifier(IS_CURRENT_COLUMN)} = true",
            "                ) target_current",
            "                ON {key_join}",
            "                WHERE {late_condition}",
            "            ''').collect()[0]['late_count']",
            "            if int(late_count or 0) > 0:",
            "                raise ValueError('historical rejected late-arriving rows')",
            "    spark.sql(f'''",
            "CREATE OR REPLACE TEMP VIEW {STAGE_VIEW} AS",
            "WITH target_current AS (",
            "  SELECT {target_keys}, {_cf_quote_identifier(ROW_HASH_COLUMN)} AS __tgt_row_hash{sequence_select}",
            "  FROM {TARGET_TABLE}",
            "  WHERE {_cf_quote_identifier(IS_CURRENT_COLUMN)} = true",
            "), joined AS (",
            "  SELECT {select_data}, target_current.__tgt_row_hash{', target_current.__tgt_sequence' if SCD2_SEQUENCE_BY else ''}",
            "  FROM {SOURCE_VIEW} source",
            "  LEFT JOIN target_current",
            "  ON {key_join}",
            "), changed AS (",
            "  SELECT * FROM joined",
            "  WHERE {late_filter}",
            "    AND (__tgt_row_hash IS NULL OR NOT ({_cf_quote_identifier(ROW_HASH_COLUMN)} <=> __tgt_row_hash))",
            "), insert_stage AS (",
            "  SELECT {', '.join(_cf_quote_identifier(column) for column in data_columns)}, {null_merge_keys}",
            "  FROM changed",
            "), update_stage AS (",
            "  SELECT {', '.join(_cf_quote_identifier(column) for column in data_columns)}, {update_merge_keys}",
            "  FROM changed WHERE __tgt_row_hash IS NOT NULL",
            ")",
            "SELECT {stage_columns} FROM insert_stage",
            "UNION ALL",
            "SELECT {stage_columns} FROM update_stage",
            "''')",
            "    target_insert_columns = data_columns",
            "    on_clause = ' AND '.join(",
            "        f'target.{_cf_quote_identifier(key)} <=> source.{_cf_quote_identifier(\"__merge_key_\" + key)}'",
            "        for key in MERGE_KEYS",
            "    )",
            "    insert_columns = ', '.join(_cf_quote_identifier(column) for column in target_insert_columns)",
            "    insert_values = ', '.join(f'source.{_cf_quote_identifier(column)}' for column in target_insert_columns)",
            "    changed_candidates = [",
            "        column for column in target_insert_columns",
            "        if column not in set(MERGE_KEYS) | {VALID_FROM_COLUMN, VALID_TO_COLUMN, IS_CURRENT_COLUMN, ROW_HASH_COLUMN, CHANGED_COLUMNS_COLUMN}",
            "    ]",
            "    changed_expr = \"source.\" + _cf_quote_identifier(CHANGED_COLUMNS_COLUMN)",
            "    if changed_candidates:",
            "        changed_expr = 'concat_ws(\\',\\', ' + ', '.join(",
            "            f\"CASE WHEN NOT (target.{_cf_quote_identifier(column)} <=> source.{_cf_quote_identifier(column)}) THEN '{column}' ELSE NULL END\"",
            "            for column in changed_candidates",
            "        ) + ')'",
            "    spark.sql(f'''",
            "MERGE INTO {TARGET_TABLE} AS target",
            "USING {STAGE_VIEW} AS source",
            "ON {on_clause} AND target.{_cf_quote_identifier(IS_CURRENT_COLUMN)} = true",
            "WHEN MATCHED AND target.{_cf_quote_identifier(ROW_HASH_COLUMN)} <> source.{_cf_quote_identifier(ROW_HASH_COLUMN)} THEN UPDATE SET",
            "  target.{_cf_quote_identifier(VALID_TO_COLUMN)} = current_timestamp(),",
            "  target.{_cf_quote_identifier(IS_CURRENT_COLUMN)} = false,",
            "  target.{_cf_quote_identifier(CHANGED_COLUMNS_COLUMN)} = {changed_expr}",
            "WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})",
            "''')",
        ]
    )


def _merge_key_guard_lines(write_mode: str) -> list[str]:
    return [
        "def _cf_quote_identifier(value):",
        "    return '`' + str(value).replace('`', '``') + '`'",
        "",
        "",
        "missing_merge_keys = [key for key in MERGE_KEYS if key not in df.columns]",
        "if missing_merge_keys:",
        "    raise ValueError(f'Missing merge_keys in source DataFrame: {missing_merge_keys}')",
        "",
        "null_merge_key_predicate = ' OR '.join(",
        "    f'{_cf_quote_identifier(key)} IS NULL' for key in MERGE_KEYS",
        ")",
        "if null_merge_key_predicate and df.filter(null_merge_key_predicate).limit(1).count() > 0:",
        f"    raise ValueError(f'{write_mode} source contains null merge_keys: {{MERGE_KEYS}}')",
        "",
        "duplicate_merge_keys = (",
        "    df.groupBy(*MERGE_KEYS)",
        "    .count()",
        "    .filter('`count` > 1')",
        "    .limit(1)",
        "    .count()",
        ")",
        "if duplicate_merge_keys:",
        f"    raise ValueError(f'{write_mode} source contains duplicate merge_keys: {{MERGE_KEYS}}')",
        "",
    ]
