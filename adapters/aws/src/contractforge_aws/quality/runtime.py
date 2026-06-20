"""Render native AWS Glue Data Quality evaluation with per-rule quality evidence.

The Glue job evaluates the contract's quality rules with ``EvaluateDataQuality``
against DQDL rulesets, appends one immutable row per rule to
``ctrl_ingestion_quality``, and enforces severity: any failed ``abort`` rule
raises; ``warn`` rules are recorded; row-level ``quarantine`` rules write
offending rows to ``ctrl_ingestion_quarantine`` and remove them from the
dataframe before the target write.
"""

from __future__ import annotations

from collections.abc import Sequence

from contractforge_core.semantic import QualityIntent, SemanticContract
from contractforge_aws.evidence.ddl import evidence_table_names, render_evidence_table_ddl
from contractforge_aws.quality.dqdl import render_quality_dqdl_rules, unmapped_quality_rules
from contractforge_aws.evidence.runtime import evidence_database
from contractforge_aws.rendering.names import iceberg_table_name
from contractforge_aws.quality.enforcement import partition_quality_rules
from contractforge_aws.quality.expression import (
    expression_quality_rules,
    render_expression_quality_blocks,
    runtime_unmapped_quality_rules,
)
from contractforge_aws.quality.quarantine import render_quarantine_block

_ABORT = "abort"


def can_render_quality_runtime(contract: SemanticContract) -> bool:
    """Quality is runtime-renderable when every rule maps to DQDL or Spark expression checks."""

    return not runtime_unmapped_quality_rules(contract.quality, unmapped_quality_rules(contract))


def has_quality_rules(contract: SemanticContract) -> bool:
    return bool(contract.quality)


def render_quality_evaluation(
    contract: SemanticContract,
    *,
    dataframe_name: str = "df",
    evidence_database_name: str | None = None,
) -> str:
    """Render the in-job Glue Data Quality evaluation block.

    Rules are partitioned by the enforcement actually applied:

    * ``abort`` -- evaluated on the input; any failure raises and fails the run.
    * ``quarantine`` -- only row-level rules; offending rows are written to the
      quarantine control table and dropped from the dataframe before the write.
    * recorded (``warn``) -- everything else (``warn`` severity, plus
      ``quarantine``-severity rules that are not row-level): recorded as quality
      evidence, never failing the run and never filtering rows.
    """

    expressions = expression_quality_rules(contract.quality)
    rules = partition_quality_rules(tuple(rule for rule in contract.quality if rule.rule != "expression"))
    database = evidence_database(contract, evidence_database_name)
    tables = evidence_table_names(database)
    quality_table = tables["quality"]
    quarantine_table = tables["quarantine"]
    target_table = iceberg_table_name(contract)

    lines = [
        "# Native Glue Data Quality evaluation with per-rule quality evidence.",
        "from awsglue.dynamicframe import DynamicFrame",
        "from awsglue.transforms import SelectFromCollection",
        "from awsgluedq.transforms import EvaluateDataQuality",
        f"spark.sql('CREATE DATABASE IF NOT EXISTS glue_catalog.`{database}`')",
        f"spark.sql('''{render_evidence_table_ddl('quality', database)}''')",
        "globals()['_cf_quality_status'] = globals().get('_cf_quality_status', 'PASSED')",
    ]
    if rules.quarantine or any(rule.severity == "quarantine" for rule in expressions):
        lines.append(f"spark.sql('''{render_evidence_table_ddl('quarantine', database)}''')")
    if rules.abort:
        lines += _eval_block(rules.abort, dataframe_name, quality_table, target_table, severity="abort", raise_on_fail=True)
    if rules.quarantine:
        lines += render_quarantine_block(rules.quarantine, dataframe_name, quality_table, quarantine_table, target_table)
    if rules.recorded:
        lines += _eval_block(rules.recorded, dataframe_name, quality_table, target_table, severity="warn", raise_on_fail=False)
    if expressions:
        lines += render_expression_quality_blocks(
            expressions,
            dataframe_name,
            quality_table,
            quarantine_table,
            target_table,
        )
    return "\n".join(lines)


