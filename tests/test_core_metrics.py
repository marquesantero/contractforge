from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_core.metrics import logical_row_metrics, normalize_rows_written


def _contract(mode: str):
    payload = {
        "source": {"type": "connector", "connector": "postgres"},
        "target": {"catalog": "main", "schema": "silver", "table": "orders"},
        "mode": mode,
    }
    if mode in {"scd1_upsert", "scd2_historical"}:
        payload["merge_keys"] = ["id"]
    return semantic_contract_from_mapping(payload)


def test_core_logical_row_metrics_for_append_like_modes() -> None:
    metrics = logical_row_metrics(_contract("scd1_hash_diff"), 7)

    assert metrics["rows_inserted"] == 7
    assert metrics["rows_affected"] == 7


def test_core_logical_row_metrics_for_update_mode_are_affected_only() -> None:
    metrics = logical_row_metrics(_contract("scd1_upsert"), 7)

    assert metrics["rows_inserted"] == 0
    assert metrics["rows_affected"] == 7


def test_core_normalize_rows_written_uses_rows_affected() -> None:
    assert normalize_rows_written(0, {"rows_affected": 250000}) == 250000
