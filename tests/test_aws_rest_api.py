"""AWS bounded REST API source rendering via the core REST client."""

from __future__ import annotations

import pytest

from contractforge_aws import render_aws_contract
from contractforge_aws.sources import can_render_source


def _contract(source: dict) -> dict:
    return {"source": source, "target": {"catalog": "lake", "schema": "bronze", "table": "api"}, "mode": "scd0_append"}


def _job(source: dict) -> str:
    job = render_aws_contract(_contract(source)).artifacts["lake_bronze_api.glue_job.py"]
    compile(job, "glue_job.py", "exec")
    return job


def test_rest_api_renders_core_client_call() -> None:
    job = _job(
        {
            "type": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "pagination": {"type": "page"},
            "limits": {"max_pages": 5},
            "auth": {"type": "bearer_token", "token": "{{ secret:api/token }}"},
        }
    )
    assert "from contractforge_core.connectors import read_rest_api_records" in job
    assert "def _cf_rest_dataframe(spark, source):" in job
    assert "_cf_rest_source = {" in job
    assert "df = _cf_rest_dataframe(spark, _cf_rest_source)" in job
    # secret resolved at runtime, not baked
    assert "'token': _cf_resolve_secret('api', 'token')" in job
    assert "{{ secret:api/token }}" not in job
    assert "import boto3" in job
    assert "--additional-python-modules contractforge-core" in job


def test_rest_api_inline_secret_is_refused() -> None:
    with pytest.raises(ValueError, match="secret:scope/key"):
        render_aws_contract(
            _contract(
                {
                    "type": "rest_api",
                    "request": {"url": "https://api.example.com/x"},
                    "auth": {"type": "bearer_token", "token": "raw-token"},
                }
            )
        )


def test_rest_api_non_http_url_is_refused() -> None:
    with pytest.raises(ValueError, match="scheme"):
        render_aws_contract(_contract({"type": "rest_api", "request": {"url": "ftp://api.example.com/x"}}))


def test_can_render_source_includes_rest_api() -> None:
    assert can_render_source({"type": "rest_api", "request": {"url": "https://api.example.com/x"}}) is True
