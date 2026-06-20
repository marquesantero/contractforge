import pytest

from contractforge_core.config import canonical_write_mode, public_write_mode
from contractforge_core.execution import canonical_custom_write_mode, write_strategy_label


@pytest.mark.parametrize(
    ("public_mode", "canonical_mode"),
    [
        ("append", "scd0_append"),
        ("overwrite", "scd0_overwrite"),
        ("upsert", "scd1_upsert"),
        ("merge_current", "scd1_upsert"),
        ("hash_diff_upsert", "scd1_hash_diff"),
        ("historical", "scd2_historical"),
        ("snapshot_reconcile_soft_delete", "snapshot_soft_delete"),
    ],
)
def test_core_write_mode_aliases_normalize_to_internal_modes(public_mode: str, canonical_mode: str) -> None:
    assert canonical_write_mode(public_mode) == canonical_mode
    assert public_write_mode(canonical_mode) == public_write_mode(public_mode)


def test_core_custom_write_mode_canonicalization() -> None:
    assert canonical_custom_write_mode("acme_writer") == "custom:acme_writer"
    assert canonical_custom_write_mode("custom:acme_writer") == "custom:acme_writer"

    with pytest.raises(ValueError, match="custom write mode"):
        canonical_custom_write_mode("")


def test_core_write_strategy_labels_match_contractforge_semantics() -> None:
    assert write_strategy_label("scd0_append") == "APPEND"
    assert write_strategy_label("append") == "APPEND"
    assert write_strategy_label("scd1_hash_diff") == "HASH_DIFF_APPEND"
    assert write_strategy_label("hash_diff_upsert") == "HASH_DIFF_APPEND"
    assert write_strategy_label("scd2_historical") == "SCD2_MERGE"
    assert write_strategy_label("historical") == "SCD2_MERGE"
    assert write_strategy_label("custom:acme_writer") == "CUSTOM:custom:acme_writer"
