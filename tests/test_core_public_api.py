from contractforge_core import (
    AccessContractModel,
    AccessGrantContractModel,
    AnnotationsContractModel,
    CapabilityEvidence,
    ColumnAnnotationsContractModel,
    ColumnMaskContractModel,
    ConnectorSourceContract,
    DeduplicateContractModel,
    DerivedNames,
    ExecutionCatchupContractModel,
    ExecutionContractModel,
    ExecutionWindow,
    ExecutionWindowContractModel,
    NamingConfig,
    NativeCapability,
    OperationsContractModel,
    PiiContractModel,
    QualityExpressionContractModel,
    QualityRulesContractModel,
    RowFilterContractModel,
    ShapeArrayContractModel,
    ShapeColumnContractModel,
    ShapeContractModel,
    ShapeFlattenContractModel,
    ShapeJsonContractModel,
    ShapeZipArraysContractModel,
    StandardizeColumnContractModel,
    TableAnnotationsContractModel,
    TransformContractModel,
    capability,
    contract_model_schemas,
    derive_names,
    diagnose_source_connectors,
    list_source_connector_details,
    load_contract_bundle,
    redact_secrets,
    redact_text,
    source_connector_details,
    target_full_table_name,
    target_schema_name,
    validate_plan_shape,
    yaml_schema,
)


def test_core_public_api_exposes_contract_and_capability_helpers() -> None:
    assert callable(contract_model_schemas)
    assert callable(yaml_schema)
    assert CapabilityEvidence(source="test", message="ok").as_dict()["source"] == "test"
    assert NativeCapability(name="merge", status="supported", reason="test").supported
    assert capability("merge", "unsupported", "test").supported is False


def test_core_public_api_exposes_canonical_governance_contract_models() -> None:
    assert AccessContractModel is not None
    assert AccessGrantContractModel(principal="analysts", privileges=["SELECT"]).principal == "analysts"
    assert AnnotationsContractModel(table={"description": "Orders"}).table.description == "Orders"
    assert ColumnAnnotationsContractModel(description="Email").description == "Email"
    assert ColumnMaskContractModel(column="email", function="main.sec.mask_email").column == "email"
    assert OperationsContractModel(criticality="high").criticality == "high"
    assert PiiContractModel(type="email").type == "email"
    assert RowFilterContractModel(
        name="country",
        function="main.sec.filter_country",
        columns=["country"],
    ).name == "country"
    assert TableAnnotationsContractModel(description="Orders").description == "Orders"


def test_core_public_api_exposes_canonical_contract_models() -> None:
    assert ConnectorSourceContract(type="connector", connector="jdbc").connector == "jdbc"
    assert DeduplicateContractModel(keys=["id"], order_by="updated_at DESC").keys == ["id"]
    assert ExecutionCatchupContractModel(enabled=True, column="updated_at").column == "updated_at"
    assert ExecutionContractModel().window is None
    assert ExecutionWindow("2026-01-01", "2026-01-02", "d1").label == "d1"
    assert ExecutionWindowContractModel(column="updated_at").column == "updated_at"
    assert QualityExpressionContractModel(name="positive", expression="amount > 0").name == "positive"
    assert QualityRulesContractModel(not_null=["id"]).not_null == ["id"]
    assert ShapeArrayContractModel(path="items").mode == "keep"
    assert ShapeColumnContractModel(alias="id").alias == "id"
    assert ShapeContractModel(arrays=[{"path": "items"}]).arrays[0].path == "items"
    assert ShapeFlattenContractModel(enabled=True).enabled
    assert ShapeJsonContractModel(column="payload", schema="id STRING").column == "payload"
    assert ShapeZipArraysContractModel(alias="zipped", columns={"a": "a"}).alias == "zipped"
    assert StandardizeColumnContractModel(trim=True).trim
    assert TransformContractModel(cast={"amount": "double"}).cast["amount"] == "double"


def test_core_public_api_exposes_ported_naming_models() -> None:
    names = derive_names(target_table="orders", layer="silver", config=NamingConfig())

    assert isinstance(names, DerivedNames)
    assert names.contract_basename == "orders"


def test_core_public_api_exposes_ported_connector_and_redaction_helpers() -> None:
    assert source_connector_details("jdbc")["family"] == "jdbc"
    assert list_source_connector_details()
    assert diagnose_source_connectors(["incremental_files"])[0]["status"] == "SUCCESS"
    assert redact_text("password=secret") == "password=***REDACTED***"
    assert redact_secrets({"password": "secret"})["password"] == "***REDACTED***"


def test_core_public_api_exposes_bundle_and_target_helpers(tmp_path) -> None:
    contract = {
        "source": {"type": "table", "table": "raw.orders"},
        "target": {"catalog": "main", "schema": "silver", "table": "orders"},
    }

    assert callable(load_contract_bundle)
    assert target_schema_name(contract) == "silver"
    assert target_full_table_name(contract) == "main.silver.orders"
    assert validate_plan_shape(contract) is None
