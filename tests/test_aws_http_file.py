"""AWS bounded HTTP file source rendering."""

from __future__ import annotations

import pytest

from contractforge_aws import render_aws_contract
from contractforge_aws.sources import can_render_source


def _contract(source: dict) -> dict:
    return {
        "source": source,
        "target": {"catalog": "lake", "schema": "bronze", "table": "feed"},
        "mode": "scd0_append",
    }


def _job(source: dict) -> str:
    job = render_aws_contract(_contract(source)).artifacts["lake_bronze_feed.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_http_json_with_bearer_secret_resolves_at_runtime() -> None:
    job = _job(
        {
            "type": "http_json",
            "request": {"url": "https://api.example.com/orders"},
            "auth": {"type": "bearer_token", "token": "{{ secret:api/token }}"},
        }
    )
    assert "def _cf_http_dataframe(" in job
    assert "from contractforge_core.connectors import read_http_file_payload" in job
    assert "_cf_http_dataframe(" in job
    assert "url='https://api.example.com/orders'" in job
    assert "fmt='json'" in job
    assert "'Authorization': 'Bearer ' + _cf_resolve_secret('api', 'token')" in job
    assert "{{ secret:api/token }}" not in job


def test_http_csv_with_api_key_and_params() -> None:
    job = _job(
        {
            "type": "http_csv",
            "request": {"url": "https://api.example.com/data", "params": {"since": "2026-01-01"}},
            "auth": {"type": "api_key", "header": "X-Key", "value": "{{ secret:api/key }}"},
            "options": {"header": "true"},
        }
    )
    assert "fmt='csv'" in job
    assert "since=2026-01-01" in job
    assert "'X-Key': _cf_resolve_secret('api', 'key')" in job


def test_http_basic_auth_uses_runtime_helper() -> None:
    job = _job(
        {
            "type": "http_json",
            "request": {"url": "https://api.example.com/x"},
            "auth": {"type": "basic", "username": "svc", "password": "{{ secret:api/pw }}"},
        }
    )
    assert "def _cf_basic_auth(username, password):" in job
    assert "_cf_basic_auth('svc', _cf_resolve_secret('api', 'pw'))" in job


def test_http_inline_token_is_refused() -> None:
    with pytest.raises(ValueError, match="secret:scope/key"):
        render_aws_contract(
            _contract(
                {
                    "type": "http_json",
                    "request": {"url": "https://api.example.com/x"},
                    "auth": {"type": "bearer_token", "token": "raw-token-123"},
                }
            )
        )


def test_http_non_https_scheme_is_refused() -> None:
    with pytest.raises(ValueError, match="scheme"):
        render_aws_contract(
            _contract({"type": "http_json", "request": {"url": "file:///etc/passwd"}})
        )


def test_can_render_source_includes_http_file() -> None:
    assert can_render_source({"type": "http_json", "request": {"url": "https://api.example.com/x"}}) is True


def test_http_helper_has_runtime_ssrf_guard_and_no_redirect() -> None:
    job = _job({"type": "http_json", "request": {"url": "https://api.example.com/x"}})
    assert "read_http_file_payload(source)" in job
    assert "socket.getaddrinfo(host, port)" not in job
    assert "CONTRACTFORGE_AWS_ALLOW_PRIVATE_HTTP_TARGETS" not in job
