"""Runtime Secret Manager resolution for GCP source credentials."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

from contractforge_gcp.security.secrets import SECRET_PLACEHOLDER_RE

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def resolve_gcp_secret_placeholders(
    value: Any, *, project_id: str | None = None, runner: CommandRunner | None = None
) -> Any:
    """Resolve ``{{ secret:scope/key }}`` placeholders with Google Secret Manager.

    Rendered artifacts keep placeholders/redacted metadata only. This function is
    intentionally called at smoke/runtime execution time immediately before the
    shared core HTTP/REST readers build auth headers.
    """

    command_runner = runner or _run_command
    if isinstance(value, str):
        return SECRET_PLACEHOLDER_RE.sub(lambda match: _access_secret(match.group(1), project_id, command_runner), value)
    if isinstance(value, dict):
        return {
            key: resolve_gcp_secret_placeholders(item, project_id=project_id, runner=command_runner)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [resolve_gcp_secret_placeholders(item, project_id=project_id, runner=command_runner) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_gcp_secret_placeholders(item, project_id=project_id, runner=command_runner) for item in value)
    return value


def _access_secret(ref: str, project_id: str | None, runner: CommandRunner) -> str:
    secret_id = _secret_id(ref)
    command = ["gcloud", "secrets", "versions", "access", "latest", f"--secret={secret_id}"]
    if project_id:
        command.append(f"--project={project_id}")
    completed = runner(tuple(command))
    if completed.returncode != 0:
        raise RuntimeError(_command_error(completed, secret_id=secret_id))
    return completed.stdout.rstrip("\r\n")


def _secret_id(ref: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", ref.strip()).strip("-")
    if not value:
        raise ValueError("Secret placeholder must include a non-empty scope/key reference.")
    return value


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    resolved = list(command)
    if resolved:
        resolved[0] = shutil.which(resolved[0]) or resolved[0]
    return subprocess.run(resolved, check=False, capture_output=True, text=True)


def _command_error(completed: subprocess.CompletedProcess[str], *, secret_id: str) -> str:
    message = (completed.stderr or completed.stdout or f"Secret Manager access failed for {secret_id}").strip()
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted-email>", message)
