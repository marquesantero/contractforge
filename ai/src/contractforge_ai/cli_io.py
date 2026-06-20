"""File-loading helpers for the ContractForge AI CLI."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def load_json_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def load_text_file(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def load_json_file(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Profile config must be a JSON object.")
    return data


def validation_report_from_file(path: str):
    from contractforge_ai.validation.loop import DeterministicValidationCheck, DeterministicValidationReport

    payload = load_json_file(path)
    checks = [
        DeterministicValidationCheck(
            kind=item.get("kind") or "artifact",
            name=str(item.get("name") or "unknown"),
            status=item.get("status") or "INVALID",
            summary=str(item.get("summary") or ""),
        )
        for item in payload.get("checks", [])
        if isinstance(item, dict)
    ]
    return DeterministicValidationReport(
        status=payload.get("status") or "INVALID",
        summary=str(payload.get("summary") or ""),
        checks=checks,
        decisions_required=[str(item) for item in payload.get("decisions_required", [])],
    )


def context_results_from_file(path: str) -> list[dict]:
    payload = load_json_file(path)
    if isinstance(payload.get("context_results"), list):
        return payload["context_results"]
    if isinstance(payload.get("results"), list):
        return payload["results"]
    return []


def load_mapping_file(path: str, *, purpose: str) -> dict:
    source = Path(path)
    raw = source.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if source.suffix.lower() in {".yaml", ".yml"} else json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{purpose} must be a JSON/YAML object.")
    return data
