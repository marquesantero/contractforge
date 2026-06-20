"""AWS adapter subtarget registry."""

from __future__ import annotations

from typing import Any, Callable

from contractforge_aws.adapter import AWSAdapter
from contractforge_aws.capabilities import AWS_SUBTARGET_GLUE_ICEBERG

_ADAPTER_FACTORIES: dict[str, Callable[..., AWSAdapter]] = {
    AWS_SUBTARGET_GLUE_ICEBERG: AWSAdapter.glue_iceberg,
}


def adapter_for_subtarget(subtarget: str, *, environment: dict[str, Any] | None = None) -> AWSAdapter:
    try:
        return _ADAPTER_FACTORIES[subtarget](environment=environment)
    except KeyError as exc:
        raise ValueError(f"Unsupported AWS adapter subtarget: {subtarget}") from exc


def validate_aws_subtarget(subtarget: str) -> None:
    adapter_for_subtarget(subtarget)


def list_aws_subtargets() -> tuple[str, ...]:
    return tuple(_ADAPTER_FACTORIES)
