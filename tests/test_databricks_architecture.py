from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "src" / "contractforge_core"
DBX_SRC = ROOT / "adapters" / "databricks" / "src" / "contractforge_databricks"
COMPATIBILITY_MODULES = {
    "contractforge_databricks.evidence.records",
    "contractforge_databricks.execution.results",
    "contractforge_databricks.parity.models",
    "contractforge_databricks.preparation.staging",
    "contractforge_databricks.quality.results",
    "contractforge_databricks.results",
    "contractforge_databricks.schema.diff",
    "contractforge_databricks.security.errors",
    "contractforge_databricks.security.redaction",
}
ALLOWED_DATABRICKS_DATACLASSES = {
    "DatabricksAdapter",
    "DatabricksCapabilities",
    "DatabricksEnvironment",
    "DatabricksIngestOptions",
    "DatabricksIngestionHooks",
    "DatabricksJobSpec",
    "DatabricksNotebookTaskSpec",
    "DatabricksSourceClassification",
    "HashDiffLatestSelection",
    "CostModel",
    "ControlRetentionTarget",
    "LakeflowAutoCdcArtifact",
    "LakeflowCompatibility",
    "MaintenancePlan",
}


def test_core_does_not_depend_on_databricks_adapter() -> None:
    offenders: list[str] = []
    for path in CORE_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            offenders.extend(name for name in names if name.startswith("contractforge_databricks"))

    assert offenders == []


def test_databricks_package_keeps_pyspark_import_optional() -> None:
    offenders: list[str] = []
    allowed = {
        DBX_SRC / "runtime" / "detection.py",
        DBX_SRC / "runtime" / "spark.py",
        DBX_SRC / "preparation" / "deduplicate.py",
        DBX_SRC / "preparation" / "shape.py",
        DBX_SRC / "preparation" / "shape_validation.py",
        DBX_SRC / "preparation" / "zip_arrays.py",
        DBX_SRC / "preparation" / "pyspark.py",
        DBX_SRC / "preparation" / "pyspark_staging.py",
    }
    for path in DBX_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            if "pyspark" in names and path not in allowed:
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_databricks_package_avoids_god_files() -> None:
    oversized = []
    for path in DBX_SRC.rglob("*.py"):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 220:
            oversized.append(f"{path.relative_to(ROOT)} has {line_count} lines")

    assert oversized == []


def test_databricks_compatibility_modules_are_reexports_only() -> None:
    offenders = []
    for module in COMPATIBILITY_MODULES:
        path = DBX_SRC.joinpath(*module.removeprefix("contractforge_databricks.").split(".")).with_suffix(".py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        executable_nodes = [
            node
            for node in tree.body
            if not isinstance(node, (ast.Expr, ast.Import, ast.ImportFrom, ast.Assign))
        ]
        if executable_nodes:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_databricks_dataclasses_are_adapter_specific() -> None:
    discovered = set()
    for path in DBX_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            decorators = {
                item.id
                for item in node.decorator_list
                if isinstance(item, ast.Name)
            }
            decorators.update(
                item.func.id
                for item in node.decorator_list
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
            )
            if "dataclass" in decorators:
                discovered.add(node.name)

    assert discovered <= ALLOWED_DATABRICKS_DATACLASSES
