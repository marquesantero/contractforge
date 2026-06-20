from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.governance import (
    access_drift_report,
    governance_referenced_columns,
    validate_governance_contract,
)


def _contract():
    return semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "annotations": {
                "table": {"tags": {"contains_pii": "true"}},
                "columns": {"email": {"pii": {"enabled": True}}},
            },
            "access": {
                "access_policy": {"on_drift": "fail", "revoke_unmanaged": True},
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
                "row_filters": [{"name": "tenant_filter", "columns": ["tenant_id"], "function": "main.sec.tenant_filter"}],
                "column_masks": [{"column": "email", "using_columns": ["country"], "function": "main.sec.mask_email"}],
            },
        }
    )


def test_governance_referenced_columns() -> None:
    refs = governance_referenced_columns(_contract())

    assert refs["annotations"] == ["email"]
    assert refs["row_filters"] == ["tenant_id"]
    assert refs["column_masks"] == ["country", "email"]
    assert refs["all"] == ["country", "email", "tenant_id"]


def test_validate_governance_contract_detects_missing_columns_and_pii_description() -> None:
    result = validate_governance_contract(_contract(), existing_columns={"email", "tenant_id"})

    assert result["status"] == "FAILED"
    assert any(issue["object"] == "country" and issue["severity"] == "fail" for issue in result["issues"])
    assert any(issue["object"] == "email" and issue["severity"] == "warn" for issue in result["issues"])


def test_access_drift_report_detects_missing_and_unmanaged_grants() -> None:
    result = access_drift_report(
        _contract(),
        current_grants={("admins", "SELECT")},
    )

    assert result["status"] == "DRIFTED"
    assert result["missing_grants"] == [("analysts", "SELECT")]
    assert result["unmanaged_grants"] == [("admins", "SELECT")]
    assert all(issue["severity"] == "fail" for issue in result["issues"])


def test_access_drift_report_in_sync() -> None:
    result = access_drift_report(_contract(), current_grants={("analysts", "select")})

    assert result["status"] == "IN_SYNC"
    assert result["issues"] == []
