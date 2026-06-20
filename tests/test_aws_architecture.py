from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "src" / "contractforge_core"
AWS_SRC = ROOT / "adapters" / "aws" / "src" / "contractforge_aws"


def test_core_does_not_depend_on_aws_adapter() -> None:
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
            offenders.extend(name for name in names if name.startswith("contractforge_aws"))

    assert offenders == []


def test_aws_package_keeps_sdk_imports_optional() -> None:
    offenders: list[str] = []
    for path in AWS_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            if "boto3" in names or "botocore" in names:
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_aws_package_avoids_god_files() -> None:
    oversized = []
    for path in AWS_SRC.rglob("*.py"):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > 220:
            oversized.append(f"{path.relative_to(ROOT)} has {line_count} lines")

    assert oversized == []


def test_aws_adapter_uses_domain_folders_for_mature_surfaces() -> None:
    expected = {
        "annotations",
        "governance",
        "quality",
        "preparation",
        "schema",
        "state",
        "evidence",
        "lineage",
    }

    assert {path.name for path in AWS_SRC.iterdir() if path.is_dir()} >= expected

    rendering_files = {path.name for path in (AWS_SRC / "rendering").glob("*.py")}
    assert not rendering_files & {
        "annotations.py",
        "dqdl.py",
        "lakeformation.py",
        "lakeformation_evidence.py",
        "quality_runtime.py",
        "preparation.py",
        "schema_runtime.py",
        "state_runtime.py",
    }
