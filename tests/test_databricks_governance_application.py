from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.annotations import apply_annotations_contract
from contractforge_databricks.governance import apply_access_contract, apply_governance_contract, check_governance_contract


class FakeRunner:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.statements: list[str] = []

    def sql(self, statement: str) -> None:
        self.statements.append(statement)
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError(f"failed on {self.fail_on}")


class QueryRunner(FakeRunner):
    def __init__(self, *, grants: list[dict[str, str]]) -> None:
        super().__init__()
        self.grants = grants
        self.queries: list[str] = []

    def query(self, statement: str) -> list[dict[str, str]]:
        self.queries.append(statement)
        return self.grants


def test_apply_annotations_contract_executes_steps() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "annotations": {
                "table": {"description": "Customers", "tags": {"domain": "crm"}},
                "columns": {"email": {"description": "Email"}},
            },
        }
    )
    runner = FakeRunner()

    result = apply_annotations_contract(runner=runner, contract=contract)

    assert result.status == "SUCCESS"
    assert result.applied == 3
    assert len(runner.statements) == 3
    assert runner.statements[0].startswith("COMMENT ON TABLE")


def test_apply_annotations_contract_honors_ignore_policy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "annotations": {"policy": "ignore", "table": {"description": "Customers"}},
        }
    )
    runner = FakeRunner()

    result = apply_annotations_contract(runner=runner, contract=contract)

    assert result.status == "IGNORED"
    assert result.ignored == 1
    assert runner.statements == []


def test_apply_annotations_contract_warns_or_fails_by_policy() -> None:
    base = {
        "source": {"type": "table", "table": "main.raw.customers"},
        "target": {"catalog": "main", "schema": "silver", "table": "customers"},
        "mode": "scd0_append",
    }
    warned = apply_annotations_contract(
        runner=FakeRunner(fail_on="COMMENT"),
        contract=semantic_contract_from_mapping({**base, "annotations": {"table": {"description": "Customers"}}}),
    )
    failed = apply_annotations_contract(
        runner=FakeRunner(fail_on="COMMENT"),
        contract=semantic_contract_from_mapping({**base, "annotations": {"policy": "fail", "table": {"description": "Customers"}}}),
    )

    assert warned.status == "WARNED"
    assert warned.failed == 1
    assert failed.status == "FAILED"
    assert failed.failed == 1


def test_apply_access_contract_validates_without_execution() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {
                "access_policy": {"mode": "validate_only"},
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
            },
        }
    )
    runner = FakeRunner()

    result = apply_access_contract(runner=runner, contract=contract)

    assert result.status == "VALIDATED"
    assert result.validated == 1
    assert runner.statements == []


def test_apply_access_contract_executes_and_warns_on_failure() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {"grants": [{"principal": "analysts", "privileges": ["SELECT"]}]},
        }
    )

    result = apply_access_contract(runner=FakeRunner(fail_on="GRANT"), contract=contract)

    assert result.status == "WARNED"
    assert result.failed == 1


def test_apply_access_contract_fails_fast_on_fail_policy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {
                "access_policy": {"on_drift": "fail"},
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
            },
        }
    )

    result = apply_access_contract(runner=FakeRunner(fail_on="GRANT"), contract=contract)

    assert result.status == "FAILED"
    assert result.failed == 1


def test_apply_access_contract_fails_on_detected_drift_with_fail_policy() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {
                "access_policy": {"on_drift": "fail"},
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
            },
        }
    )
    runner = QueryRunner(grants=[])

    result = apply_access_contract(runner=runner, contract=contract)

    assert result.status == "FAILED"
    assert "SHOW GRANTS ON TABLE `main`.`silver`.`customers`" in runner.queries[0]
    assert "Declared grant is missing" in result.errors[0]
    assert runner.statements == []


def test_apply_access_contract_reconciles_unmanaged_grants_when_explicitly_allowed() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {
                "access_policy": {"revoke_unmanaged": True},
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
            },
        }
    )
    runner = QueryRunner(
        grants=[
            {"Principal": "analysts", "ActionType": "SELECT"},
            {"Principal": "admins", "ActionType": "MODIFY"},
        ]
    )

    result = apply_access_contract(runner=runner, contract=contract, allow_revoke_unmanaged=True)

    assert result.status == "SUCCESS"
    assert result.applied == 2
    assert runner.statements[0] == "GRANT SELECT ON TABLE `main`.`silver`.`customers` TO `analysts`"
    assert runner.statements[1] == "REVOKE MODIFY ON TABLE `main`.`silver`.`customers` FROM `admins`"
    assert "revoke" in result.sql_preview[1].lower()


def test_apply_access_contract_requires_explicit_confirmation_to_revoke_unmanaged() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {
                "access_policy": {"revoke_unmanaged": True},
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
            },
        }
    )
    runner = QueryRunner(grants=[{"Principal": "admins", "ActionType": "MODIFY"}])

    result = apply_access_contract(runner=runner, contract=contract)

    assert result.status == "FAILED"
    assert result.errors == ("access.revoke_unmanaged requires explicit allow_revoke_unmanaged=True",)
    assert runner.statements == []


def test_apply_access_contract_not_configured() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
        }
    )

    assert apply_access_contract(runner=FakeRunner(), contract=contract).status == "NOT_CONFIGURED"


def test_check_governance_contract_returns_combined_preview() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "annotations": {"table": {"description": "Customers"}},
            "access": {"grants": [{"principal": "analysts", "privileges": ["SELECT"]}]},
        }
    )

    result = check_governance_contract(contract)

    assert result["status"] == "VALIDATED"
    assert result["validated"] == 2
    assert result["annotations"].validated == 1
    assert result["access"].validated == 1
    assert len(result["sql_preview"]) == 2


def test_apply_governance_contract_combines_annotations_and_access() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "annotations": {"table": {"description": "Customers"}},
            "access": {"grants": [{"principal": "analysts", "privileges": ["SELECT"]}]},
        }
    )
    runner = FakeRunner()

    result = apply_governance_contract(runner=runner, contract=contract)

    assert result["status"] == "SUCCESS"
    assert result["applied"] == 2
    assert len(runner.statements) == 2
