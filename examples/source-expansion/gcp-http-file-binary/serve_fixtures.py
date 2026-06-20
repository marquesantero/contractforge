from __future__ import annotations

import argparse
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pyarrow as pa
import pyarrow.orc as orc
import pyarrow.parquet as pq
from fastavro import writer


ROOT = Path(__file__).resolve().parent
GENERATED = ROOT / ".generated"


def _orders_table() -> pa.Table:
    return pa.table(
        {
            "order_id": pa.array(["A-001", "A-002", "A-003"], type=pa.string()),
            "amount": pa.array([10.0, 20.5, 30.25], type=pa.float64()),
            "status": pa.array(["paid", "pending", "paid"], type=pa.string()),
        }
    )


def _write_fixtures() -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    table = _orders_table()
    pq.write_table(table, GENERATED / "orders.parquet")
    orc.write_table(table, GENERATED / "orders.orc")
    schema = {
        "type": "record",
        "name": "Order",
        "fields": [
            {"name": "order_id", "type": "string"},
            {"name": "amount", "type": "double"},
            {"name": "status", "type": "string"},
        ],
    }
    records = [
        {"order_id": "A-001", "amount": 10.0, "status": "paid"},
        {"order_id": "A-002", "amount": 20.5, "status": "pending"},
        {"order_id": "A-003", "amount": 30.25, "status": "paid"},
    ]
    with (GENERATED / "orders.avro").open("wb") as handle:
        writer(handle, schema, records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    _write_fixtures()
    os.chdir(GENERATED)
    handler = partial(SimpleHTTPRequestHandler, directory=str(GENERATED))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"serving {GENERATED} at http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

