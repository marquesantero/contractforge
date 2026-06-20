"""Free-form intent normalization for agentic project generation."""

from __future__ import annotations

import re

from contractforge_ai.agentic.models import IntentSpec, Layer
from contractforge_ai.models import EvidenceItem, RequiredDecision
from contractforge_ai.planning.platforms import detect_platform_hints
from contractforge_ai.planning.project import detect_prompt_dab_compute, detect_prompt_operations, detect_prompt_quality_rules
from contractforge_ai.write_modes import canonical_write_mode


def interpret_intent(
    prompt: str,
    *,
    sample_table: str | None = None,
    default_catalog: str | None = None,
    output_target: str = "contractforge-yaml",
) -> IntentSpec:
    """Normalize a user prompt into an IntentSpec."""

    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ValueError("Generation prompt cannot be empty.")

    table_refs = _table_references(normalized_prompt)
    source = sample_table or _source(normalized_prompt, table_refs)
    target_table = _target_table(normalized_prompt, table_refs)
    catalog = _catalog(default_catalog, sample_table, target_table, source)
    base_name = _base_name(normalized_prompt, sample_table, target_table, source)
    layers = _requested_layers(normalized_prompt)
    final_columns = _final_columns(normalized_prompt)
    hash_columns = _hash_columns(normalized_prompt)
    quality_rules = detect_prompt_quality_rules(normalized_prompt)
    operations = detect_prompt_operations(normalized_prompt)
    dab_compute = detect_prompt_dab_compute(normalized_prompt)
    schedule = _detect_schedule(normalized_prompt)
    platform_hints = _platform_hints(normalized_prompt, output_target)
    decisions = _intent_decisions(normalized_prompt, layers)

    return IntentSpec(
        prompt=normalized_prompt,
        requested_layers=layers,
        source=source,
        target_table=target_table,
        base_name=base_name,
        catalog=catalog,
        final_columns=final_columns,
        hash_columns=hash_columns,
        quality_rules=quality_rules,
        operations=operations,
        dab_compute=dab_compute,
        schedule=schedule,
        platform_hints=platform_hints,
        silver_mode=_silver_mode(normalized_prompt),
        output_target=output_target,
        completion_goal=_completion_goal(normalized_prompt),
        decisions_required=decisions,
        evidence=[
            EvidenceItem(
                source="user_prompt",
                reason="Normalized free-form generation request into a typed intent specification.",
                value={
                    "requested_layers": layers,
                    "source": source,
                    "target_table": target_table,
                    "final_columns": final_columns,
                    "platform_hints": platform_hints,
                },
                confidence=0.70,
            )
        ],
        confidence=0.70 if not decisions else 0.62,
    )


def _requested_layers(prompt: str) -> list[Layer]:
    text = prompt.lower()
    if _contains_any(text, "only gold", "gold only", "só gold", "apenas gold"):
        return ["gold"]
    if _contains_any(text, "only silver", "silver only", "só silver", "apenas silver"):
        return ["silver"]
    if _contains_any(text, "only bronze", "bronze only", "só bronze", "apenas bronze"):
        return ["bronze"]
    if _contains_any(text, "bronze to gold", "bronze até gold", "bronze para gold", "até gold", "to gold", "medallion"):
        return ["bronze", "silver", "gold"]
    if _contains_any(text, "bronze to silver", "bronze até silver", "bronze para silver", "até silver", "to silver"):
        return ["bronze", "silver"]
    if "gold" in text:
        return ["gold"]
    if "silver" in text:
        return ["silver"]
    return ["bronze"]


def _completion_goal(prompt: str) -> str:
    text = prompt.lower()
    if _contains_any(text, "complete what is missing", "complete missing", "complete o que falta", "o que falta"):
        return "complete_missing"
    if _contains_any(text, "patch", "update existing", "atualize", "corrija"):
        return "patch_existing"
    return "generate_requested_layers"


