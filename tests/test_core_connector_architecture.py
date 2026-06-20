from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONNECTORS = ROOT / "src" / "contractforge_core" / "connectors"
ADAPTERS = ROOT / "adapters"


def test_connector_init_files_are_facades_only() -> None:
    offenders: list[str] = []

    for path in CONNECTORS.rglob("__init__.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Assign) and all(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                continue
            offenders.append(f"{path.relative_to(ROOT)} contains {type(node).__name__}")

    assert offenders == []


def test_file_and_catalog_connectors_are_package_owned() -> None:
    assert not (CONNECTORS / "files.py").exists()
    assert (CONNECTORS / "files" / "files" / "source.py").exists()
    assert (CONNECTORS / "catalog" / "catalog" / "source.py").exists()


def test_stream_connectors_are_package_owned() -> None:
    assert not (CONNECTORS / "bounded_streams.py").exists()
    assert (CONNECTORS / "streams" / "kafka" / "source.py").exists()
    assert (CONNECTORS / "streams" / "eventhubs" / "source.py").exists()


def test_jdbc_connector_is_package_owned() -> None:
    assert not (CONNECTORS / "jdbc.py").exists()
    assert not (CONNECTORS / "rds_iam.py").exists()
    assert (CONNECTORS / "databases" / "jdbc" / "source.py").exists()
    assert (CONNECTORS / "databases" / "jdbc" / "rds_iam.py").exists()


def test_adapters_do_not_import_private_core_connector_symbols() -> None:
    offenders: list[str] = []

    for path in ADAPTERS.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if not node.module.startswith("contractforge_core.connectors"):
                continue
            for alias in node.names:
                if alias.name.startswith("_"):
                    offenders.append(f"{path.relative_to(ROOT)} imports {node.module}.{alias.name}")

    assert offenders == []
