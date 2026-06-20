"""Publish Snowflake runtime artifacts to a stage."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from contractforge_snowflake.api import build_snowflake_publish_bundle
from contractforge_snowflake.connection_options import validate_connect_options
from contractforge_snowflake.environment import SnowflakeEnvironment

_STAGE_RE = re.compile(r"^@[A-Za-z0-9_.$/\"]+$")
ConnectionFactory = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class SnowflakePublishedArtifact:
    name: str
    uri: str
    bytes: int


@dataclass(frozen=True)
class SnowflakeStagePublishResult:
    stage: str
    prefix: str
    execution_model: str
    artifacts: tuple[SnowflakePublishedArtifact, ...]

    @property
    def manifest_uri(self) -> str:
        for artifact in self.artifacts:
            if artifact.name == "snowflake.publish_manifest.json":
                return artifact.uri
        raise RuntimeError("Snowflake publish manifest was not published")


def publish_snowflake_contract(
    contract: dict[str, Any],
    *,
    environment: dict[str, Any] | None = None,
    stage: str | None = None,
    prefix: str | None = None,
    connection: Any | None = None,
    connect_options: dict[str, Any] | None = None,
    connection_factory: ConnectionFactory | None = None,
) -> SnowflakeStagePublishResult:
    """Publish a contract bundle to a Snowflake stage.

    The published files are consumed by the stable ContractForge Snowflake
    runner. This function does not generate per-contract ingestion SQL.
    """

    env = SnowflakeEnvironment.from_contract(environment)
    destination = _resolve_destination(stage=stage, prefix=prefix, artifact_uri=env.artifact_uri)
    bundle = build_snowflake_publish_bundle(contract, environment=environment)
    owner = _ConnectionOwner(connection=connection, connect_options=connect_options, connection_factory=connection_factory)
    try:
        with tempfile.TemporaryDirectory(prefix="contractforge-snowflake-") as tmpdir:
            published = tuple(
                _publish_one(
                    owner.connection,
                    name=name,
                    body=body,
                    root=Path(tmpdir),
                    stage=destination.stage,
                    prefix=destination.prefix,
                )
                for name, body in sorted(bundle.artifacts.items())
            )
    finally:
        owner.close()
    return SnowflakeStagePublishResult(
        stage=destination.stage,
        prefix=destination.prefix,
        execution_model="library_runner",
        artifacts=published,
    )


@dataclass(frozen=True)
class _StageDestination:
    stage: str
    prefix: str


class _ConnectionOwner:
    def __init__(
        self,
        *,
        connection: Any | None,
        connect_options: dict[str, Any] | None,
        connection_factory: ConnectionFactory | None,
    ) -> None:
        self._owns_connection = connection is None
        self.connection = connection or _connect_with_factory(connect_options or {}, connection_factory=connection_factory)

    def close(self) -> None:
        if self._owns_connection and hasattr(self.connection, "close"):
            self.connection.close()


def _resolve_destination(*, stage: str | None, prefix: str | None, artifact_uri: str | None) -> _StageDestination:
    uri_stage, uri_prefix = _parse_artifact_uri(artifact_uri)
    resolved_stage = _validate_stage(stage or uri_stage)
    resolved_prefix = _normalize_prefix(prefix if prefix is not None else uri_prefix)
    return _StageDestination(stage=resolved_stage, prefix=resolved_prefix)


def _parse_artifact_uri(artifact_uri: str | None) -> tuple[str | None, str]:
    if not artifact_uri:
        return None, ""
    text = artifact_uri.strip()
    if text.startswith("snowflake://"):
        text = text[len("snowflake://") :]
    if not text.startswith("@"):
        return None, _normalize_prefix(text)
    stage, _, path = text.partition("/")
    return stage, _normalize_prefix(path)


def _publish_one(connection: Any, *, name: str, body: str, root: Path, stage: str, prefix: str) -> SnowflakePublishedArtifact:
    relative = _safe_artifact_path(name)
    local_path = root / Path(*relative.parts)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(body, encoding="utf-8")
    target = _stage_target(stage=stage, prefix=prefix, artifact_parent=relative.parent)
    _execute_put(connection, local_path=local_path, target=target)
    return SnowflakePublishedArtifact(name=name, uri=f"{target}/{relative.name}", bytes=len(body.encode("utf-8")))


def _execute_put(connection: Any, *, local_path: Path, target: str) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(f"PUT '{_file_uri(local_path)}' {target} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
    finally:
        if hasattr(cursor, "close"):
            cursor.close()


def _stage_target(*, stage: str, prefix: str, artifact_parent: PurePosixPath) -> str:
    parts = [stage.rstrip("/")]
    if prefix:
        parts.append(prefix.strip("/"))
    parent = str(artifact_parent).strip(".")
    if parent:
        parts.append(parent.strip("/"))
    return "/".join(parts)


def _safe_artifact_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe Snowflake artifact name: {name}")
    return path


def _validate_stage(stage: str | None) -> str:
    if not stage:
        raise ValueError("Snowflake publish requires a stage or environment.artifacts.uri")
    text = stage.strip().rstrip("/")
    if not _STAGE_RE.match(text):
        raise ValueError(f"Unsafe Snowflake stage reference: {stage}")
    return text


def _normalize_prefix(prefix: str | None) -> str:
    text = (prefix or "").strip().strip("/")
    if ".." in PurePosixPath(text).parts:
        raise ValueError(f"Unsafe Snowflake artifact prefix: {prefix}")
    return text


def _file_uri(path: Path) -> str:
    return "file://" + path.resolve().as_posix().replace("'", "''")


def _connect_with_factory(options: dict[str, Any], *, connection_factory: ConnectionFactory | None) -> Any:
    connect_options = validate_connect_options(options)
    if connection_factory is not None:
        return connection_factory(connect_options)
    return _connect(connect_options)


def _connect(options: dict[str, Any]) -> Any:
    connect_options = validate_connect_options(options)
    try:
        import snowflake.connector
    except ImportError as exc:  # pragma: no cover - exercised only without injected connection
        raise RuntimeError(
            "Publishing to Snowflake requires the runtime extra: pip install contractforge-snowflake[runtime]"
        ) from exc
    return snowflake.connector.connect(**connect_options)
