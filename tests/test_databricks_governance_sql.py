from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.governance import render_governance_sql


def test_render_governance_sql_for_uc_access_and_annotations() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "connector", "connector": "postgres"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "annotations": {
                "table": {"description": "Customer table", "tags": {"domain": "crm"}},
                "columns": {"email": {"description": "Email address", "pii": {"type": "email"}}},
            },
            "access": {
                "grants": [{"principal": "analysts", "privileges": ["SELECT"]}],
                "row_filters": [
                    {
                        "name": "country_filter",
                        "function": "main.security.country_filter",
                        "columns": ["country"],
                    }
                ],
                "column_masks": {
                    "email": {
                        "function": "main.security.mask_email",
                        "using_columns": ["email"],
                    }
                },
            },
        }
    )

    sql = render_governance_sql(contract)

    assert "COMMENT ON TABLE `main`.`silver`.`customers` IS 'Customer table';" in sql
    assert "ALTER TABLE `main`.`silver`.`customers` SET TAGS ('domain' = 'crm');" in sql
    assert "ALTER TABLE `main`.`silver`.`customers` ALTER COLUMN `email` COMMENT 'Email address';" in sql
    assert "'pii_type' = 'email'" in sql
    assert "GRANT SELECT ON TABLE `main`.`silver`.`customers` TO `analysts`;" in sql
    assert "ALTER TABLE `main`.`silver`.`customers` SET ROW FILTER main.security.country_filter ON (`country`);" in sql
    assert "ALTER TABLE `main`.`silver`.`customers` ALTER COLUMN `email` SET MASK main.security.mask_email USING COLUMNS (`email`);" in sql
