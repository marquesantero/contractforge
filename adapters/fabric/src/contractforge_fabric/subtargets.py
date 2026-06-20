"""Fabric adapter subtarget registry."""

from __future__ import annotations

from typing import Any, Callable

from contractforge_fabric.adapter import FabricAdapter
from contractforge_fabric.capabilities import FABRIC_SUBTARGET_LAKEHOUSE

_ADAPTER_FACTORIES: dict[str, Callable[..., FabricAdapter]] = {
    FABRIC_SUBTARGET_LAKEHOUSE: FabricAdapter.lakehouse,
}


def adapter_for_subtarget(subtarget: str, *, environment: dict[str, Any] | None = None) -> FabricAdapter:
    try:
        return _ADAPTER_FACTORIES[subtarget](environment=environment)
    except KeyError as exc:
        raise ValueError(f"Unsupported Fabric adapter subtarget: {subtarget}") from exc


def validate_fabric_subtarget(subtarget: str) -> None:
    adapter_for_subtarget(subtarget)


def list_fabric_subtargets() -> tuple[str, ...]:
    return tuple(_ADAPTER_FACTORIES)
