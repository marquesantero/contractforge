"""Artifact loading helpers for the Snowflake runtime."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.request import url2pathname
from urllib.parse import urlparse

MAX_RUNTIME_ARTIFACT_BYTES = 5_000_000
_STAGE_ARTIFACT_RE = re.compile(r'^@[A-Za-z0-9_.$/"\-/]+$')


def load_json_artifact(uri: str, *, session: Any | None = None) -> dict[str, Any]:
    loader = _LOADERS[_artifact_kind(uri)]
    payload = loader(uri, session)
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object artifact: {uri}")
    return data


def _artifact_kind(uri: str) -> str:
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme == "file":
        return "file"
    if uri.startswith("@"):
        return "stage"
    return "local"


def _load_local(uri: str, session: Any | None) -> str:
    path = Path(uri)
    _validate_local_size(path, uri)
    return path.read_text(encoding="utf-8")


def _load_file(uri: str, session: Any | None) -> str:
    path = Path(url2pathname(urlparse(uri).path))
    _validate_local_size(path, uri)
    return path.read_text(encoding="utf-8")


def _load_stage(uri: str, session: Any | None) -> str:
    _validate_stage_artifact_uri(uri)
    if session is None or not hasattr(session, "file"):
        raise ValueError("Snowflake stage artifact loading requires a Snowpark session with file access")
    stream = session.file.get_stream(uri)
    with stream:
        payload = stream.read()
    _validate_payload_size(payload, uri)
    return payload.decode("utf-8") if isinstance(payload, bytes) else str(payload)


def _validate_local_size(path: Path, uri: str) -> None:
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size > MAX_RUNTIME_ARTIFACT_BYTES:
        raise ValueError(f"Snowflake runtime artifact is too large: {uri}")


def _validate_payload_size(payload: bytes | str, uri: str) -> None:
    size = len(payload.encode("utf-8")) if isinstance(payload, str) else len(payload)
    if size > MAX_RUNTIME_ARTIFACT_BYTES:
        raise ValueError(f"Snowflake runtime artifact is too large: {uri}")


def _validate_stage_artifact_uri(uri: str) -> None:
    if not _STAGE_ARTIFACT_RE.match(uri) or ".." in uri.split("/"):
        raise ValueError(f"Unsafe Snowflake stage artifact URI: {uri}")


_LOADERS: dict[str, Callable[[str, Any | None], str]] = {
    "file": _load_file,
    "local": _load_local,
    "stage": _load_stage,
}


__all__ = ["MAX_RUNTIME_ARTIFACT_BYTES", "load_json_artifact"]
