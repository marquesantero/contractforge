"""Project dependency graph helpers for AWS orchestration."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9_]+")


def dependency_waves(steps: Sequence[Mapping[str, Any]]) -> tuple[tuple[Mapping[str, Any], ...], ...]:
    """Return conservative execution waves from ``project.yaml.execution_order``.

    Each wave can run in parallel. Later waves wait for all earlier work, which
    preserves dependency safety even for DAG shapes that Step Functions cannot
    express with a simple linear chain.
    """

    by_name = {_step_name(step): step for step in steps}
    pending = dict(by_name)
    completed: set[str] = set()
    waves: list[tuple[Mapping[str, Any], ...]] = []
    while pending:
        ready_names = [
            name
            for name, step in pending.items()
            if (_dependencies(step) & set(by_name)).issubset(completed)
        ]
        if not ready_names:
            unresolved = ", ".join(sorted(pending))
            raise ValueError(f"project execution_order contains cyclic or unknown dependencies: {unresolved}")
        waves.append(tuple(pending.pop(name) for name in ready_names))
        completed.update(ready_names)
    return tuple(waves)


def state_key(value: str) -> str:
    text = _SAFE_KEY_RE.sub("_", str(value).strip()).strip("_")
    return text or "contractforge_step"


def _step_name(step: Mapping[str, Any]) -> str:
    name = str(step.get("name") or "").strip()
    if not name:
        raise ValueError("project execution_order entries require name")
    return name


def _dependencies(step: Mapping[str, Any]) -> set[str]:
    raw = step.get("depends_on") or ()
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, Sequence):
        return {str(item) for item in raw}
    raise ValueError(f"project step {_step_name(step)!r} has invalid depends_on")
