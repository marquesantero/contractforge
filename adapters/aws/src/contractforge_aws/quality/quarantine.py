"""Quarantine block rendering for AWS Glue Data Quality."""

from __future__ import annotations

from collections.abc import Sequence

from contractforge_core.semantic import QualityIntent
from contractforge_aws.quality.dqdl import render_quality_dqdl_rules

_CF_DQ_ROW_COLUMNS = "['DataQualityRulesPass', 'DataQualityRulesFail', 'DataQualityRulesSkip', 'DataQualityEvaluationResult']"


def render_quarantine_block(
    rules: Sequence[QualityIntent],
    dataframe_name: str,
    quality_table: str,
    quarantine_table: str,
    target_table: str,
) -> list[str]:
    ruleset = render_quality_dqdl_rules(rules).rstrip()
    frame = "_cf_dq_quarantine"
    return [
        "",
        "# Quality rules with 'quarantine' enforcement (row-level): offending rows are",
        "# recorded to the quarantine control table and removed from the write.",
        "from pyspark.sql import functions as _cf_F",
        f"{frame}_input = DynamicFrame.fromDF({dataframe_name}, glue_context, {frame!r})",
        f"{frame}_results = EvaluateDataQuality().process_rows(",
        f"    frame={frame}_input,",
        f"    ruleset='''{ruleset}''',",
        f"    publishing_options={{'dataQualityEvaluationContext': {frame!r}, 'enableDataQualityResultsPublishing': False}},",
        "    additional_options={'performanceTuning.caching': 'CACHE_NOTHING'},",
        ")",
        f"{frame}_outcomes = SelectFromCollection.apply(dfc={frame}_results, key='ruleOutcomes', transformation_ctx='{frame}_outcomes').toDF().collect()",
        f"_cf_persist_quality_evidence(spark, {quality_table!r}, _cf_run_id, {target_table!r}, {frame}_outcomes, 'quarantine')",
        f"{frame}_rows = SelectFromCollection.apply(dfc={frame}_results, key='rowLevelOutcomes', transformation_ctx='{frame}_rows').toDF()",
        f"_cf_dq_row_columns = {_CF_DQ_ROW_COLUMNS}",
        f"_cf_payload_columns = [_cf_c for _cf_c in {frame}_rows.columns if _cf_c not in _cf_dq_row_columns]",
        f"{frame}_failed = {frame}_rows.filter(\"DataQualityEvaluationResult = 'Failed'\").select(",
        "    _cf_F.lit(_cf_run_id).alias('run_id'),",
        f"    _cf_F.lit({target_table!r}).alias('target_table'),",
        "    _cf_F.concat_ws(', ', _cf_F.col('DataQualityRulesFail')).alias('rule_name'),",
        "    _cf_F.lit(None).cast('string').alias('error_reason'),",
        "    _cf_F.to_json(_cf_F.struct(*[_cf_F.col(_cf_c) for _cf_c in _cf_payload_columns])).alias('record_payload'),",
        "    _cf_F.lit(None).cast('string').alias('record_ref'),",
        "    _cf_F.concat_ws(', ', _cf_F.col('DataQualityRulesFail')).alias('reason'),",
        "    _cf_F.current_timestamp().alias('quarantined_at_utc'),",
        ")",
        f"_cf_rows_quarantined_current = {frame}_failed.count()",
        "_cf_rows_quarantined = int(globals().get('_cf_rows_quarantined', 0)) + int(_cf_rows_quarantined_current)",
        "globals()['_cf_rows_quarantined'] = _cf_rows_quarantined",
        "if _cf_rows_quarantined_current:",
        "    _cf_update_quality_status('QUARANTINED')",
        f"{frame}_failed.writeTo({quarantine_table!r}).append()",
        f"{dataframe_name} = {frame}_rows.filter(\"DataQualityEvaluationResult = 'Passed'\").drop(*_cf_dq_row_columns)",
    ]
