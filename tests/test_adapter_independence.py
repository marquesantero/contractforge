from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = {
    "contractforge_aws": ROOT / "adapters" / "aws" / "src" / "contractforge_aws",
    "contractforge_databricks": ROOT / "adapters" / "databricks" / "src" / "contractforge_databricks",
    "contractforge_fabric": ROOT / "adapters" / "fabric" / "src" / "contractforge_fabric",
    "contractforge_gcp": ROOT / "adapters" / "gcp" / "src" / "contractforge_gcp",
    "contractforge_snowflake": ROOT / "adapters" / "snowflake" / "src" / "contractforge_snowflake",
}


def test_adapters_do_not_import_other_adapters() -> None:
    offenders: list[str] = []
    for package, source_root in ADAPTERS.items():
        forbidden = set(ADAPTERS) - {package}
        for path in source_root.rglob("*.py"):
            for imported in _imported_modules(path):
                root = imported.split(".", 1)[0]
                if root in forbidden:
                    offenders.append(f"{path.relative_to(ROOT)} imports {imported}")

    assert offenders == []


def _imported_modules(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)
