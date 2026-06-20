from contractforge_core.contracts import semantic_contract_from_mapping
from datetime import datetime

from contractforge_databricks.annotations import annotation_steps, render_annotations_audit_insert_sql, render_annotations_sql


def test_render_annotations_sql_for_uc_tags_and_lifecycle_metadata() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.customers"},
            "target": {"catalog": "main", "schema": "silver", "table": "customers"},
            "mode": "scd0_append",
            "annotations": {
                "table": {
                    "description": "Customer table",
                    "aliases": ["clients"],
                    "tags": {"domain": "crm", "regulated": True},
                    "deprecated": {
                        "since": "2026-01-01",
                        "replacement": "main.gold.customers",
                        "removal_date": "2026-12-31",
                    },
                },
                "columns": {
                    "email": {
                        "description": "Email address",
                        "aliases": "email_address",
                        "tags": {"confidentiality": "restricted"},
                        "pii": {"enabled": True, "type": "email", "sensitivity": "restricted"},
                    }
                },
            },
        }
    )

    sql = render_annotations_sql(contract)
    steps = annotation_steps(contract)
    audit_sql = render_annotations_audit_insert_sql(
        contract,
        run_id="run-1",
        status="APPLIED",
        captured_at_utc=datetime(2026, 1, 1, 12, 0, 0),
    )

    assert [step["annotation_type"] for step in steps] == ["description", "tags", "description", "tags"]
    assert "COMMENT ON TABLE `main`.`silver`.`customers` IS 'Customer table';" in sql
    assert "'domain' = 'crm'" in sql
    assert "'regulated' = 'true'" in sql
    assert "'alias_1' = 'clients'" in sql
    assert "'deprecated_since' = '2026-01-01'" in sql
    assert "'deprecated_replacement' = 'main.gold.customers'" in sql
    assert "ALTER TABLE `main`.`silver`.`customers` ALTER COLUMN `email` COMMENT 'Email address';" in sql
    assert "ALTER TABLE `main`.`silver`.`customers` ALTER COLUMN `email` SET TAGS" in sql
    assert "'pii' = 'true'" in sql
    assert "'pii_type' = 'email'" in sql
    assert "INSERT INTO `main`.`ops`.`ctrl_ingestion_annotations`" in audit_sql
    assert "'APPLIED'" in audit_sql
    assert "'column'" in audit_sql
