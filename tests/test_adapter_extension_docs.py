from __future__ import annotations

import re
from pathlib import Path

from contractforge_aws.contract_extensions import AWS_EXTENSION_FIELDS
from contractforge_databricks.contract_extensions import DATABRICKS_EXTENSION_FIELDS


ROOT = Path(__file__).resolve().parents[1]


def test_databricks_extension_spec_matches_adapter_allowlist() -> None:
    documented = _extension_table_keys(ROOT / "docs" / "specs" / "extensions-databricks.md")

    assert documented == DATABRICKS_EXTENSION_FIELDS


def test_aws_extension_spec_matches_adapter_allowlist() -> None:
    documented = _extension_table_keys(ROOT / "docs" / "specs" / "extensions-aws.md")

    assert documented == AWS_EXTENSION_FIELDS


def _extension_table_keys(path: Path) -> set[str]:
    return set(re.findall(r"^\| `([^`]+)` \|", path.read_text(encoding="utf-8"), re.M))
