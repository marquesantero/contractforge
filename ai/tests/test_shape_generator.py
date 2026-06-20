import json
from pathlib import Path

from contractforge_ai.cli import main
from contractforge_ai.generators.shape import suggest_shape


def test_suggest_shape_discovers_nested_struct_and_array(tmp_path: Path):
    sample = tmp_path / "sample.json"
    sample.write_text(
        json.dumps(
            {
                "id": "evt-1",
                "properties": {
                    "mag": 2.1,
                    "place": "10 km S",
                    "time": 1710000000000,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [-122.1, 37.1, 10.0],
                },
            }
        ),
        encoding="utf-8",
    )

    result = suggest_shape(sample)

    assert {"path": "id", "alias": "id"} in result.shape["select"]
    assert {"path": "properties.mag", "alias": "properties_mag"} in result.shape["select"]
    assert {"path": "geometry.type", "alias": "geometry_type"} in result.shape["select"]
    assert any(item["path"] == "geometry.coordinates" for item in result.shape["explode"])
    assert result.decisions_required
    assert result.warnings
    assert result.traceability.review_required is True
    assert result.traceability.decisions_required
    assert result.traceability.evidence[0].value["arrays"] == 1
    compile(result.python_example, "<shape-example>", "exec")
    assert "shape = {" in result.python_example
    assert '"shape": shape' in result.python_example
    assert "semantic_contract_from_mapping(contract)" in result.python_example
    assert "**'shape:" not in result.python_example


def test_suggest_shape_flags_array_of_structs(tmp_path: Path):
    sample = tmp_path / "sample.json"
    sample.write_text(
        json.dumps(
            {
                "order_id": "1",
                "items": [
                    {"sku": "A", "quantity": 2},
                    {"sku": "B", "quantity": 1},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = suggest_shape(sample)

    assert any(item["path"] == "items" and item["kind"] == "array<struct>" for item in result.discovered_paths)
    assert result.shape["explode"][0]["path"] == "items"
    assert result.shape["explode"][0]["requires_review"] is True
    assert any("row counts" in warning for warning in result.warnings)


def test_suggest_shape_flags_nested_arrays(tmp_path: Path):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"matrix": [[1, 2], [3, 4]]}), encoding="utf-8")

    result = suggest_shape(sample)

    assert any(item["path"] == "matrix[]" for item in result.discovered_paths)
    assert any("Nested arrays" in warning for warning in result.warnings)


def test_suggest_shape_cli_outputs_yaml(tmp_path: Path, capsys):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"id": "1", "payload": {"amount": 10.5}}), encoding="utf-8")

    exit_code = main(["suggest-shape", "--sample", str(sample), "--format", "yaml"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "shape:" in output
    assert "payload_amount" in output


def test_suggest_shape_rejects_scalar_sample(tmp_path: Path):
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps("not-object"), encoding="utf-8")

    try:
        suggest_shape(sample)
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("Expected ValueError")

