from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.planner import plan_contract
from contractforge_core.semantic import (
    GovernanceIntent,
    OperationsIntent,
    QualityIntent,
    SemanticContract,
    ShapeIntent,
    SourceIntent,
    TargetIntent,
    TransformIntent,
    WriteIntent,
)


def contract_for(mode: str, **kwargs) -> SemanticContract:
    if mode in {"scd1_upsert", "snapshot_soft_delete", "scd2_historical"}:
        kwargs.setdefault("merge_keys", ("order_id",))
    if mode == "scd1_hash_diff":
        kwargs.setdefault("hash_keys", ("order_id",))
    source_raw = {"read": {"source_complete": True}} if mode == "snapshot_soft_delete" else None
    return SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage", location="s3://landing/orders", raw=source_raw),
        target=TargetIntent(name="orders", layer="bronze", namespace="sales"),
        write=WriteIntent(mode=mode, **kwargs),
    )


FULL_FEATURE = PlatformCapabilities(
    platform="full-feature-test",
    supports_append=True,
    supports_overwrite=True,
    supports_merge=True,
    supports_hash_diff=True,
    supports_scd2=True,
    supports_snapshot_soft_delete=True,
    supports_schema_evolution=True,
    supports_row_filters=True,
    supports_column_masks=True,
    supports_available_now_streaming=True,
    supports_expression_quality=True,
    supports_shape=True,
    supports_transform=True,
    evidence_stores=("audit_tables",),
)

APPEND_ONLY = PlatformCapabilities(
    platform="append-only-test",
    supports_append=True,
    evidence_stores=("audit_files",),
)


def test_append_supported_on_limited_adapter() -> None:
    result = plan_contract(contract_for("scd0_append"), APPEND_ONLY)

    assert result.status == "SUPPORTED"
    assert result.plan is not None


def test_overwrite_requires_capability() -> None:
    result = plan_contract(contract_for("scd0_overwrite"), APPEND_ONLY)

    assert result.status == "UNSUPPORTED"
    assert result.plan is None
    assert [blocker.code for blocker in result.blockers] == ["OVERWRITE_UNSUPPORTED"]


def test_scd1_requires_merge_capability() -> None:
    result = plan_contract(contract_for("scd1_upsert"), APPEND_ONLY)

    assert result.status == "UNSUPPORTED"
    assert "MERGE_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_scd1_supported_on_full_feature_adapter() -> None:
    result = plan_contract(contract_for("scd1_upsert"), FULL_FEATURE)

    assert result.status == "SUPPORTED"
    assert result.plan is not None


def test_merge_modes_require_merge_keys_before_adapter_capabilities() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="scd1_upsert"),
    )

    result = plan_contract(contract, FULL_FEATURE)

    assert result.status == "UNSUPPORTED"
    assert [blocker.code for blocker in result.blockers] == ["MERGE_KEYS_REQUIRED"]


def test_scd1_hash_diff_requires_explicit_hash_diff_capability() -> None:
    merge_only = PlatformCapabilities(
        platform="merge-only-test",
        supports_append=True,
        supports_merge=True,
        evidence_stores=("audit_tables",),
    )

    result = plan_contract(contract_for("scd1_hash_diff"), merge_only)

    assert result.status == "UNSUPPORTED"
    assert "HASH_DIFF_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_hash_diff_requires_hash_keys_before_adapter_capabilities() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="scd1_hash_diff"),
    )

    result = plan_contract(contract, FULL_FEATURE)

    assert result.status == "UNSUPPORTED"
    assert [blocker.code for blocker in result.blockers] == ["HASH_KEYS_REQUIRED"]


def test_hash_diff_all_columns_except_strategy_does_not_require_hash_keys() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(
            mode="scd1_hash_diff",
            merge_keys=("order_id",),
            hash_strategy="all_columns_except",
            hash_exclude_columns=("updated_at",),
        ),
    )

    result = plan_contract(contract, FULL_FEATURE)

    assert result.status == "SUPPORTED"


def test_snapshot_soft_delete_requires_platform_capability() -> None:
    result = plan_contract(contract_for("snapshot_soft_delete"), APPEND_ONLY)

    assert result.status == "UNSUPPORTED"
    assert "SNAPSHOT_SOFT_DELETE_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_snapshot_soft_delete_requires_complete_snapshot_declaration() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="snapshot_soft_delete", merge_keys=("order_id",)),
    )

    result = plan_contract(contract, FULL_FEATURE)

    assert result.status == "UNSUPPORTED"
    assert [blocker.code for blocker in result.blockers] == ["SNAPSHOT_SOURCE_COMPLETE_REQUIRED"]


