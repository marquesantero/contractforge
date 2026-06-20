"""Lightweight access to ContractForge Core naming helpers."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from types import ModuleType
from typing import Any


def derive_names(**kwargs: Any) -> Any:
    """Delegate to ContractForge naming derivation."""

    return _naming_module().derive_names(**kwargs)


def normalize_identifier(value: Any) -> str:
    """Delegate to ContractForge identifier normalization."""

    return _naming_module().normalize_identifier(value)


def normalize_naming_config(value: Any) -> Any:
    """Delegate to ContractForge naming configuration normalization."""

    module = _naming_module()
    if hasattr(module, "normalize_naming_config"):
        return module.normalize_naming_config(value)
    return module.naming_config_from_mapping(value)


@lru_cache(maxsize=1)
def _naming_module() -> ModuleType:
    return import_module("contractforge_core.naming")