def _intent_decisions(prompt: str, layers: list[Layer]) -> list[RequiredDecision]:
    decisions: list[RequiredDecision] = []
    text = prompt.lower()
    silver_mode = canonical_write_mode(_silver_mode(prompt))
    if "silver" in layers and silver_mode in {"scd1_hash_diff", "scd1_upsert", "scd2_historical"} and not _contains_any(text, "key", "keys", "merge key", "chave"):
        decisions.append(
            RequiredDecision(
                question="Confirm merge keys and hash-diff column policy for the silver layer.",
                reason="Historical and upsert modes require stable business keys; ContractForge AI should not invent them from naming alone.",
                path="contracts/silver/*.ingestion.yaml.merge_keys",
            )
        )
    if "silver" in layers and silver_mode == "scd1_hash_diff" and not _contains_any(text, "hash column", "hash columns", "hash key", "hash keys", "hash diff columns", "colunas de hash"):
        decisions.append(
            RequiredDecision(
                question="Confirm hash-diff columns or choose hash_strategy=all_columns_except.",
                reason="Hash-diff semantics require explicit column inclusion/exclusion policy; ContractForge AI should not invent it.",
                path="contracts/silver/*.ingestion.yaml.hash_keys",
            )
        )
    if "gold" in layers and _contains_any(text, "aggregate", "aggregation", "agregar", "sum", "count") and not _contains_any(text, "grain", "granularity", "grão", "granularidade"):
        decisions.append(
            RequiredDecision(
                question="Confirm gold table grain before generating aggregation logic.",
                reason="Gold aggregation semantics are business decisions and cannot be inferred safely from a target table name.",
                path="contracts/gold/*.ingestion.yaml.transform",
            )
        )
    return decisions


def _source(prompt: str, table_refs: list[str]) -> str | None:
    source_patterns = [
        r"(?:from|source|use table|using table|origem|fonte)\s+([A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*)",
        r"\b(s3a?://[^\s,;]+|abfss?://[^\s,;]+|https?://[^\s,;]+|/Volumes/[^\s,;]+|dbfs:/[^\s,;]+)",
    ]
    for pattern in source_patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return match.group(1).rstrip(".")
    return table_refs[0] if table_refs else None


def _platform_hints(prompt: str, output_target: str) -> list[str]:
    hints = detect_platform_hints(prompt)
    target_hints = {
        "aws-glue-iceberg": "aws",
        "databricks-dab": "databricks",
    }
    target_hint = target_hints.get(output_target)
    if target_hint and target_hint not in hints:
        hints.append(target_hint)
    return hints


def _target_table(prompt: str, table_refs: list[str]) -> str | None:
    match = re.search(r"(?:target|to|into|destino|tabela final)\s+([A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*)", prompt, re.IGNORECASE)
    if match:
        return match.group(1)
    return table_refs[-1] if len(table_refs) > 1 else None


def _table_references(prompt: str) -> list[str]:
    return re.findall(r"\b[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\.[A-Za-z_][\w-]*\b", prompt)


def _catalog(default_catalog: str | None, sample_table: str | None, target_table: str | None, source: str | None) -> str:
    for table in (target_table, sample_table, source):
        if table and table.count(".") == 2:
            return table.split(".")[0]
    return default_catalog or "main"


def _base_name(prompt: str, sample_table: str | None, target_table: str | None, source: str | None) -> str:
    explicit = re.search(r"(?:project|pipeline|flow)\s+(?:named|called)\s+['\"]?([A-Za-z][\w -]{2,80})", prompt, re.IGNORECASE)
    if explicit:
        return _safe_name(_trim_clause(explicit.group(1)))
    for candidate in (target_table, sample_table, source):
        if candidate and candidate.count(".") == 2:
            return _safe_name(candidate.split(".")[-1].removeprefix("b_").removeprefix("s_").removeprefix("g_").removesuffix("_sample"))
    return "generated_project"


def _trim_clause(value: str) -> str:
    return re.split(r"\b(?:from|source|target|to|into|using|with)\b", value, maxsplit=1, flags=re.IGNORECASE)[0]