def _eval_block(
    rules: Sequence[QualityIntent],
    dataframe_name: str,
    quality_table: str,
    target_table: str,
    *,
    severity: str,
    raise_on_fail: bool,
) -> list[str]:
    ruleset = render_quality_dqdl_rules(rules).rstrip()
    frame = f"_cf_dq_{severity}"
    outcomes = f"{frame}_outcomes"
    failed = f"{frame}_failed"
    status_on_fail = "FAILED" if raise_on_fail else "WARNED"
    block = [
        "",
        f"# Quality rules with '{severity}' enforcement.",
        f"{frame}_input = DynamicFrame.fromDF({dataframe_name}, glue_context, {frame!r})",
        f"{frame}_results = EvaluateDataQuality.apply(",
        f"    frame={frame}_input,",
        f"    ruleset='''{ruleset}''',",
        f"    publishing_options={{'dataQualityEvaluationContext': {frame!r}, 'enableDataQualityResultsPublishing': False}},",
        ")",
        f"{outcomes} = {frame}_results.toDF().collect()",
        f"_cf_persist_quality_evidence(spark, {quality_table!r}, _cf_run_id, {target_table!r}, {outcomes}, {severity!r})",
        f"{failed} = [_cf_r for _cf_r in {outcomes} if str(_cf_r['Outcome']).strip() != 'Passed']",
        f"if {failed}:",
        f"    _cf_update_quality_status({status_on_fail!r})",
    ]
    if raise_on_fail:
        block.append(f"    raise ValueError('Data quality (abort) failed: ' + str([_cf_r['Rule'] for _cf_r in {failed}]))")
    else:
        block.append(f"    print('Data quality (warn) failures recorded: ' + str([_cf_r['Rule'] for _cf_r in {failed}]))")
    return block


def render_quality_evidence_helper() -> str:
    """Render the Glue-runtime ``_cf_persist_quality_evidence`` helper definition."""

    return "\n".join(
        [
            "def _cf_persist_quality_evidence(spark, quality_table, run_id, target_table, outcomes, severity):",
            '    """Append one immutable quality-evidence row per evaluated rule (append-only)."""',
            "    import datetime as _dt",
            "    import json",
            "",
            "    def _q(value):",
            "        if value is None:",
            "            return 'NULL'",
            '        return "\'" + str(value).replace("\'", "\'\'") + "\'"',
            "",
            "    checked_at = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')",
            "    for outcome in outcomes:",
            "        record = outcome.asDict() if hasattr(outcome, 'asDict') else dict(outcome)",
            "        passed = str(record.get('Outcome')).strip() == 'Passed'",
            "        row = {",
            "            'run_id': _q(run_id),",
            "            'target_table': _q(target_table),",
            "            'rule_name': _q(record.get('Rule')),",
            "            'status': _q('PASSED' if passed else 'FAILED'),",
            "            'severity': _q(severity),",
            "            'failed_count': '0' if passed else '1',",
            "            'observed_value': _q(record.get('EvaluatedMetrics')),",
            '            \'checked_at_utc\': "CAST(\'" + checked_at + "\' AS TIMESTAMP)",',
            "            'message': _q(record.get('FailureReason')),",
            "            'details_json': _q(json.dumps({str(k): str(v) for k, v in record.items()}, sort_keys=True)),",
            "        }",
            "        columns_sql = ', '.join('`' + key + '`' for key in row)",
            "        values_sql = ', '.join(row[key] for key in row)",
            "        spark.sql('INSERT INTO ' + quality_table + ' (' + columns_sql + ') VALUES (' + values_sql + ')')",
            "",
            "def _cf_update_quality_status(status):",
            "    precedence = {'NOT_CONFIGURED': 0, 'PASSED': 1, 'WARNED': 2, 'QUARANTINED': 3, 'FAILED': 4}",
            "    current = globals().get('_cf_quality_status', 'PASSED')",
            "    if precedence.get(status, 0) > precedence.get(current, 0):",
            "        globals()['_cf_quality_status'] = status",
            "",
        ]
    )
