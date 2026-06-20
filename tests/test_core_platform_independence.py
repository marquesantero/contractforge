from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "src" / "contractforge_core"

FORBIDDEN_CORE_IMPORTS = (
    "awsglue",
    "boto3",
    "botocore",
    "contractforge_aws",
    "contractforge_databricks",
    "contractforge_snowflake",
    "databricks",
    "pyspark",
    "snowflake",
)


def test_core_has_no_platform_sdk_or_adapter_imports() -> None:
    offenders: list[str] = []
    for path in CORE_SRC.rglob("*.py"):
        for imported in _imported_modules(path):
            if _is_forbidden(imported):
                offenders.append(f"{path.relative_to(ROOT)} imports {imported}")

    assert offenders == []


def _imported_modules(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def _is_forbidden(module: str) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_CORE_IMPORTS)
