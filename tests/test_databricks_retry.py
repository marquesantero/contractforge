import pytest

from contractforge_databricks.execution import is_retryable_delta_concurrency_error, with_delta_retry


def test_retryable_delta_concurrency_error_detection() -> None:
    assert is_retryable_delta_concurrency_error(RuntimeError("DELTA_CONCURRENT_APPEND conflict"))
    assert not is_retryable_delta_concurrency_error(ValueError("invalid contract"))


def test_with_delta_retry_retries_concurrency_errors() -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("concurrent write conflict")
        return "ok"

    result = with_delta_retry(flaky, attempts=2, backoff_seconds=2, jitter=lambda: 0.5, sleep=sleeps.append)

    assert result == "ok"
    assert calls["count"] == 2
    assert sleeps == [2.5]


def test_with_delta_retry_does_not_retry_non_concurrency_errors() -> None:
    calls = {"count": 0}

    def invalid() -> None:
        calls["count"] += 1
        raise ValueError("invalid contract")

    with pytest.raises(ValueError):
        with_delta_retry(invalid, attempts=3, sleep=lambda _: None)

    assert calls["count"] == 1
