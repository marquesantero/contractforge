"""Public contract validation models and adapters."""

from contractforge_core.contracts.base import contract_validation_error
from contractforge_core.contracts.bundle import (
    ContractBundle,
    compose_contract_sections,
    contract_metadata_warnings,
    load_contract_bundle,
)
from contractforge_core.contracts.defaults import ContractDefaultDecision, ResolvedContract, resolve_contract_defaults
from contractforge_core.contracts.environment import EnvironmentContractModel, validate_environment_contract
from contractforge_core.contracts.execution import (
    ExecutionCatchupContractModel,
    ExecutionContractModel,
    ExecutionWindowContractModel,
    ExecutionWindowItemContractModel,
    validate_execution_contract,
)
from contractforge_core.contracts.governance import (
    AccessContractModel,
    AccessGrantContractModel,
    AnnotationsContractModel,
    ColumnAnnotationsContractModel,
    ColumnMaskContractModel,
    DeprecatedContractModel,
    OperationsContractModel,
    PiiContractModel,
    RowFilterContractModel,
    TableAnnotationsContractModel,
    validate_access_contract,
    validate_annotations_contract,
    validate_operations_contract,
)
from contractforge_core.contracts.normalize import semantic_contract_from_mapping
from contractforge_core.contracts.naming import NamingContractModel, validate_naming_contract
from contractforge_core.contracts.plan_validation import validate_plan_shape
from contractforge_core.contracts.quality import (
    QualityExpressionContractModel,
    QualityRulesContractModel,
    validate_quality_rules_contract,
)
from contractforge_core.contracts.root import SemanticContractInputModel, validate_contract
from contractforge_core.contracts.schema import contract_model_schemas, yaml_schema
from contractforge_core.contracts.shape_validation import validate_shape_semantics
from contractforge_core.contracts.source_portability import SourceTypeClassification, classify_source_type
from contractforge_core.contracts.targeting import target_full_table_name, target_schema_name
from contractforge_core.contracts.source import (
    ConnectorSourceContract,
    GenericSourceContract,
    SourceDiscoveryContract,
    SourceStateContract,
    SourceStateLocationContract,
    SourceContract,
    validate_source_contract,
)
from contractforge_core.contracts.source_validation import validate_source_semantics
from contractforge_core.contracts.transform import (
    DeduplicateContractModel,
    ShapeArrayContractModel,
    ShapeColumnContractModel,
    ShapeContractModel,
    ShapeFlattenContractModel,
    ShapeJsonContractModel,
    ShapeZipArraysContractModel,
    StandardizeColumnContractModel,
    TransformContractModel,
    validate_shape_contract,
    validate_transform_contract,
)

__all__ = [
    "AccessContractModel",
    "AccessGrantContractModel",
    "AnnotationsContractModel",
    "ConnectorSourceContract",
    "ContractBundle",
    "ContractDefaultDecision",
    "ColumnAnnotationsContractModel",
    "ColumnMaskContractModel",
    "DeduplicateContractModel",
    "DeprecatedContractModel",
    "EnvironmentContractModel",
    "ExecutionContractModel",
    "ExecutionCatchupContractModel",
    "ExecutionWindowContractModel",
    "ExecutionWindowItemContractModel",
    "GenericSourceContract",
    "OperationsContractModel",
    "NamingContractModel",
    "PiiContractModel",
    "QualityExpressionContractModel",
    "QualityRulesContractModel",
    "ResolvedContract",
    "RowFilterContractModel",
    "SemanticContractInputModel",
    "ShapeContractModel",
    "ShapeArrayContractModel",
    "ShapeColumnContractModel",
    "ShapeFlattenContractModel",
    "ShapeJsonContractModel",
    "ShapeZipArraysContractModel",
    "SourceContract",
    "SourceDiscoveryContract",
    "SourceStateContract",
    "SourceStateLocationContract",
    "SourceTypeClassification",
    "StandardizeColumnContractModel",
    "TableAnnotationsContractModel",
    "TransformContractModel",
    "contract_model_schemas",
    "contract_validation_error",
    "classify_source_type",
    "compose_contract_sections",
    "contract_metadata_warnings",
    "load_contract_bundle",
    "resolve_contract_defaults",
    "semantic_contract_from_mapping",
    "target_full_table_name",
    "target_schema_name",
    "validate_access_contract",
    "validate_annotations_contract",
    "validate_contract",
    "validate_environment_contract",
    "validate_execution_contract",
    "validate_operations_contract",
    "validate_plan_shape",
    "validate_naming_contract",
    "validate_quality_rules_contract",
    "validate_shape_contract",
    "validate_shape_semantics",
    "validate_source_contract",
    "validate_source_semantics",
    "validate_transform_contract",
    "yaml_schema",
]
