"""Databricks adapter package for ContractForge Core."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("contractforge-databricks")
except PackageNotFoundError:  # pragma: no cover - editable installs without metadata
    __version__ = "0.0.0+unknown"

from contractforge_databricks.adapter import DatabricksAdapter
from contractforge_databricks.api import plan_databricks_contract, render_databricks_contract
from contractforge_databricks.capabilities.evaluate import evaluate_databricks_capabilities
from contractforge_databricks.capabilities.mapping import to_core_capabilities
from contractforge_databricks.capabilities.models import CapabilityEvidence, DatabricksCapabilities, NativeCapability
from contractforge_databricks.capabilities.uc import uc_capability_issues
from contractforge_databricks.cost import CostModel, build_operational_cost_report, render_operational_cost_query
from contractforge_databricks.dashboards import render_control_dashboard_artifacts, render_control_dashboard_sql
from contractforge_databricks.environment import DatabricksEnvironment
from contractforge_databricks.evidence import render_deployment_ledger_insert_sql
from contractforge_databricks.bundles import render_databricks_project_bundle, render_databricks_project_bundle_yaml
from contractforge_databricks.governance import (
    access_drift_report,
    apply_access_contract,
    apply_governance_contract,
    check_governance_contract,
    governance_referenced_columns,
    render_access_sql,
    render_governance_sql,
    validate_governance_contract,
)
from contractforge_databricks.lakeflow import (
    LakeflowAutoCdcArtifact,
    LakeflowCompatibility,
    evaluate_lakeflow_compatibility,
    render_lakeflow_auto_cdc_artifact,
    render_lakeflow_auto_cdc_python,
)
from contractforge_databricks.maintenance import build_control_retention_plan, execute_control_retention_plan
from contractforge_databricks.metrics import render_delta_history_query, resolve_write_metrics
from contractforge_databricks.parity import (
    ParityMetricExpectation,
    WriteEngineParityScenario,
    build_write_engine_parity_plan,
    get_write_engine_parity_scenario,
    list_write_engine_parity_scenarios,
    scenarios_for_engine,
    scenarios_for_mode,
)
from contractforge_databricks.presets import apply_preset, get_preset, list_presets, preset_details, register_preset
from contractforge_databricks.preparation import apply_shape
from contractforge_databricks.quality import (
    get_quality_rule,
    list_quality_rules,
    register_quality_rule,
    unregister_quality_rule,
)
from contractforge_databricks.runtime import (
    DatabricksIngestOptions,
    DatabricksIngestionHooks,
    PreparedViewInput,
    apply_databricks_access_bundle,
    apply_databricks_annotations_bundle,
    apply_databricks_governance_bundle,
    detect_databricks_capabilities,
    deploy_databricks_bundle,
    deploy_databricks_project,
    get_source_resolver,
    ingest_databricks_bundle,
    ingest_databricks_contract,
    list_source_resolvers,
    register_source_resolver,
    render_databricks_project_bundle_file,
    resolve_source_dataframe,
    run_available_now_stream,
    unregister_source_resolver,
)
from contractforge_databricks.templates import (
    contract_template_details,
    contract_template_files,
    get_contract_template,
    list_contract_templates,
    recommend_contract_templates,
)
from contractforge_databricks.write_modes.registry import (
    get_write_mode,
    list_write_modes,
    register_write_mode,
    unregister_write_mode,
)
from contractforge_databricks.write_modes.strategy import WriteStrategy, choose_write_strategy

__all__ = [
    "CapabilityEvidence",
    "CostModel",
    "DatabricksAdapter",
    "DatabricksCapabilities",
    "DatabricksEnvironment",
    "DatabricksIngestOptions",
    "DatabricksIngestionHooks",
    "LakeflowAutoCdcArtifact",
    "LakeflowCompatibility",
    "NativeCapability",
    "ParityMetricExpectation",
    "PreparedViewInput",
    "WriteEngineParityScenario",
    "WriteStrategy",
    "access_drift_report",
    "apply_access_contract",
    "apply_databricks_access_bundle",
    "apply_databricks_annotations_bundle",
    "apply_databricks_governance_bundle",
    "apply_governance_contract",
    "apply_preset",
    "apply_shape",
    "build_control_retention_plan",
    "build_operational_cost_report",
    "build_write_engine_parity_plan",
    "check_governance_contract",
    "choose_write_strategy",
    "contract_template_details",
    "contract_template_files",
    "detect_databricks_capabilities",
    "deploy_databricks_bundle",
    "deploy_databricks_project",
    "evaluate_databricks_capabilities",
    "evaluate_lakeflow_compatibility",
    "execute_control_retention_plan",
    "get_contract_template",
    "get_preset",
    "get_quality_rule",
    "get_source_resolver",
    "get_write_engine_parity_scenario",
    "get_write_mode",
    "governance_referenced_columns",
    "ingest_databricks_bundle",
    "ingest_databricks_contract",
    "list_contract_templates",
    "list_presets",
    "list_quality_rules",
    "list_source_resolvers",
    "list_write_engine_parity_scenarios",
    "list_write_modes",
    "plan_databricks_contract",
    "preset_details",
    "recommend_contract_templates",
    "register_preset",
    "register_quality_rule",
    "register_source_resolver",
    "register_write_mode",
    "render_access_sql",
    "render_control_dashboard_artifacts",
    "render_control_dashboard_sql",
    "render_databricks_contract",
    "render_databricks_project_bundle",
    "render_databricks_project_bundle_file",
    "render_databricks_project_bundle_yaml",
    "render_deployment_ledger_insert_sql",
    "render_delta_history_query",
    "render_governance_sql",
    "render_lakeflow_auto_cdc_artifact",
    "render_lakeflow_auto_cdc_python",
    "render_operational_cost_query",
    "resolve_source_dataframe",
    "resolve_write_metrics",
    "run_available_now_stream",
    "scenarios_for_engine",
    "scenarios_for_mode",
    "to_core_capabilities",
    "uc_capability_issues",
    "unregister_source_resolver",
    "unregister_quality_rule",
    "unregister_write_mode",
    "validate_governance_contract",
]
