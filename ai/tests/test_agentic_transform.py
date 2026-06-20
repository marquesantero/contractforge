import json
from pathlib import Path

from contractforge_ai.agentic.intent import interpret_intent
from contractforge_ai.agentic.transform import infer_transformation_plan


def test_infer_transformation_plan_projects_exact_columns(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "order_id", "type": "STRING"}, {"name": "amount", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    intent = interpret_intent("Create gold with final columns: order_id, amount.")

    plan = infer_transformation_plan(intent, schema_path=str(schema))

    assert plan.shape_columns == {"order_id": "order_id", "amount": "amount"}
    assert [step.action for step in plan.steps] == ["select", "select"]
    assert plan.decisions_required == []


def test_infer_transformation_plan_renames_structurally_equivalent_columns(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "customerId", "type": "STRING"}, {"name": "order_total", "type": "DOUBLE"}]}),
        encoding="utf-8",
    )
    intent = interpret_intent("Create gold with final columns: customer_id, order_total.")

    plan = infer_transformation_plan(intent, schema_path=str(schema))

    assert plan.shape_columns == {"customer_id": "customerId", "order_total": "order_total"}
    assert [step.action for step in plan.steps] == ["rename", "select"]
    assert plan.decisions_required == []


def test_infer_transformation_plan_adds_safe_numeric_casts_when_target_schema_is_available(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps(
            {
                "source_columns": [{"name": "quantity", "type": "INT"}],
                "target_columns": [{"name": "quantity", "type": "DOUBLE"}],
            }
        ),
        encoding="utf-8",
    )
    intent = interpret_intent("Create gold with final columns: quantity.")

    plan = infer_transformation_plan(intent, schema_path=str(schema))

    assert plan.shape_columns == {"quantity": "CAST(quantity AS DOUBLE)"}
    assert plan.steps[0].action == "cast"
    assert plan.decisions_required == []


def test_infer_transformation_plan_requires_review_for_unsafe_casts(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps(
            {
                "source_columns": [{"name": "event_date", "type": "STRING"}],
                "target_columns": [{"name": "event_date", "type": "DATE"}],
            }
        ),
        encoding="utf-8",
    )
    intent = interpret_intent("Create gold with final columns: event_date.")

    plan = infer_transformation_plan(intent, schema_path=str(schema))

    assert plan.shape_columns == {}
    assert plan.steps[0].action == "review_required"
    assert plan.decisions_required[0].path == "transform.shape.columns.event_date"


def test_infer_transformation_plan_requires_review_for_ambiguous_renames(tmp_path: Path):
    schema = tmp_path / "orders.json"
    schema.write_text(
        json.dumps({"columns": [{"name": "customerId"}, {"name": "customer_id"}]}),
        encoding="utf-8",
    )
    intent = interpret_intent("Create gold with final columns: customerid.")

    plan = infer_transformation_plan(intent, schema_path=str(schema))

    assert plan.shape_columns == {}
    assert plan.steps[0].action == "review_required"
    assert plan.decisions_required[0].options == ["customerId", "customer_id"]


def test_infer_transformation_plan_flattens_nested_json_sample_paths(tmp_path: Path):
    sample = tmp_path / "order_sample.json"
    sample.write_text(
        json.dumps(
            {
                "order": {"id": "O-1", "total": 42.5},
                "customer": {"id": "C-1"},
            }
        ),
        encoding="utf-8",
    )
    intent = interpret_intent("Create gold with final columns: order_id, order_total, customer_id.")

    plan = infer_transformation_plan(intent, schema_path=str(sample))

    assert plan.shape_columns == {
        "order_id": "order.id",
        "order_total": "order.total",
        "customer_id": "customer.id",
    }
    assert [step.action for step in plan.steps] == ["rename", "rename", "rename"]
    assert plan.decisions_required == []


def test_infer_transformation_plan_requires_review_for_array_sample_paths(tmp_path: Path):
    sample = tmp_path / "order_sample.json"
    sample.write_text(
        json.dumps(
            {
                "order_id": "O-1",
                "items": [{"sku": "SKU-1", "quantity": 2}],
            }
        ),
        encoding="utf-8",
    )
    intent = interpret_intent("Create gold with final columns: order_id, items_sku, items_quantity.")

    plan = infer_transformation_plan(intent, schema_path=str(sample))

    assert plan.shape_columns == {"order_id": "order_id"}
    assert [step.action for step in plan.steps] == ["select", "review_required", "review_required"]
    assert [decision.path for decision in plan.decisions_required] == [
        "transform.shape.columns.items_sku",
        "transform.shape.columns.items_quantity",
    ]
