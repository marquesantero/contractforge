from contractforge_core.capabilities import PlatformCapabilities
from contractforge_core.capabilities.native import capability
from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.execution import ExecutionOutcome
from contractforge_core.planner import plan_contract
from contractforge_core.runtime import PreparedInput
from contractforge_databricks.capabilities.mapping import to_core_capabilities
from contractforge_databricks.capabilities.models import DatabricksCapabilities
from contractforge_databricks.runtime.write import execute_prepared_write
from contractforge_databricks.write_modes.registry import (
    clear_write_mode_registry,
    get_write_mode,
    list_write_modes,
    register_write_mode,
)


def setup_function() -> None:
    clear_write_mode_registry()


def teardown_function() -> None:
    clear_write_mode_registry()


def test_core_accepts_custom_write_mode_as_review_boundary() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": "custom:acme_delta_writer",
        }
    )

    result = plan_contract(
        contract,
        PlatformCapabilities(platform="generic", supports_append=True, evidence_stores=("audit",)),
    )

    assert result.status == "REVIEW_REQUIRED"
    assert result.plan is not None


def test_registered_databricks_write_mode_declares_capability_and_dispatches() -> None:
    def handler(**kwargs):
        return ExecutionOutcome(
            status="SUCCESS",
            operation="custom:acme_delta_writer",
            target=kwargs["contract"].target.name,
            metrics={"rows_written": 3},
            sql="-- custom",
        )

    mode = register_write_mode("acme_delta_writer", handler)
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "mode": mode,
        }
    )
    capabilities = to_core_capabilities(
        DatabricksCapabilities(
            runtime_kind="databricks_serverless",
            target_table=None,
            spark_version=None,
            capabilities={"delta_control_tables": capability("delta_control_tables", "supported", "test")},
        )
    )

    assert mode == "custom:acme_delta_writer"
    assert get_write_mode(mode) is handler
    assert list_write_modes() == (mode,)
    assert mode in capabilities.supported_custom_write_modes
    assert plan_contract(contract, capabilities).status == "SUPPORTED"

    outcome = execute_prepared_write(
        runner=lambda sql: None,
        contract=contract,
        prepared=PreparedInput(source_view="orders_view", source_columns=("id",), rows_read=3),
    )

    assert outcome.operation == mode
    assert outcome.metrics["rows_written"] == 3
