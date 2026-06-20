import ast
from pathlib import Path


AI_SRC = Path(__file__).resolve().parents[1] / "src" / "contractforge_ai"
DISALLOWED_TOP_LEVEL_IMPORTS = (
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


def test_ai_package_has_no_top_level_adapter_or_platform_sdk_imports():
    offenders: list[str] = []
    for path in AI_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            for imported in _top_level_imports(node):
                if _is_disallowed(imported):
                    offenders.append(f"{path.relative_to(AI_SRC)} imports {imported}")

    assert offenders == []


def _top_level_imports(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return (node.module,)
    return ()


def _is_disallowed(module: str) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in DISALLOWED_TOP_LEVEL_IMPORTS)
