from __future__ import annotations

import urllib.error

import pytest

from contractforge_databricks.runtime.http_file import (
    cleanup_http_file_downloads,
    download_http_file,
    resolve_http_file_dataframe,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class FakeOpener:
    def __init__(self, open_fn) -> None:
        self._open_fn = open_fn

    def open(self, request, timeout):
        return self._open_fn(request, timeout)


def _patch_http_open(monkeypatch, open_fn) -> None:
    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: FakeOpener(open_fn))


def test_download_http_file_gets_payload_with_params_and_headers(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, dict(request.header_items()), timeout))
        return FakeResponse(b"id\n1\n")

    _patch_http_open(monkeypatch, fake_urlopen)

    path = download_http_file(
        {
            "type": "http_csv",
            "request": {
                "url": "https://example.com/orders.csv",
                "params": {"region": "br"},
                "headers": {"Accept": "text/csv"},
            },
            "limits": {"timeout_seconds": 10},
        }
    )

    assert path.endswith(".csv")
    assert calls[0][0] == "https://example.com/orders.csv?region=br"
    assert calls[0][1]["Accept"] == "text/csv"
    assert calls[0][2] == 10
    cleanup_http_file_downloads()


def test_cleanup_http_file_downloads_removes_downloaded_temp_files(monkeypatch) -> None:
    _patch_http_open(monkeypatch, lambda request, timeout: FakeResponse(b"id\n1\n"))
    path = download_http_file({"type": "http_csv", "url": "https://example.com/orders.csv"})

    cleanup_http_file_downloads()

    from pathlib import Path

    assert not Path(path).exists()


def test_download_http_file_enforces_max_bytes(monkeypatch) -> None:
    _patch_http_open(monkeypatch, lambda request, timeout: FakeResponse(b"too-large"))

    with pytest.raises(ValueError, match="max_bytes=3"):
        download_http_file({"type": "http_text", "url": "https://example.com/data.txt", "limits": {"max_bytes": 3}})


def test_download_http_file_retries_retryable_http_error(monkeypatch) -> None:
    attempts = []

    def fake_urlopen(request, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, "rate limited", hdrs=None, fp=None)
        return FakeResponse(b"ok\n")

    _patch_http_open(monkeypatch, fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    path = download_http_file(
        {
            "type": "http_text",
            "url": "https://example.com/data.txt",
            "limits": {"retry_attempts": 2, "retry_backoff_seconds": 0.1},
        }
    )

    assert path.endswith(".txt")
    assert len(attempts) == 2


def test_download_http_file_rejects_non_get() -> None:
    with pytest.raises(ValueError, match="only GET"):
        download_http_file({"type": "http_json", "request": {"url": "https://example.com/data", "method": "POST"}})


class FakeDataFrame:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class FakeReader:
    def __init__(self) -> None:
        self.options = {}
        self.loaded_path = None

    def format(self, value: str):
        return self

    def option(self, key: str, value: str):
        self.options[key] = value
        return self

    def load(self, path: str):
        self.loaded_path = path
        return FakeDataFrame(3)


class FakeSpark:
    def __init__(self) -> None:
        self.read = FakeReader()


def test_resolve_http_file_dataframe_enforces_max_records(monkeypatch) -> None:
    monkeypatch.setattr("contractforge_databricks.runtime.http_file.download_http_file", lambda source: "orders.json")

    with pytest.raises(ValueError, match="max_records=2"):
        resolve_http_file_dataframe(
            FakeSpark(),
            {"type": "http_json", "url": "https://example.com/data.json", "limits": {"max_records": 2}},
        )