def test_snapshot_soft_delete_can_be_marked_review_required() -> None:
    capabilities = PlatformCapabilities(
        platform="snapshot-review-test",
        supports_append=True,
        evidence_stores=("audit_tables",),
        review_required_semantics=("snapshot_soft_delete",),
    )

    result = plan_contract(contract_for("snapshot_soft_delete"), capabilities)

    assert result.status == "REVIEW_REQUIRED"
    assert result.plan is not None


def test_additive_schema_without_evolution_returns_warning() -> None:
    result = plan_contract(contract_for("scd0_append", schema_policy="additive_only"), APPEND_ONLY)

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert [warning.code for warning in result.warnings] == ["SCHEMA_EVOLUTION_UNAVAILABLE"]


def test_row_filters_require_governance_capability() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="customers_raw", kind="object_storage"),
        target=TargetIntent(name="customers", layer="silver"),
        write=WriteIntent(mode="scd0_append"),
        governance=GovernanceIntent(row_filters=("country = 'BR'",)),
    )

    result = plan_contract(contract, APPEND_ONLY)

    assert result.status == "UNSUPPORTED"
    assert "ROW_FILTERS_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_available_now_can_require_review() -> None:
    capabilities = PlatformCapabilities(
        platform="review-streaming-test",
        supports_append=True,
        evidence_stores=("audit_tables",),
        review_required_semantics=("available_now_streaming",),
    )
    contract = SemanticContract(
        source=SourceIntent(name="events_raw", kind="object_storage"),
        target=TargetIntent(name="events", layer="bronze"),
        write=WriteIntent(mode="scd0_append"),
        operations=OperationsIntent(available_now_streaming=True),
    )

    result = plan_contract(contract, capabilities)

    assert result.status == "REVIEW_REQUIRED"
    assert result.plan is not None


def test_production_evidence_store_is_required() -> None:
    capabilities = PlatformCapabilities(platform="no-evidence-test", supports_append=True)

    result = plan_contract(contract_for("scd0_append"), capabilities)

    assert result.status == "UNSUPPORTED"
    assert [blocker.code for blocker in result.blockers] == ["EVIDENCE_STORE_REQUIRED"]


def test_expression_quality_requires_capability() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="scd0_append"),
        quality=(QualityIntent(name="positive_amount", rule="expression", value="amount > 0"),),
    )

    result = plan_contract(contract, APPEND_ONLY)

    assert result.status == "UNSUPPORTED"
    assert "QUALITY_EXPRESSION_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_expression_quality_can_be_review_required() -> None:
    capabilities = PlatformCapabilities(
        platform="quality-review-test",
        supports_append=True,
        evidence_stores=("audit_tables",),
        review_required_semantics=("quality_rules.expression",),
    )
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="scd0_append"),
        quality=(QualityIntent(name="positive_amount", rule="expression", value="amount > 0"),),
    )

    result = plan_contract(contract, capabilities)

    assert result.status == "REVIEW_REQUIRED"
    assert result.plan is not None


def test_shape_requires_adapter_capability() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="scd0_append"),
        shape=ShapeIntent(raw={"flatten": True}),
    )

    result = plan_contract(contract, APPEND_ONLY)

    assert result.status == "UNSUPPORTED"
    assert "SHAPE_UNSUPPORTED" in {blocker.code for blocker in result.blockers}


def test_transform_without_capability_returns_warning() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="scd0_append"),
        transform=TransformIntent(raw={"derive": {"loaded_at": "current_timestamp()"}}),
    )

    result = plan_contract(contract, APPEND_ONLY)

    assert result.status == "SUPPORTED_WITH_WARNINGS"
    assert "TRANSFORM_SUPPORT_UNKNOWN" in {warning.code for warning in result.warnings}


def test_plan_includes_shape_transform_and_quality_steps_when_supported() -> None:
    contract = SemanticContract(
        source=SourceIntent(name="orders_raw", kind="object_storage"),
        target=TargetIntent(name="orders", layer="silver"),
        write=WriteIntent(mode="scd0_append"),
        quality=(QualityIntent(name="id_not_null", rule="not_null", columns=("id",)),),
        shape=ShapeIntent(raw={"flatten": True}),
        transform=TransformIntent(raw={"derive": {"loaded_at": "current_timestamp()"}}),
    )

    result = plan_contract(contract, FULL_FEATURE)

    assert result.status == "SUPPORTED"
    assert result.plan is not None
    assert [step.name for step in result.plan.steps] == [
        "read_source",
        "shape",
        "transform",
        "quality",
        "write_target",
        "record_evidence",
    ]
