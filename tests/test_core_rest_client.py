"""Platform-neutral bounded REST client (core)."""

from __future__ import annotations

import io
import json

import pytest

from contractforge_core.connectors import read_rest_api_records, rest_request_headers
from contractforge_core.connectors.api.rest import pagination, safety
import contractforge_core.connectors.api.rest.reader as reader


class _FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, url: str, headers: dict | None = None):
        super().__init__(body)
        self._url = url
        self.headers = _FakeHeaders(headers or {})

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _FakeHeaders:
    def __init__(self, data: dict):
        self._data = data

    def get_content_charset(self):
        return "utf-8"

    def items(self):
        return self._data.items()

    def get(self, key, default=None):
        return self._data.get(key, default)


def _patch_http(monkeypatch, responses: list):
    calls = {"urls": []}

    def _fake_open_request(request, *, timeout=None):
        calls["urls"].append(request.full_url)
        body, headers = responses.pop(0)
        return _FakeResponse(body, request.full_url, headers)

    monkeypatch.setattr(reader, "_open_request", _fake_open_request)
    monkeypatch.setattr(reader, "validate_http_target", lambda *a, **k: None)
    return calls


def test_reads_records_from_path(monkeypatch):
    body = json.dumps({"data": [{"id": 1}, {"id": 2}]}).encode()
    _patch_http(monkeypatch, [(body, {})])
    records = read_rest_api_records(
        {"type": "rest_api", "request": {"url": "https://api.example.com/x"}, "response": {"records_path": "data"}}
    )
    assert records == [{"id": 1}, {"id": 2}]


def test_page_pagination_builds_urls(monkeypatch):
    page = json.dumps([{"id": 1}]).encode()
    calls = _patch_http(monkeypatch, [(page, {}), (page, {})])
    read_rest_api_records(
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/x"},
            "pagination": {"type": "page"},
            "limits": {"max_pages": 2},
        }
    )
    assert "page=1" in calls["urls"][0]
    assert "page=2" in calls["urls"][1]


def test_bearer_auth_header_built_from_resolved_value():
    headers = rest_request_headers({"auth": {"type": "bearer_token", "token": "abc"}})
    assert headers["Authorization"] == "Bearer abc"


def test_max_records_limit_enforced(monkeypatch):
    body = json.dumps([{"id": 1}, {"id": 2}, {"id": 3}]).encode()
    _patch_http(monkeypatch, [(body, {})])
    with pytest.raises(ValueError, match="max_records"):
        read_rest_api_records(
            {"type": "rest_api", "request": {"url": "https://api.example.com/x"}, "limits": {"max_records": 2}}
        )


def test_safety_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="scheme"):
        safety.validate_http_target("file:///etc/passwd")


def test_pagination_link_header_next():
    assert pagination.link_header_next('<https://api.example.com/x?page=2>; rel="next"') == "https://api.example.com/x?page=2"


def test_rest_reader_refuses_redirects():
    handler = reader._NoRedirect()
    with pytest.raises(ValueError, match="refused a redirect"):
        handler.redirect_request(None, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data")


def test_oauth_token_url_uses_http_safety():
    with pytest.raises(ValueError, match="OAuth token URL scheme"):
        rest_request_headers(
            {
                "auth": {
                    "type": "oauth_client_credentials",
                    "token_url": "file:///tmp/token",
                    "client_id": "client",
                    "client_secret": "secret",
                }
            }
        )
