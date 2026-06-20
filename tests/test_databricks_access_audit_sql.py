from datetime import datetime

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.governance import access_steps, render_access_audit_insert_sql, render_access_sql


def test_access_steps_preserve_contractforge_governance_audit_shape() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {
                "access_policy": {"mode": "validate_only", "on_drift": "warn", "revoke_unmanaged": False},
                "grants": [{"principal": "analysts", "privileges": ["SELECT", "MODIFY"]}],
                "row_filters": [
                    {
                        "name": "country_filter",
                        "function": "main.security.country_filter",
                        "columns": ["country"],
                        "applies_to": {"principals": ["analysts"]},
                    }
                ],
                "column_masks": {
                    "email": {
                        "function": "main.security.mask_email",
                        "using_columns": ["email"],
                        "applies_to": {"principals": ["analysts"]},
                    }
                },
            },
        }
    )

    steps = access_steps(contract)
    review_sql = render_access_sql(contract)
    audit_sql = render_access_audit_insert_sql(
        contract,
        run_id="run-1",
        status="VALIDATED",
        captured_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert [step["access_type"] for step in steps] == ["grant", "grant", "row_filter", "column_mask"]
    assert steps[0]["mode"] == "validate_only"
    assert "GRANT SELECT ON TABLE `main`.`silver`.`customers` TO `analysts`;" in review_sql
    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_access`" in audit_sql
    assert "'row_filter'" in audit_sql
    assert "'column_mask'" in audit_sql
    assert "'main.security.mask_email'" in audit_sql
    assert "'VALIDATED'" in audit_sql


def test_column_mask_does_not_invent_using_columns() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "access": {"column_masks": {"email": {"function": "main.security.mask_email"}}},
        }
    )

    assert access_steps(contract)[0]["sql"] == (
        "ALTER TABLE `main`.`silver`.`customers` ALTER COLUMN `email` SET MASK main.security.mask_email"
    )
