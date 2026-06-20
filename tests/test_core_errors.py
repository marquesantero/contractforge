import pytest

from contractforge_core.errors import (
    ContractForgeExecutionError,
    exception_message,
    raise_for_failure_result,
    short_error_message,
)


def test_core_short_error_message_prefers_relevant_redacted_line() -> None:
    message = short_error_message(
        "\n".join(
            [
                "outer wrapper",
                "Caused by: SQLException: password=raw-secret",
                "last generic line",
            ]
        )
    )

    assert message.startswith("Caused by: SQLException:")
    assert "raw-secret" not in message
    assert "***REDACTED***" in message


def test_core_exception_message_uses_exception_text() -> None:
    assert exception_message(RuntimeError("token=abc")) == "token=***REDACTED***"


def test_core_short_error_message_handles_empty_text() -> None:
    assert short_error_message("") == ""


def test_raise_for_failure_result_raises_public_execution_error() -> None:
    with pytest.raises(ContractForgeExecutionError) as exc_info:
        raise_for_failure_result(
            {
                "status": "failed",
                "target_table": "main.silver.orders",
                "run_id": "run-1",
                "error_message": "RuntimeError: password=raw-secret",
            }
        )

    assert exc_info.value.status == "failed"
    assert exc_info.value.run_id == "run-1"
    assert exc_info.value.target == "main.silver.orders"
    assert "raw-secret" not in str(exc_info.value)
    assert "***REDACTED***" in str(exc_info.value)


def test_raise_for_failure_result_allows_non_failure_status() -> None:
    assert raise_for_failure_result({"status": "SUCCESS"}) is None
