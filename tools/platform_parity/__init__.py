"""ContractForge platform parity test helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_local_import_paths() -> None:
    """Make local adapter packages importable for repo-local parity tools."""

    root = Path(__file__).resolve().parents[2]
    candidate_paths = (
        root / "src",
        root / "adapters" / "databricks" / "src",
        root / "adapters" / "aws" / "src",
        root / "adapters" / "snowflake" / "src",
        root / "adapters" / "fabric" / "src",
    )
    for path in candidate_paths:
        text = str(path)
        if path.exists() and text not in sys.path:
            sys.path.insert(0, text)


_bootstrap_local_import_paths()
