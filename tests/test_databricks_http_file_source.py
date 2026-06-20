import pytest

from contractforge_core.contracts import semantic_contract_from_mapping
from contractforge_databricks import DatabricksAdapter
from contractforge_databricks.sources import render_http_file_python


def test_render_http_csv_python_with_bearer_auth_and_limits() -> None:
    code = render_http_file_python(
        {
            "type": "http_csv",
            "request": {"url": "https://example.com/orders.csv", "headers": {"Accept": "text/csv"}},
            "auth": {"type": "bearer_token", "token": "raw-token"},
            "limits": {"timeout_seconds": 30, "max_bytes": 1024},
        }
    )

    assert "from contractforge_core.connectors import download_http_file" in code
    assert "local_path = download_http_file(source)" in code
    assert "'timeout_seconds': 30" in code
    assert ".format('csv')" in code
    assert "'max_bytes': 1024" in code
    assert "raw-token" not in code.split("http_source_review", 1)[1]
    assert "***REDACTED***" in code


def test_render_http_file_requires_format() -> None:
    with pytest.raises(ValueError, match="format"):
        render_http_file_python({"type": "http_file", "url": "https://example.com/data"})


def test_render_http_file_requires_bearer_token() -> None:
    with pytest.raises(ValueError, match="auth.token"):
        render_http_file_python(
            {"type": "http_json", "url": "https://example.com/data.json", "auth": {"type": "bearer_token"}}
        )


def test_render_http_file_supports_params_retry_and_read_options() -> None:
    code = render_http_file_python(
        {
            "type": "http_csv",
            "request": {
                "url": "https://example.com/orders.csv",
                "params": {"region": "br"},
            },
            "options": {"header": True, "delimiter": ";"},
            "limits": {"retry_attempts": 3, "retry_backoff_seconds": 0.5},
        }
    )

    assert "'params': {'region': 'br'}" in code
    assert "'retry_attempts': 3" in code
    assert "'retry_backoff_seconds': 0.5" in code
    assert "reader = reader.option('header', 'true')" in code
    assert "reader = reader.option('delimiter', ';')" in code


def test_render_http_file_rejects_non_get_method() -> None:
    with pytest.raises(ValueError, match="only GET"):
        render_http_file_python(
            {
                "type": "http_json",
                "request": {"url": "https://example.com/data.json", "method": "POST"},
            }
        )


def test_databricks_bundle_renders_http_file_source_artifact() -> None:
    adapter = DatabricksAdapter.from_evidence(
        target_table="main.bronze.orders",
        runtime_type="serverless",
        spark_conf={"spark.databricks.serverless.enabled": "true"},
    )
    contract = semantic_contract_from_mapping(
        {
            "source": {"type": "http_json", "url": "https://example.com/orders.json"},
            "target": {"catalog": "main", "schema": "bronze", "table": "orders"},
            "mode": "scd0_append",
        }
    )

    artifacts = adapter.render_contract(contract)

    assert "main_bronze_orders.source_http_file.py" in artifacts.artifacts
