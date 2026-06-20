import sys
import types

from contractforge_ai.validation import validate_with_contractforge


def test_validate_with_contractforge_fails_when_package_is_unavailable(monkeypatch):
    def fail_import(name):
        if name == "contractforge_core.contracts":
            raise ModuleNotFoundError("No module named 'contractforge_core'", name="contractforge_core")
        raise AssertionError(name)

    monkeypatch.setattr("contractforge_ai.validation.contractforge.import_module", fail_import)

    result = validate_with_contractforge({"source": {"path": "x"}, "target": {"table": "t"}, "mode": "scd0_append"})

    assert result.status == "FAIL"
    assert result.findings[0].code == "contractforge.validation.package_unavailable"
    assert result.findings[0].severity == "critical"


def test_validate_with_contractforge_fails_when_package_dependency_is_unavailable(monkeypatch):
    def fail_import(name):
        if name == "contractforge_core.contracts":
            raise ModuleNotFoundError("No module named 'pydantic'", name="pydantic")
        raise AssertionError(name)

    monkeypatch.setattr("contractforge_ai.validation.contractforge.import_module", fail_import)

    result = validate_with_contractforge({"source": {"path": "x"}, "target": {"table": "t"}, "mode": "scd0_append"})

    assert result.status == "FAIL"
    assert result.findings[0].code == "contractforge.validation.dependency_unavailable"
    assert result.findings[0].severity == "critical"
    assert "pydantic" in result.findings[0].detail


def test_validate_with_contractforge_passes_when_plan_build_succeeds(monkeypatch):
    contracts_module = types.ModuleType("contractforge_core.contracts")

    def semantic_contract_from_mapping(contract):
        assert "_metadata" not in contract
        return types.SimpleNamespace(
            target=types.SimpleNamespace(name=contract["target"]["table"], layer=contract.get("layer")),
            write=types.SimpleNamespace(mode=contract["mode"]),
        )

    contracts_module.semantic_contract_from_mapping = semantic_contract_from_mapping
    monkeypatch.setitem(sys.modules, "contractforge_core", types.ModuleType("contractforge_core"))
    monkeypatch.setitem(sys.modules, "contractforge_core.contracts", contracts_module)

    result = validate_with_contractforge(
        {
            "_metadata": {"draft": True},
            "source": {"path": "x"},
            "target": {"table": "t"},
            "layer": "bronze",
            "mode": "scd0_append",
        }
    )

    assert result.status == "PASS"
    assert result.findings == []
    assert result.traceability.evidence[0].value["target_table"] == "t"


def test_validate_with_contractforge_fails_when_plan_build_rejects_contract(monkeypatch):
    contracts_module = types.ModuleType("contractforge_core.contracts")

    def semantic_contract_from_mapping(contract):
        del contract
        raise ValueError("target.table is required")

    contracts_module.semantic_contract_from_mapping = semantic_contract_from_mapping
    monkeypatch.setitem(sys.modules, "contractforge_core", types.ModuleType("contractforge_core"))
    monkeypatch.setitem(sys.modules, "contractforge_core.contracts", contracts_module)

    result = validate_with_contractforge({"source": {"path": "x"}, "target": {}, "mode": "scd0_append"})

    assert result.status == "FAIL"
    assert result.findings[0].code == "contractforge.validation.contract_rejected"
    assert "target.table is required" in result.findings[0].detail