def _silver_mode(prompt: str) -> str:
    text = prompt.lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    for mode in (
        "historical",
        "scd2_historical",
        "hash_diff_upsert",
        "scd1_hash_diff",
        "upsert",
        "scd1_upsert",
        "snapshot_reconcile_soft_delete",
        "snapshot_soft_delete",
    ):
        if mode in normalized:
            return {
                "scd2_historical": "historical",
                "scd1_hash_diff": "hash_diff_upsert",
                "scd1_upsert": "upsert",
                "snapshot_soft_delete": "snapshot_reconcile_soft_delete",
            }.get(mode, mode)
    if "hash diff" in text:
        return "hash_diff_upsert"
    if "upsert" in text or "merge" in text:
        return "upsert"
    return "hash_diff_upsert"


def _final_columns(prompt: str) -> list[str]:
    patterns = [
        r"(?:gold final columns|final columns|output columns|selected columns|colunas finais)\s*[:=]\s*([A-Za-z0-9_,\s.-]+)",
        r"(?:gold.*(?:with|containing|contendo|com))\s+([A-Za-z0-9_,\s.-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            raw = re.split(r"\b(?:using|with|from|into|for|and|e)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            return [_safe_name(item) for item in re.split(r"[,;\s]+", raw) if item.strip()]
    return []


def _hash_columns(prompt: str) -> list[str]:
    patterns = [
        r"(?:hash columns|hash keys|hash diff columns|colunas de hash)\s*[:=]\s*([A-Za-z0-9_,\s.-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            raw = re.split(r"\b(?:required columns|final columns|gold final columns|must be|should be|with|from|into|using|severity|daily|schedule)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            return [_safe_name(item) for item in re.split(r"[,;\s]+", raw.split(".", 1)[0]) if item.strip()]
    return []


def _detect_schedule(prompt: str) -> dict[str, object]:
    schedule: dict[str, object] = {}
    cron = _detect_cron(prompt)
    timezone = _detect_timezone(prompt)
    lowered = prompt.lower()
    if cron:
        schedule["cron"] = cron
    elif "daily" in lowered or "diário" in lowered or "diaria" in lowered:
        hour = _detect_hour(prompt)
        schedule["cron"] = f"0 {hour if hour is not None else 6} * * *"
    elif "hourly" in lowered or "cada hora" in lowered:
        schedule["cron"] = "0 * * * *"
    if timezone:
        schedule["timezone"] = timezone
    return schedule


def _detect_cron(prompt: str) -> str | None:
    patterns = [
        r"(?:cron|schedule)\s*[:=]\s*['\"]?([0-9*/,-]+\s+[0-9*/,-]+\s+[0-9*/,-]+\s+[0-9*/,-]+\s+[0-9*/,-]+)",
        r"['\"]([0-9*/,-]+\s+[0-9*/,-]+\s+[0-9*/,-]+\s+[0-9*/,-]+\s+[0-9*/,-]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _detect_hour(prompt: str) -> int | None:
    match = re.search(r"(?:at|às|as)\s+(\d{1,2})(?::\d{2})?\s*(?:h|hours?|am|pm)?", prompt, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(\d{1,2})(?::00)?\s*(?:h|hours?)\b", prompt, re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    suffix_match = re.search(rf"{re.escape(match.group(0))}\s*(am|pm)", prompt, re.IGNORECASE)
    if suffix_match and suffix_match.group(1).lower() == "pm" and hour < 12:
        hour += 12
    if 0 <= hour <= 23:
        return hour
    return None


def _detect_timezone(prompt: str) -> str | None:
    lowered = prompt.lower()
    aliases = {
        "sao paulo": "America/Sao_Paulo",
        "são paulo": "America/Sao_Paulo",
        "brazil": "America/Sao_Paulo",
        "brasil": "America/Sao_Paulo",
        "utc": "UTC",
        "new york": "America/New_York",
        "london": "Europe/London",
    }
    for alias, timezone in aliases.items():
        if alias in lowered:
            return timezone
    for iana in re.finditer(r"\b([A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?)\b", prompt):
        prefix = prompt[max(0, iana.start() - 4) : iana.start()]
        if "://" not in prefix:
            return iana.group(1)
    return None


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().lower()).strip("_")
    return cleaned or "generated_project"


def _contains_any(value: str, *needles: str) -> bool:
    return any(needle in value for needle in needles)
