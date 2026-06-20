from contractforge_core.execution import ExecutionOutcome
from contractforge_core.runtime import PreparedInput, QuarantineReference, QueryOne, rows_written_from_outcome


def test_core_prepared_input_defaults() -> None:
    prepared = PreparedInput(source_view="orders_view")

    assert prepared.source_view == "orders_view"
    assert prepared.source_columns == ()
    assert prepared.source_schema is None
    assert prepared.rows_read == 0
    assert prepared.source_metadata is None


def test_core_prepared_input_carries_source_metadata() -> None:
    prepared = PreparedInput(
        source_view="orders_view",
        source_columns=("id", "amount"),
        source_schema={"id": "BIGINT", "amount": "DOUBLE"},
        rows_read=10,
        rows_quarantined=1,
        source_name="postgres.public.orders",
        source_metadata={"source_type": "jdbc"},
    )

    assert prepared.source_columns == ("id", "amount")
    assert prepared.source_schema == {"id": "BIGINT", "amount": "DOUBLE"}
    assert prepared.rows_quarantined == 1
    assert prepared.source_metadata == {"source_type": "jdbc"}


def test_core_prepared_input_carries_quarantine_references() -> None:
    prepared = PreparedInput(
        source_view="orders_view",
        rows_read=10,
        rows_quarantined=1,
        quarantine_records=(QuarantineReference("s3://q/orders/run-1/part-000.json", "quality_gate", "not_null"),),
    )

    assert prepared.quarantine_records[0].record_ref == "s3://q/orders/run-1/part-000.json"
    assert prepared.quarantine_records[0].reason == "quality_gate"


def test_core_rows_written_from_outcome_prefers_metric() -> None:
    prepared = PreparedInput(source_view="orders", rows_read=10, rows_quarantined=2)
    outcome = ExecutionOutcome(status="SUCCESS", operation="append", target="orders", metrics={"rows_written": 5})

    assert rows_written_from_outcome(prepared, outcome) == 5


def test_core_rows_written_from_outcome_falls_back_to_prepared_counts() -> None:
    prepared = PreparedInput(source_view="orders", rows_read=10, rows_quarantined=2)

    assert rows_written_from_outcome(prepared, None) == 8


def test_core_query_one_protocol_accepts_callable() -> None:
    def query_one(statement: str):
        return {"statement": statement}

    typed: QueryOne = query_one

    assert typed("select 1") == {"statement": "select 1"}
