"""Authentication helpers for Fabric runtime clients."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable

FABRIC_RESOURCE = "https://api.fabric.microsoft.com"

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class AzureCliFabricTokenProvider:
    """Acquire Microsoft Fabric API tokens through Azure CLI."""

    tenant_id: str | None = None
    resource: str = FABRIC_RESOURCE
    command: str = "az"
    runner: CommandRunner | None = None

    def __call__(self) -> str:
        args = [self.command, "account", "get-access-token", "--resource", self.resource, "-o", "json"]
        if self.tenant_id:
            args.extend(["--tenant", self.tenant_id])
        completed = (self.runner or _run_command)(args)
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(f"Azure CLI could not acquire a Fabric token{': ' + stderr if stderr else ''}")
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("Azure CLI returned invalid JSON while acquiring a Fabric token") from exc
        token = payload.get("accessToken")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Azure CLI Fabric token response did not include accessToken")
        return token


def _run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    command = shutil.which(args[0]) or args[0]
    return subprocess.run(
        [command, *args[1:]],
        check=False,
        capture_output=True,
        text=True,
    )
