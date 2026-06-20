"""ContractForge naming policies and derived-name helpers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

NamingPolicy = Literal["caf_default", "custom"]

_NON_WORD_RE = re.compile(r"[^a-z0-9]+")
_TRIM_SEPARATOR_RE = re.compile(r"(^[-_]+|[-_]+$)")


@dataclass(frozen=True)
class NamingConfig:
    policy: NamingPolicy = "caf_default"
    display_name: str | None = None
    logical_name: str | None = None
    slug: str | None = None
    contract_basename: str | None = None
    bundle_name: str | None = None
    job_name: str | None = None
    task_key: str | None = None
    artifact_prefix: str | None = None
    preserve_target_identifiers: bool = True


@dataclass(frozen=True)
class DerivedNames:
    display_name: str
    logical_name: str
    slug: str
    contract_basename: str
    bundle_name: str
    job_name: str
    task_key: str

    def as_dict(self) -> dict[str, str]:
        return {
            "display_name": self.display_name,
            "logical_name": self.logical_name,
            "slug": self.slug,
            "contract_basename": self.contract_basename,
            "bundle_name": self.bundle_name,
            "job_name": self.job_name,
            "task_key": self.task_key,
        }


def normalize_slug(value: Any, *, separator: str = "-") -> str:
    sep = "-" if separator not in {"-", "_"} else separator
    text = _ascii(value).lower()
    text = _NON_WORD_RE.sub(sep, text)
    text = _TRIM_SEPARATOR_RE.sub("", text)
    return text or "contractforge"


def normalize_identifier(value: Any) -> str:
    identifier = normalize_slug(value, separator="_")
    if identifier[0].isdigit():
        return f"n_{identifier}"
    return identifier


def derive_names(
    *,
    target_table: str | None = None,
    layer: str | None = None,
    domain: str | None = None,
    data_product: str | None = None,
    config: NamingConfig | None = None,
) -> DerivedNames:
    cfg = config or NamingConfig()
    base = _first_non_empty(cfg.logical_name or data_product, target_table, cfg.display_name, "contractforge")
    logical_name = normalize_identifier(cfg.logical_name or data_product or base)
    display_name = cfg.display_name.strip() if cfg.display_name else _display_name(logical_name)
    slug = normalize_slug(cfg.slug or logical_name)
    contract_basename = normalize_identifier(cfg.contract_basename or target_table or logical_name)

    prefix = normalize_slug(cfg.artifact_prefix, separator="_") if cfg.artifact_prefix else "cf"
    normalized_layer = normalize_identifier(layer) if layer else ""
    normalized_domain = normalize_identifier(domain) if domain else ""

    caf_parts = [prefix]
    caf_parts.extend(part for part in (normalized_domain, normalized_layer, normalize_identifier(slug)) if part)
    caf_identifier = "_".join(caf_parts)
    caf_slug = "-".join(part.replace("_", "-") for part in caf_parts)

    return DerivedNames(
        display_name=display_name,
        logical_name=logical_name,
        slug=slug,
        contract_basename=contract_basename,
        bundle_name=normalize_slug(cfg.bundle_name or caf_slug),
        job_name=cfg.job_name.strip() if cfg.job_name else caf_identifier,
        task_key=normalize_identifier(cfg.task_key or caf_identifier),
    )


def naming_config_from_mapping(value: dict[str, Any] | None) -> NamingConfig:
    if value is None:
        return NamingConfig()
    return NamingConfig(
        policy=value.get("policy", "caf_default"),
        display_name=_optional_text(value.get("display_name")),
        logical_name=_optional_text(value.get("logical_name")),
        slug=_optional_text(value.get("slug")),
        contract_basename=_optional_text(value.get("contract_basename")),
        bundle_name=_optional_text(value.get("bundle_name")),
        job_name=_optional_text(value.get("job_name")),
        task_key=_optional_text(value.get("task_key")),
        artifact_prefix=_optional_text(value.get("artifact_prefix")),
        preserve_target_identifiers=bool(value.get("preserve_target_identifiers", True)),
    )


def _ascii(value: Any) -> str:
    text = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _display_name(value: str) -> str:
    words = normalize_slug(value).replace("-", " ").strip()
    return words.title() if words else "ContractForge"


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return "contractforge"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
