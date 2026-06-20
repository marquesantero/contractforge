"""Databricks runtime file path selection helpers."""

from __future__ import annotations

import os
import re
from typing import Any


def selected_file_load_path(spark: Any, source: dict[str, Any], options: dict[str, str]) -> object:
    path = source.get("path")
    if not path:
        return path
    read = source.get("read") if isinstance(source.get("read"), dict) else {}
    pattern_text = str(read.get("file_regex") or "").strip()
    if not pattern_text:
        return path
    try:
        pattern = re.compile(pattern_text)
    except re.error as exc:
        raise ValueError(f"source.read.file_regex is invalid: {exc}") from exc
    scope = str(read.get("file_regex_scope") or "relative_path").strip().lower()
    if scope not in {"filename", "relative_path"}:
        raise ValueError("source.read.file_regex_scope must be 'filename' or 'relative_path'")
    max_listed = _positive_int(read.get("file_regex_max_listed"), "source.read.file_regex_max_listed", 10000)
    recursive = _bool(read.get("file_regex_recursive"), _bool(options.get("recursiveFileLookup"), False))
    listed = _listed_files(spark, str(path), recursive=recursive, max_files=max_listed, declared=read.get("files"))
    root = str(path).rstrip("/")
    matched = []
    for file_path in listed:
        file_text = str(file_path)
        relative = file_text[len(root) :].lstrip("/") if file_text.startswith(root) else os.path.basename(file_text)
        candidate = os.path.basename(file_text) if scope == "filename" else relative
        if pattern.search(candidate):
            matched.append(file_text)
    if not matched:
        raise ValueError(
            "source.read.file_regex found no matching files. "
            f"pattern={pattern_text!r}, scope={scope}, listed_files={len(listed)}"
        )
    return matched


def _listed_files(
    spark: Any,
    path: str,
    *,
    recursive: bool,
    max_files: int,
    declared: object,
) -> list[str]:
    if isinstance(declared, (list, tuple)):
        files = [str(item) for item in declared]
        if len(files) > max_files:
            raise ValueError(f"source.read.file_regex exceeded source.read.file_regex_max_listed={max_files}")
        return files
    jvm = getattr(spark, "_jvm", None)
    jsc = getattr(spark, "_jsc", None)
    if jvm is None or jsc is None:
        raise RuntimeError(
            "source.read.file_regex requires Hadoop FileSystem access through classic PySpark. "
            "In Spark Connect/serverless, use pathGlobFilter, a filtered External Location/Volume path, "
            "or provide an explicit source.read.files list."
        )
    return _hadoop_list_files(jvm, jsc, path, recursive=recursive, max_files=max_files)


def _hadoop_list_files(jvm: Any, jsc: Any, path: str, *, recursive: bool, max_files: int) -> list[str]:
    root = jvm.org.apache.hadoop.fs.Path(path)
    fs = root.getFileSystem(jsc.hadoopConfiguration())
    files: list[str] = []

    def visit(current_path: Any) -> None:
        status = fs.getFileStatus(current_path)
        if status.isFile():
            _append(files, str(status.getPath().toString()), max_files)
            return
        for child in fs.listStatus(current_path):
            if child.isDirectory():
                if recursive:
                    visit(child.getPath())
                continue
            _append(files, str(child.getPath().toString()), max_files)

    visit(root)
    return files


def _append(files: list[str], path: str, max_files: int) -> None:
    files.append(path)
    if len(files) > max_files:
        raise ValueError(f"source.read.file_regex exceeded source.read.file_regex_max_listed={max_files}")


def _bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _positive_int(value: object, field: str, default: int) -> int:
    if value in (None, ""):
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed
