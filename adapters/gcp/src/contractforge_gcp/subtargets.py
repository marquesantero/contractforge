"""GCP adapter subtarget registry."""

from __future__ import annotations

from typing import Any, Callable

from contractforge_gcp.adapter import GCPAdapter
from contractforge_gcp.capabilities import GCP_SUBTARGET_BIGQUERY

_ADAPTER_FACTORIES: dict[str, Callable[..., GCPAdapter]] = {GCP_SUBTARGET_BIGQUERY: GCPAdapter.bigquery}


def adapter_for_subtarget(subtarget: str, *, environment: dict[str, Any] | None = None) -> GCPAdapter:
    try:
        return _ADAPTER_FACTORIES[subtarget](environment=environment)
    except KeyError as exc:
        raise ValueError(f"Unsupported GCP adapter subtarget: {subtarget}") from exc


def validate_gcp_subtarget(subtarget: str) -> None:
    adapter_for_subtarget(subtarget)


def list_gcp_subtargets() -> tuple[str, ...]:
    return tuple(_ADAPTER_FACTORIES)
