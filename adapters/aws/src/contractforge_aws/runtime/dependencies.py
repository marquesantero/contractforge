"""Optional AWS runtime dependency loading."""

from __future__ import annotations

import importlib
from types import ModuleType


def require_boto3() -> ModuleType:
    try:
        return importlib.import_module("boto3")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "AWS runtime helpers require the optional runtime dependencies. "
            "Install with: pip install 'contractforge-aws[runtime]'."
        ) from exc
