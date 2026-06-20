from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "adapters" / "databricks" / "src" / "contractforge_databricks" / "preparation" / "pyspark.py"
STAGING_MODULE = ROOT / "adapters" / "databricks" / "src" / "contractforge_databricks" / "preparation" / "pyspark_staging.py"


def test_pyspark_preparation_uses_lazy_imports_only() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    top_level_imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.append(node.module)

    assert "pyspark.sql" not in top_level_imports


def test_pyspark_preparation_exposes_expected_functions() -> None:
    content = STAGING_MODULE.read_text(encoding="utf-8")

    assert "def with_row_hash" in content
    assert "def prepare_hash_diff_stage" in content
    assert "def prepare_snapshot_stage" in content
    assert "def prepare_scd2_stage" in content
    assert "spec.effective_from_column" in content
    assert 'F.col(spec.effective_from_column).cast("timestamp")' in content
    assert "def apply_write_staging" in content
    assert "createOrReplaceTempView" in MODULE.read_text(encoding="utf-8")
