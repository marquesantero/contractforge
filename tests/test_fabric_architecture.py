from __future__ import annotations

from pathlib import Path

from contractforge_fabric import FabricContractSmokeResult, run_fabric_contract_smoke
from contractforge_fabric.smoke import run_fabric_contract_smoke as smoke_run
from contractforge_fabric.preparation import render_shape_preparation, render_transform_preparation
from contractforge_fabric.write_modes import render_notebook_write_statement


ROOT = Path(__file__).resolve().parents[1]
FABRIC_PACKAGE = ROOT / "adapters" / "fabric" / "src" / "contractforge_fabric"


def test_fabric_adapter_uses_mature_package_boundaries() -> None:
    expected = {
        "access",
        "annotations",
        "capabilities",
        "evidence",
        "lineage",
        "operations",
        "preparation",
        "quality",
        "rendering",
        "runtime",
        "smoke",
        "sources",
        "state",
        "write_modes",
    }
    actual = {path.name for path in FABRIC_PACKAGE.iterdir() if path.is_dir() and path.name != "__pycache__"}

    assert expected <= actual
    assert not (FABRIC_PACKAGE / "runtime" / "smoke.py").exists()


def test_fabric_smoke_and_write_mode_public_imports_are_stable() -> None:
    assert smoke_run is run_fabric_contract_smoke
    assert FabricContractSmokeResult.__name__ == "FabricContractSmokeResult"
    assert callable(render_notebook_write_statement)
    assert callable(render_shape_preparation)
    assert callable(render_transform_preparation)
