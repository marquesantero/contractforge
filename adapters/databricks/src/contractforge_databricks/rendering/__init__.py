from __future__ import annotations

from typing import Any


def render_databricks_artifacts(*args: Any, **kwargs: Any) -> Any:
    from contractforge_databricks.rendering.bundle import render_databricks_artifacts as _render

    return _render(*args, **kwargs)

__all__ = ["render_databricks_artifacts"]
