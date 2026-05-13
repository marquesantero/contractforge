"""Loader de contratos separados por responsabilidade."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from .governance import AccessContract, AnnotationsContract, OperationsContract
from .plan import IngestionPlan, build_plan_from_kwargs


@dataclass(frozen=True)
class ContractBundle:
    """Pacote logico de contratos de uma tabela."""

    ingestion: IngestionPlan
    annotations: Optional[AnnotationsContract] = None
    operations: Optional[OperationsContract] = None
    access: Optional[AccessContract] = None


def _load_structured(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise RuntimeError("Carga de YAML requer PyYAML instalado") from exc
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} deve conter um objeto")
    return payload


def _candidate_paths(base: Path, suffix: str) -> Iterable[Path]:
    if base.is_file():
        stem = base.name
        if ".ingestion." in stem:
            yield base.with_name(stem.replace(".ingestion.", f".{suffix}.", 1))
        return
    yield base.with_suffix(f".{suffix}.yaml")
    yield base.with_suffix(f".{suffix}.yml")
    yield base.with_suffix(f".{suffix}.json")


def _first_existing(base: Path, suffix: str) -> Optional[Path]:
    for candidate in _candidate_paths(base, suffix):
        if candidate.exists():
            return candidate
    return None


def load_contract_bundle(path: str | Path) -> ContractBundle:
    """Carrega ``*.ingestion.yaml`` e arquivos irmaos opcionais.

    Exemplo para ``contracts/gold/gd_orders_daily``:

    - ``gd_orders_daily.ingestion.yaml`` ou ``gd_orders_daily.yaml``
    - ``gd_orders_daily.annotations.yaml``
    - ``gd_orders_daily.operations.yaml``
    - ``gd_orders_daily.access.yaml``
    """
    base = Path(path)
    ingestion_path = base if base.is_file() else _first_existing(base, "ingestion")
    if ingestion_path is None:
        default_path = base.with_suffix(".yaml")
        ingestion_path = default_path if default_path.exists() else None
    if ingestion_path is None:
        raise FileNotFoundError(f"Contrato de ingestao nao encontrado para {base}")

    ingestion_payload = _load_structured(ingestion_path)
    annotations_path = _first_existing(ingestion_path, "annotations")
    operations_path = _first_existing(ingestion_path, "operations")
    access_path = _first_existing(ingestion_path, "access")

    if annotations_path:
        ingestion_payload["annotations"] = _load_structured(annotations_path)
    if operations_path:
        ingestion_payload["operations"] = _load_structured(operations_path)
    if access_path:
        ingestion_payload["access"] = _load_structured(access_path)

    plan = build_plan_from_kwargs(**ingestion_payload)
    return ContractBundle(
        ingestion=plan,
        annotations=plan.annotations,
        operations=plan.operations,
        access=plan.access,
    )
