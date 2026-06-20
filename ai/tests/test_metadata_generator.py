import json
from pathlib import Path

from contractforge_ai.cli import main
from contractforge_ai.generators.metadata import suggest_metadata


def test_suggest_metadata_from_schema_profile(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "customer_id", "type": "STRING", "nullable": False},
                    {"name": "customer_email", "type": "STRING", "nullable": True},
                    {
                        "name": "status",
                        "type": "STRING",
                        "nullable": False,
                        "profile": {"distinct_values": ["open", "closed", "cancelled"]},
                    },
                    {"name": "order_amount", "type": "DOUBLE", "nullable": True},
                    {"name": "updated_at", "type": "TIMESTAMP", "nullable": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = suggest_metadata(schema)

    assert result.quality_rules["not_null"] == ["customer_id", "status"]
    assert result.quality_rules["accepted_values"]["status"] == ["open", "closed", "cancelled"]
    assert result.annotations["columns"]["customer_email"]["pii"] == {
        "enabled": True,
        "type": "email",
        "sensitivity": "restricted",
    }
    assert result.annotations["columns"]["customer_id"]["tags"]["role"] == "key"
    assert result.annotations["columns"]["updated_at"]["tags"]["role"] == "timestamp"
    assert result.quality_rules["expressions"][0]["expression"] == "order_amount >= 0"
    assert any(suggestion.kind == "pii" for suggestion in result.suggestions)
    assert result.traceability.review_required is True
    assert result.traceability.evidence[0].source == "schema"
    pii_suggestion = next(suggestion for suggestion in result.suggestions if suggestion.kind == "pii")
    assert pii_suggestion.review_required is True
    assert pii_suggestion.to_dict()["confidence_level"] == "high"
    assert pii_suggestion.evidence_items[0].path == "columns.customer_email.name"


def test_suggest_metadata_accepts_mapping_columns(tmp_path: Path):
    schema = tmp_path / "schema.yaml"
    schema.write_text(
        """
columns:
  id:
    type: string
    nullable: false
  phone_number:
    type: string
    nullable: true
""",
        encoding="utf-8",
    )

    result = suggest_metadata(schema)

    assert result.quality_rules["not_null"] == ["id"]
    assert result.annotations["columns"]["phone_number"]["pii"]["type"] == "phone"


def test_suggest_metadata_cli_outputs_yaml(tmp_path: Path, capsys):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "columns": [
                    {"name": "id", "type": "STRING", "nullable": False},
                    {"name": "credit_card_number", "type": "STRING", "nullable": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["suggest-metadata", "--schema", str(schema), "--format", "yaml"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "annotations:" in output
    assert "quality_rules:" in output
    assert "credit_card" in output
    assert "not_null:" in output


def test_suggest_metadata_warns_when_no_columns(tmp_path: Path):
    schema = tmp_path / "empty.json"
    schema.write_text("{}", encoding="utf-8")

    result = suggest_metadata(schema)

    assert result.warnings
    assert result.annotations == {"table": {}, "columns": {}}
    assert result.quality_rules == {}

