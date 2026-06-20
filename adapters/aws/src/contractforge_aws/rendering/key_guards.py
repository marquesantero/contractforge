"""Render runtime key-integrity guards for merge-based writes."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract


def render_pre_quality_merge_key_guard(contract: SemanticContract) -> list[str]:
    if contract.write.mode not in {"scd1_upsert", "scd1_hash_diff"}:
        return []
    merge_keys = tuple(contract.write.merge_keys)
    if not merge_keys:
        raise ValueError(f"AWS Glue Iceberg {contract.write.mode} rendering requires merge_keys")
    return [
        "# Validate merge-key integrity before quality quarantine can remove offending rows.",
        f"merge_keys = {list(merge_keys)!r}",
        "",
        "def _cf_quote_identifier(value):",
        "    return '`' + str(value).replace('`', '``') + '`'",
        "",
        "",
        "missing_merge_keys = [key for key in merge_keys if key not in df.columns]",
        "if missing_merge_keys:",
        "    raise ValueError(f'Missing merge_keys in source DataFrame: {missing_merge_keys}')",
        "",
        "null_merge_key_predicate = ' OR '.join(f'{_cf_quote_identifier(key)} IS NULL' for key in merge_keys)",
        "if null_merge_key_predicate and df.filter(null_merge_key_predicate).limit(1).count() > 0:",
        f"    raise ValueError(f'{contract.write.mode} source contains null merge_keys: {{merge_keys}}')",
        "",
        "_cf_duplicate_merge_keys = (",
        "    df.groupBy(*merge_keys)",
        "    .count()",
        "    .filter('`count` > 1')",
        "    .limit(1)",
        "    .count()",
        ")",
        "if _cf_duplicate_merge_keys:",
        f"    raise ValueError(f'{contract.write.mode} source contains duplicate merge_keys: {{merge_keys}}')",
    ]
