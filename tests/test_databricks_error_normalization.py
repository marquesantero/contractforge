from __future__ import annotations

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks.annotations import apply_annotations_contract
from contractforge_databricks.security import exception_message, short_error_message


class SecretFailingRunner:
    def sql(self, statement: str) -> None:
        raise RuntimeError(
            "py4j.protocol.Py4JJavaError: failed\n"
            "Authorization=Bearer raw-token\n"
            "Caused by: org.postgresql.util.PSQLException: password=innersecret"
        )


def test_short_error_message_prefers_caused_by_and_redacts_secrets() -> None:
    message = short_error_message(
        "org.apache.spark.SparkException: Job aborted\n"
        "jdbc:postgresql://user:s3cr3t@host/db?password=topsecret\n"
        "Caused by: org.postgresql.util.PSQLException: password=innersecret"
    )

    assert message.startswith("Caused by:")
    assert "topsecret" not in message
    assert "innersecret" not in message
    assert "***REDACTED***" in message


def test_exception_message_uses_last_relevant_line() -> None:
    message = exception_message(
        RuntimeError(
            "Traceback (most recent call last):\n"
            "  File \"job.py\", line 1, in <module>\n"
            "ValueError: invalid contract"
        )
    )

    assert message == "ValueError: invalid contract"


def test_annotation_runtime_errors_are_normalized() -> None:
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "table", "table": "main.raw.orders"},
            "target": {"catalog": "main", "schema": "silver", "table": "orders"},
            "annotations": {"table": {"description": "Orders"}},
        }
    )

    result = apply_annotations_contract(runner=SecretFailingRunner(), contract=contract)

    assert result.status == "WARNED"
    assert len(result.errors) == 1
    assert "raw-token" not in result.errors[0]
    assert "innersecret" not in result.errors[0]
    assert "***REDACTED***" in result.errors[0]
