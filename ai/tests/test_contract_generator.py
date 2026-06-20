import json
from pathlib import Path

from contractforge_ai.cli import main
from contractforge_ai.generators.contract import generate_contract_draft


def test_generate_bronze_contract_draft(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "event_id", "type": "STRING", "nullable": False},
                    {"name": "customer_email", "type": "STRING", "nullable": True},
                    {"name": "amount", "type": "DOUBLE", "nullable": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = generate_contract_draft(
        schema,
        connector="files",
        source_path="/Volumes/main/landing/events",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_events",
        owner="data-engineering",
    )

    contract = result.contract
    assert contract["_metadata"]["draft"] is True
    assert contract["_metadata"]["review_required"] is True
    assert contract["mode"] == "append"
    assert contract["source"]["read"]["schema"] == "event_id STRING, customer_email STRING, amount DOUBLE"
    assert contract["quality_rules"]["not_null"] == ["event_id"]
    assert contract["annotations"]["columns"]["customer_email"]["pii"]["type"] == "email"
    assert result.decisions_required
    assert result.traceability.review_required is True
    assert result.traceability.confidence_level == "medium"
    assert result.traceability.decisions_required
    assert result.validation is not None
    assert result.validation.status == "WARN"
    assert any(finding.code == "generated.review_placeholder" for finding in result.validation.findings)


def test_generate_silver_contract_draft_selects_merge_key_candidate(tmp_path: Path):
    schema = tmp_path / "schema.yaml"
    schema.write_text(
        """
columns:
  customer_id:
    type: string
    nullable: false
  status:
    type: string
    nullable: false
    profile:
      distinct_values: [active, inactive]
""",
        encoding="utf-8",
    )

    result = generate_contract_draft(
        schema,
        connector="table",
        source_path="main.bronze.customers",
        target_catalog="main",
        target_schema="silver",
        target_table="s_customers",
        layer="silver",
    )

    assert result.contract["mode"] == "hash_diff_upsert"
    assert result.contract["merge_keys"] == ["customer_id"]
    assert any("Merge key candidate" in assumption for assumption in result.assumptions)
    assert any("Validate merge_keys" in decision for decision in result.decisions_required)
    assert any("merge key" in item.question.lower() for item in result.traceability.decisions_required)
    assert result.validation is not None
    assert result.validation.status == "WARN"


def test_generate_http_file_contract_adds_required_format(tmp_path: Path):
    schema = tmp_path / "schema.yaml"
    schema.write_text(
        """
columns:
- name: title
  type: string
  nullable: false
""",
        encoding="utf-8",
    )

    result = generate_contract_draft(
        schema,
        connector="http_file",
        source_path="https://example.com/api/events",
        target_catalog="main",
        target_schema="bronze",
        target_table="b_events",
        layer="bronze",
    )

    assert result.contract["source"]["format"] == "json"


def test_generate_object_storage_contract_marks_missing_format_for_review(tmp_path: Path):
    schema = tmp_path / "schema.yaml"
    schema.write_text(
        """
columns:
- name: id
  type: string
  nullable: false
""",
        encoding="utf-8",
    )

    result = generate_contract_draft(
        schema,
        connector="s3",
        source_path="s3://landing/orders",
        target_catalog="analytics",
        target_schema="bronze",
        target_table="b_orders",
        layer="bronze",
    )

    assert result.contract["source"]["format"] == "REVIEW_REQUIRED"
    assert any("source file format" in decision for decision in result.decisions_required)


def test_generate_contract_cli_outputs_yaml(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "id", "type": "STRING", "nullable": False}]}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "generate-contract",
            "--schema",
            str(schema),
            "--connector",
            "files",
            "--source-path",
            "/tmp/input",
            "--target-catalog",
            "main",
            "--target-schema",
            "bronze",
            "--target-table",
            "b_input",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "_metadata:" in output
    assert "draft: true" in output
    assert "quality_rules:" in output
