"""Glue job review outline reason derivation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from contractforge_core.planner import ExecutionPlan
from contractforge_core.semantic import SemanticContract
from contractforge_aws.quality.dqdl import unmapped_quality_rules
from contractforge_aws.preparation import can_render_preparation
from contractforge_aws.quality.expression import runtime_unmapped_quality_rules
from contractforge_aws.quality.runtime import can_render_quality_runtime
from contractforge_aws.sources import can_render_source


@dataclass(frozen=True)
class GlueJobOutlineContext:
    contract: SemanticContract
    plan: ExecutionPlan | None


@dataclass(frozen=True)
class GlueJobOutlineRule:
    condition: Callable[[GlueJobOutlineContext], bool]
    reason: Callable[[GlueJobOutlineContext], str]


def render_glue_job_outline(contract: SemanticContract, plan: ExecutionPlan | None) -> str:
    context = GlueJobOutlineContext(contract=contract, plan=plan)
    target = f"`{contract.target.namespace or 'default'}.{contract.target.name}`"
    steps = ", ".join(step.name for step in plan.steps) if plan else "no executable plan"
    return (
        "# AWS Glue Job Outline\n\n"
        f"{_outline_reason(context)}\n\n"
        f"- Target: {target}\n"
        "- Table format: Apache Iceberg\n"
        "- Catalog: AWS Glue Catalog\n"
        "- Evidence store: ContractForge evidence tables on Iceberg/S3\n"
        f"- Abstract steps: {steps}\n"
    )


def _outline_reason(context: GlueJobOutlineContext) -> str:
    return next(
        (rule.reason(context) for rule in _OUTLINE_RULES if rule.condition(context)),
        _default_reason(context),
    )


def _source_not_renderable(context: GlueJobOutlineContext) -> bool:
    return not can_render_source(context.contract.source.raw or {})


def _preparation_not_renderable(context: GlueJobOutlineContext) -> bool:
    return can_render_source(context.contract.source.raw or {}) and not can_render_preparation(context.contract)


def _quality_not_renderable(context: GlueJobOutlineContext) -> bool:
    return (
        can_render_source(context.contract.source.raw or {})
        and can_render_preparation(context.contract)
        and not can_render_quality_runtime(context.contract)
    )


def _default_reason(_context: GlueJobOutlineContext) -> str:
    return (
        "Runtime generation is implemented for `scd0_append`, `scd0_overwrite`, "
        "`scd1_upsert` and `scd1_hash_diff`."
    )


def _source_reason(_context: GlueJobOutlineContext) -> str:
    return (
        "Runtime generation is blocked because the source connector is not rendered by the AWS adapter yet. "
        "JDBC, catalog (`table`/`view`/`sql`), file/object-storage, `http_file`, `rest_api`, bounded Kafka/Event Hubs, "
        "`delta_share` and `incremental_files` sources are renderable; available_now streams render with a "
        "checkpoint and append/merge write modes; `native_passthrough` remains review-only."
    )


def _preparation_reason(_context: GlueJobOutlineContext) -> str:
    return (
        "Runtime generation is blocked because the contract contains shape or transform semantics that the "
        "AWS renderer cannot preserve yet. Top-level `select_columns`, `column_mapping`, `filter_expression`, "
        "portable `transform.cast`, `transform.standardize`, `transform.derive`, `transform.composite_keys`, "
        "`transform.deduplicate`, `shape.parse_json` (with a concrete schema), `shape.arrays`, `shape.columns` "
        "and `shape.flatten` are renderable. `shape.arrays` explode/explode_outer is blocked in the bronze layer "
        "unless `allow_cardinality_change_on_bronze` is set, and sibling explodes need `allow_cartesian`; "
        "`shape.zip_arrays` is renderable through Spark `arrays_zip` plus field renaming."
    )


def _quality_reason(context: GlueJobOutlineContext) -> str:
    unmapped_names = runtime_unmapped_quality_rules(context.contract.quality, unmapped_quality_rules(context.contract))
    unmapped = ", ".join(f"`{name}`" for name in unmapped_names) or "the listed rules"
    return (
        "Runtime generation is blocked because the contract contains quality rules with no faithful AWS Glue Data "
        "Quality (DQDL) equivalent and cannot be evaluated natively yet: " + unmapped + ". "
        "`required_columns`, `not_null`, `unique_key`, `row_count_minimum`, `accepted_values`, `max_null_ratio` "
        "and Spark SQL `expression` rules are evaluated in the Glue job, with `abort` rules failing the run and "
        "`warn`/`quarantine` rules recorded as quality evidence."
    )


_OUTLINE_RULES = (
    GlueJobOutlineRule(_source_not_renderable, _source_reason),
    GlueJobOutlineRule(_preparation_not_renderable, _preparation_reason),
    GlueJobOutlineRule(_quality_not_renderable, _quality_reason),
)
