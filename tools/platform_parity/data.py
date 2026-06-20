"""Small deterministic datasets for platform parity smoke runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.platform_parity.contracts import platform_parity_scenarios, scenario_by_name


def records_for_scenario(name: str) -> tuple[dict[str, Any], ...]:
    records = _RECORDS.get(name)
    if records is None:
        valid = ", ".join(sorted(_RECORDS))
        raise ValueError(f"No parity data registered for {name!r}. Valid scenarios: {valid}")
    return records


def write_jsonl_dataset(root: Path, *, names: tuple[str, ...] = ()) -> dict[str, str]:
    scenarios = tuple(scenario_by_name(name) for name in names) if names else platform_parity_scenarios()
    written: dict[str, str] = {}
    for scenario in scenarios:
        path = root / _dataset_name(scenario) / "part-00000.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(record, sort_keys=True) for record in records_for_scenario(scenario.name)]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written[scenario.name] = str(path)
    return written


def _dataset_name(scenario: Any) -> str:
    source = scenario.contract_for("databricks").get("source") or {}
    path = str(source.get("path") or "").rstrip("/")
    if path:
        return path.rsplit("/", 1)[-1]
    return str(scenario.name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contractforge-platform-parity-data")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("scenario", nargs="*")
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)
    written = write_jsonl_dataset(args.output, names=tuple(args.scenario))
    print(json.dumps({"kind": "contractforge_platform_parity_data", "written": written}, indent=args.indent, sort_keys=True))
    return 0


_RECORDS: dict[str, tuple[dict[str, Any], ...]] = {
    "orders_append_quality": (
        {"order_id": "o-001", "status": " paid ", "amount": "125.50"},
        {"order_id": "o-002", "status": "new", "amount": "20.00"},
        {"order_id": "", "status": "paid", "amount": "9.99"},
        {"order_id": "o-004", "status": "unknown", "amount": "1.00"},
    ),
    "orders_overwrite_shape": (
        {
            "order_id": "o-001",
            "payload": json.dumps(
                {
                    "channel": "web",
                    "items": [{"sku": "sku-1", "quantity": 2}, {"sku": "sku-2", "quantity": 1}],
                },
                sort_keys=True,
            ),
        },
        {
            "order_id": "o-002",
            "payload": json.dumps(
                {
                    "channel": "store",
                    "items": [{"sku": "sku-3", "quantity": -1}],
                },
                sort_keys=True,
            ),
        },
    ),
    "customers_upsert": (
        {"customer_id": "c-001", "email": " A@example.COM ", "updated_at": "2026-05-30T10:00:00Z"},
        {"customer_id": "c-001", "email": "a.latest@example.com", "updated_at": "2026-05-31T10:00:00Z"},
        {"customer_id": "c-002", "email": "b@example.com", "updated_at": "2026-05-31T09:00:00Z"},
    ),
    "customers_hash_diff": (
        {"customer_id": "c-001", "lifetime_value": "1200.50", "updated_at": "2026-05-31T10:00:00Z"},
        {"customer_id": "c-002", "lifetime_value": "25.00", "updated_at": "2026-05-31T10:05:00Z"},
    ),
    "customers_historical": (
        {"customer_id": "c-001", "email": "a@example.com", "status": "ACTIVE", "updated_at": "2026-05-31T10:00:00Z"},
        {"customer_id": "c-001", "email": "a.new@example.com", "status": "ACTIVE", "updated_at": "2026-06-01T10:00:00Z"},
        {"customer_id": "c-002", "email": "b@example.com", "status": "DELETE", "updated_at": "2026-06-01T11:00:00Z"},
    ),
    "customers_snapshot_soft_delete": (
        {"customer_id": "c-001", "email": "a@example.com", "status": "ACTIVE", "updated_at": "2026-06-01T10:00:00Z"},
        {"customer_id": "c-003", "email": "c@example.com", "status": "ACTIVE", "updated_at": "2026-06-01T10:05:00Z"},
    ),
    "governance_review_boundary": (
        {"customer_id": "c-001", "email": "a@example.com", "country": "BR"},
        {"customer_id": "c-002", "email": "b@example.com", "country": "US"},
    ),
}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
