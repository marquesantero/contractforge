from __future__ import annotations

from contractforge_databricks.runtime.errors import error_log_payload


def test_error_log_payload_redacts_stack_trace() -> None:
    exc = RuntimeError("jdbc:postgresql://user:pass@host/db password=raw-token")

    payload = error_log_payload(
        exc,
        run_id="run-1",
        target="catalog.schema.table",
        source_table="public.orders",
        mode="append",
    )

    assert "***REDACTED***" in payload["error_message"]
    assert "***REDACTED***" in payload["stack_trace"]
    assert "raw-token" not in payload["stack_trace"]
    assert "raw-token" not in payload["error_message"]
    assert "pass@host" not in payload["stack_trace"]
    assert "pass@host" not in payload["error_message"]
