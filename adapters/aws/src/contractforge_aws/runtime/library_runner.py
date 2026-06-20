"""Generic AWS Glue runner for ContractForge contracts.

Glue requires a Python ``ScriptLocation``. In library-runner mode that script is
stable and tiny; this module loads the contract/environment from S3 or local
paths, renders the same reviewed Glue runtime body the adapter already
certifies, and executes it in the current Glue process.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from typing import Any
from urllib.parse import urlparse

import yaml

from contractforge_aws.api import render_aws_contract
from contractforge_aws.runtime.dependencies import require_boto3
from contractforge_aws.runtime_args import CONTRACT_URI_ARG, ENVIRONMENT_URI_ARG, RUNTIME_MODE_ARG

MAX_RUNTIME_ARTIFACT_BYTES = 5_000_000


def main(argv: list[str] | None = None) -> int:
    """Entrypoint used by the stable Glue runner script."""

    args = list(sys.argv if argv is None else argv)
    contract_uri = _required_runtime_arg(args, CONTRACT_URI_ARG)
    environment_uri = _runtime_arg(args, ENVIRONMENT_URI_ARG)
    runtime_mode = _runtime_arg(args, RUNTIME_MODE_ARG, "library_runner")
    if runtime_mode != "library_runner":
        raise ValueError(f"{RUNTIME_MODE_ARG} must be 'library_runner', got {runtime_mode!r}")

    contract = load_mapping_uri(contract_uri)
    environment = load_mapping_uri(environment_uri) if environment_uri else None
    generated = _render_runtime_script(contract, environment=environment)
    _validate_rendered_runtime_script(generated)
    namespace: dict[str, Any] = {"__name__": "__contractforge_aws_library_runner__"}
    exec(compile(generated, f"<contractforge:{contract_uri}>", "exec"), namespace)
    return 0


def load_mapping_uri(uri: str) -> dict[str, Any]:
    """Load a YAML/JSON object from an S3 URI or local path."""

    text = load_text_uri(uri)
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"ContractForge runtime URI must contain a mapping: {uri}")
    return loaded


def load_text_uri(uri: str) -> str:
    parsed = urlparse(str(uri).strip())
    if parsed.scheme == "s3":
        if not parsed.netloc or not parsed.path.strip("/"):
            raise ValueError(f"Invalid S3 URI: {uri!r}")
        client = require_boto3().client("s3")
        response = client.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
        _validate_content_length(response.get("ContentLength"), uri)
        body = response["Body"].read()
        _validate_payload_size(body, uri)
        return body.decode("utf-8")
    is_windows_path = len(parsed.scheme) == 1 and str(uri)[1:3] in {":\\", ":/"}
    if parsed.scheme and parsed.scheme != "file" and not is_windows_path:
        raise ValueError(f"Unsupported ContractForge runtime URI scheme: {parsed.scheme!r}")
    path = parsed.path if parsed.scheme == "file" else str(uri)
    _validate_local_size(path, uri)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _render_runtime_script(contract: dict[str, Any], *, environment: dict[str, Any] | None) -> str:
    artifacts = render_aws_contract(contract, environment=environment).artifacts
    for name, body in sorted(artifacts.items()):
        if name.endswith(".glue_job.py"):
            return str(body)
    raise RuntimeError("ContractForge AWS library runner could not render a Glue runtime script")


def _validate_rendered_runtime_script(source: str) -> None:
    """Reject obviously unsafe generated runtime bodies before execution.

    This is not a sandbox. The AWS runner only executes scripts produced by the
    adapter renderer for trusted contracts. The validation is a defense-in-depth
    guard against accidental renderer regressions that would introduce dynamic
    execution or process-spawning primitives into the stable runner path.
    """

    tree = ast.parse(source)
    for node in ast.walk(tree):
        call_name = _call_name(node) if isinstance(node, ast.Call) else None
        if call_name in _FORBIDDEN_CALLS:
            raise ValueError(f"Unsafe AWS runtime script call is not allowed: {call_name}")
        if isinstance(node, ast.Import):
            _validate_imports(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            _validate_imports((node.module,))


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = [func.attr]
        owner = func.value
        while isinstance(owner, ast.Attribute):
            parts.append(owner.attr)
            owner = owner.value
        if isinstance(owner, ast.Name):
            parts.append(owner.id)
        return ".".join(reversed(parts))
    return None


def _validate_imports(modules: Any) -> None:
    for module in modules:
        root = str(module).split(".", 1)[0]
        if root in _FORBIDDEN_IMPORT_ROOTS:
            raise ValueError(f"Unsafe AWS runtime script import is not allowed: {module}")


def _validate_content_length(content_length: Any, uri: str) -> None:
    if content_length is not None and int(content_length) > MAX_RUNTIME_ARTIFACT_BYTES:
        raise ValueError(f"ContractForge runtime artifact is too large: {uri}")


def _validate_payload_size(payload: bytes, uri: str) -> None:
    if len(payload) > MAX_RUNTIME_ARTIFACT_BYTES:
        raise ValueError(f"ContractForge runtime artifact is too large: {uri}")


def _validate_local_size(path: str, uri: str) -> None:
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size > MAX_RUNTIME_ARTIFACT_BYTES:
        raise ValueError(f"ContractForge runtime artifact is too large: {uri}")


def _runtime_arg(args: list[str], name: str, default: str | None = None) -> str | None:
    flag = f"--{name}"
    for idx, value in enumerate(args):
        if value == flag and idx + 1 < len(args):
            return args[idx + 1]
        if value.startswith(flag + "="):
            return value.split("=", 1)[1]
    return default


def _required_runtime_arg(args: list[str], name: str) -> str:
    value = _runtime_arg(args, name)
    if not value:
        raise ValueError(f"Missing required Glue runtime argument --{name}")
    return value


__all__ = [
    "CONTRACT_URI_ARG",
    "ENVIRONMENT_URI_ARG",
    "MAX_RUNTIME_ARTIFACT_BYTES",
    "RUNTIME_MODE_ARG",
    "load_mapping_uri",
    "load_text_uri",
    "main",
]

_FORBIDDEN_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "execfile",
    "open",
    "pathlib.Path.open",
    "Path.open",
    "os.popen",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.rmdir",
    "os.spawnl",
    "os.spawnle",
    "os.spawnlp",
    "os.spawnlpe",
    "os.spawnv",
    "os.spawnve",
    "os.spawnvp",
    "os.spawnvpe",
    "os.system",
    "shutil.rmtree",
    "shutil.move",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
    "subprocess.run",
}

_FORBIDDEN_IMPORT_ROOTS = {"subprocess", "shutil"}
