import json
from pathlib import Path

from contractforge_ai.context import build_project_context_package


def test_project_context_infers_schema_from_json_sample(tmp_path: Path):
    sample = tmp_path / "orders.json"
    sample.write_text(
        json.dumps(
            [
                {
                    "order_id": "A-1",
                    "amount": 10.5,
                    "active": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    package = build_project_context_package(
        intent="Create a bronze ingestion for orders",
        context_dir=tmp_path,
        runtime="serverless",
    )

    assert package.runtime == "databricks-serverless"
    assert package.files[0].format == "json"
    assert package.inferred_schema == {
        "columns": [
            {"name": "order_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "double", "nullable": False},
            {"name": "active", "type": "boolean", "nullable": False},
        ]
    }
    assert package.traceability.evidence[0].value["has_inferred_schema"] is True


def test_project_context_infers_schema_from_csv_sample(tmp_path: Path):
    sample = tmp_path / "orders.csv"
    sample.write_text("order_id,amount\nA-1,10.5\n", encoding="utf-8")

    package = build_project_context_package(
        intent="Create a bronze ingestion for orders",
        context_dir=tmp_path,
        runtime="classic",
    )

    assert package.runtime == "databricks-classic"
    assert package.files[0].format == "csv"
    assert package.inferred_schema == {
        "columns": [
            {"name": "order_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "string", "nullable": False},
        ]
    }


def test_project_context_requires_schema_or_sample_evidence():
    package = build_project_context_package(intent="Create a project")

    assert package.inferred_schema is None
    assert any(decision.path == "schema_path" for decision in package.decisions_required)
    assert package.traceability.review_required is True
