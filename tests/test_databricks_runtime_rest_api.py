from __future__ import annotations

import json
import urllib.error

import pytest

from contractforge_core.connectors.api.rest import reader as rest_reader
from contractforge_core.connectors.api.rest import auth as rest_core_auth
from contractforge_core.watermark import encode_watermark_values
from contractforge_databricks.runtime.rest_auth import rest_request_headers
from contractforge_databricks.runtime.rest_api import read_rest_api_records, resolve_rest_api_dataframe


@pytest.fixture(autouse=True)
def _public_dns_for_http_safety(monkeypatch):
    # The REST read now validates targets in the core client, so patch the
    # core SSRF resolver to a public address for offline tests.
    import contractforge_core.connectors.api.rest.safety as core_safety

    monkeypatch.setattr(
        core_safety.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 0, "", ("93.184.216.34", 0))],
    )


class Headers(dict):
    def get_content_charset(self):
        return "utf-8"


class FakeResponse:
    def __init__(self, payload: object, *, url: str = "https://api.example.com/orders", headers=None) -> None:
        self.raw = json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload
        self.url = url
        self.headers = Headers(headers or {})

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self.raw

    def geturl(self) -> str:
        return self.url


def _patch_open_request(monkeypatch, fake_open):
    monkeypatch.setattr(rest_reader, "_open_request", lambda request, *, timeout=None: fake_open(request, timeout))
    monkeypatch.setattr(rest_core_auth, "_open_request", lambda request, *, timeout=None: fake_open(request, timeout))


class FakeSpark:
    def __init__(self) -> None:
        self.records = None
        self.schema = None

    def createDataFrame(self, records, schema=None):
        self.records = records
        self.schema = schema
        return "df"


class FakeSparkContext:
    def parallelize(self, rows):
        return list(rows)


class FakeJsonReader:
    def __init__(self) -> None:
        self.schema_value = None
        self.options = {}
        self.json_input = None

    def schema(self, value):
        self.schema_value = value
        return self

    def option(self, key, value):
        self.options[key] = value
        return self

    def json(self, value):
        self.json_input = value
        return "json_df"


class FakeSparkWithJsonReader:
    def __init__(self) -> None:
        self.sparkContext = FakeSparkContext()
        self.read = FakeJsonReader()


def test_read_rest_api_records_from_records_path(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, dict(request.header_items()), timeout))
        return FakeResponse({"items": [{"id": 1}, {"id": 2}]})

    _patch_open_request(monkeypatch, fake_urlopen)

    records = read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {
                "url": "https://api.example.com/orders",
                "params": {"region": "br"},
                "headers": {"Accept": "application/json"},
            },
            "auth": {"type": "bearer_token", "token": "token"},
            "response": {"records_path": "$.items"},
            "limits": {"timeout_seconds": 5},
        }
    )

    assert records == [{"id": 1}, {"id": 2}]
    assert calls[0][0] == "https://api.example.com/orders?region=br"
    assert calls[0][1]["Authorization"] == "Bearer token"
    assert calls[0][2] == 5


def test_read_rest_api_records_does_not_retry_json_parse_errors(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse(b"{not-json")

    _patch_open_request(monkeypatch, fake_urlopen)

    with pytest.raises(json.JSONDecodeError):
        read_rest_api_records(
            {
                "type": "rest_api",
                "url": "https://api.example.com/orders",
                "response": {"records_path": "$.items"},
                "limits": {"retry_attempts": 3},
            }
        )

    assert calls == ["https://api.example.com/orders"]


def test_read_rest_api_records_resolves_databricks_secret_placeholders(monkeypatch) -> None:
    calls = []
    monkeypatch.setenv("CONTRACTFORGE_ALLOW_SECRET_ENV_OVERRIDE", "1")
    monkeypatch.setenv("CONTRACTFORGE_SECRET_API_PROD_TOKEN", "resolved-token")

    def fake_urlopen(request, timeout):
        calls.append(dict(request.header_items()))
        return FakeResponse({"items": []})

    _patch_open_request(monkeypatch, fake_urlopen)

    read_rest_api_records(
        {
            "type": "rest_api",
            "url": "https://api.example.com/orders",
            "auth": {"type": "bearer_token", "token": "{{ secret:api-prod/token }}"},
            "response": {"records_path": "$.items"},
        }
    )

    assert calls[0]["Authorization"] == "Bearer resolved-token"


def test_read_rest_api_records_page_pagination(monkeypatch) -> None:
    urls = []

    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        page = "1" if "page=1" in request.full_url else "2"
        return FakeResponse({"items": [{"page": page}]})

    _patch_open_request(monkeypatch, fake_urlopen)

    records = read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "pagination": {"type": "page", "page_param": "page", "max_pages": 2},
            "response": {"records_path": "$.items"},
        }
    )

    assert records == [{"page": "1"}, {"page": "2"}]
    assert urls == ["https://api.example.com/orders?page=1", "https://api.example.com/orders?page=2"]


def test_read_rest_api_records_supports_basic_auth(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(dict(request.header_items()))
        return FakeResponse({"items": []})

    _patch_open_request(monkeypatch, fake_urlopen)

    read_rest_api_records(
        {
            "type": "rest_api",
            "url": "https://api.example.com/orders",
            "auth": {"type": "basic", "username": "u", "password": "p"},
            "response": {"records_path": "$.items"},
        }
    )

    assert calls[0]["Authorization"] == "Basic dTpw"


def test_read_rest_api_records_supports_oauth_client_credentials(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.data, dict(request.header_items()), timeout))
        if "oauth2" in request.full_url:
            return FakeResponse({"access_token": "oauth-token"})
        return FakeResponse({"items": [{"id": 1}]})

    _patch_open_request(monkeypatch, fake_urlopen)

    records = read_rest_api_records(
        {
            "type": "rest_api",
            "url": "https://api.example.com/orders",
            "auth": {
                "type": "oauth_client_credentials",
                "tenant_id": "tenant-1",
                "client_id": "client-1",
                "client_secret": "secret-1",
                "scopes": ["api://orders/.default"],
            },
            "response": {"records_path": "$.items"},
            "limits": {"timeout_seconds": 8},
        }
    )

    assert records == [{"id": 1}]
    token_request = calls[0]
    api_request = calls[1]
    assert token_request[0] == "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token"
    assert b"client_id=client-1" in token_request[1]
    assert token_request[3] == 8
    assert api_request[2]["Authorization"] == "Bearer oauth-token"


def test_read_rest_api_records_rejects_oauth_without_credentials() -> None:
    with pytest.raises(ValueError, match="OAuth client credentials"):
        read_rest_api_records(
            {
                "type": "rest_api",
                "url": "https://api.example.com/orders",
                "auth": {"type": "oauth_client_credentials", "client_id": "client-1"},
            }
        )


def test_read_rest_api_records_rejects_oauth2_alias() -> None:
    with pytest.raises(ValueError, match="oauth2_client_credentials"):
        rest_request_headers(
            {
                "type": "rest_api",
                "url": "https://api.example.com/orders",
                "auth": {
                    "type": "oauth2_client_credentials",
                    "tenant_id": "tenant-1",
                    "client_id": "client-1",
                    "client_secret": "secret-1",
                },
            }
        )


def test_read_rest_api_records_cursor_pagination(monkeypatch) -> None:
    urls = []

    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        if len(urls) == 1:
            return FakeResponse({"items": [{"id": 1}], "next": "abc"})
        return FakeResponse({"items": [{"id": 2}], "next": None})

    _patch_open_request(monkeypatch, fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    records = read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "pagination": {
                "type": "cursor",
                "cursor_param": "cursor",
                "next_cursor_path": "$.next",
                "max_pages": 3,
            },
            "response": {"records_path": "$.items"},
        }
    )

    assert records == [{"id": 1}, {"id": 2}]
    assert urls == ["https://api.example.com/orders", "https://api.example.com/orders?cursor=abc"]


def test_read_rest_api_records_link_header_pagination(monkeypatch) -> None:
    urls = []

    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        if len(urls) == 1:
            return FakeResponse(
                {"items": [{"id": 1}]},
                headers={"Link": '<https://api.example.com/orders?page=2>; rel="next"'},
            )
        return FakeResponse({"items": [{"id": 2}]})

    _patch_open_request(monkeypatch, fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    records = read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "pagination": {"type": "link_header", "max_pages": 2},
            "response": {"records_path": "$.items"},
        }
    )

    assert records == [{"id": 1}, {"id": 2}]
    assert urls == ["https://api.example.com/orders", "https://api.example.com/orders?page=2"]


def test_read_rest_api_records_respects_rate_limit_between_pages(monkeypatch) -> None:
    urls = []
    sleeps = []
    ticks = iter([100.0, 100.5, 101.5])

    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        return FakeResponse({"items": [{"url": request.full_url}]})

    _patch_open_request(monkeypatch, fake_urlopen)
    monkeypatch.setattr("time.monotonic", lambda: next(ticks))
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))

    records = read_rest_api_records(
        {
            "type": "rest_api",
            "url": "https://api.example.com/orders",
            "pagination": {"type": "page", "max_pages": 2},
            "response": {"records_path": "$.items"},
            "limits": {"rate_limit_per_minute": 60},
        }
    )

    assert len(records) == 2
    assert urls == ["https://api.example.com/orders?page=1", "https://api.example.com/orders?page=2"]
    assert sleeps == [0.5]


def test_read_rest_api_records_raw_mode(monkeypatch) -> None:
    _patch_open_request(monkeypatch, lambda request, timeout: FakeResponse(b'{"ok": true}'))

    records = read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {"url": "https://api.example.com/raw"},
            "response": {"mode": "raw", "raw_column": "payload"},
        }
    )

    assert records == [{"payload": '{"ok": true}', "response_page_number": 1}]


def test_read_rest_api_records_rejects_invalid_raw_column() -> None:
    with pytest.raises(ValueError, match="raw_column"):
        read_rest_api_records(
            {
                "type": "rest_api",
                "url": "https://api.example.com/raw",
                "response": {"mode": "raw", "raw_column": "bad column"},
            }
        )


def test_read_rest_api_records_retries_retryable_errors(monkeypatch) -> None:
    attempts = []

    def fake_urlopen(request, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(request.full_url, 500, "server error", hdrs=None, fp=None)
        return FakeResponse({"id": 1})

    _patch_open_request(monkeypatch, fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    records = read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "limits": {"retry_attempts": 2},
        }
    )

    assert records == [{"id": 1}]
    assert len(attempts) == 2


def test_read_rest_api_records_enforces_max_records(monkeypatch) -> None:
    _patch_open_request(monkeypatch, lambda request, timeout: FakeResponse({"items": [{"id": 1}, {"id": 2}]}))

    with pytest.raises(ValueError, match="limits.max_records"):
        read_rest_api_records(
            {
                "type": "connector",
                "connector": "rest_api",
                "request": {"url": "https://api.example.com/orders"},
                "response": {"records_path": "$.items"},
                "limits": {"max_records": 1},
            }
        )


def test_read_rest_api_records_applies_incremental_watermark_to_query_and_header(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, dict(request.header_items())))
        return FakeResponse({"items": []})

    _patch_open_request(monkeypatch, fake_urlopen)

    read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {"url": "https://api.example.com/orders"},
            "incremental": {
                "watermark_value": "2026-01-01T00:00:00Z",
                "watermark_param": "updated_since",
                "watermark_header": "X-Watermark",
            },
            "response": {"records_path": "$.items"},
        }
    )

    assert calls[0][0] == "https://api.example.com/orders?updated_since=2026-01-01T00%3A00%3A00Z"
    headers = {key.lower(): value for key, value in calls[0][1].items()}
    assert headers["x-watermark"] == "2026-01-01T00:00:00Z"


def test_read_rest_api_records_extracts_typed_incremental_watermark(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse({"items": []})

    _patch_open_request(monkeypatch, fake_urlopen)

    read_rest_api_records(
        {
            "type": "rest_api",
            "url": "https://api.example.com/orders",
            "incremental": {
                "watermark_value": encode_watermark_values({"updated_at": "2026-01-01"}),
                "watermark_column": "updated_at",
                "watermark_param": "updated_since",
            },
            "response": {"records_path": "$.items"},
        }
    )

    assert calls[0] == "https://api.example.com/orders?updated_since=2026-01-01"


def test_read_rest_api_records_applies_incremental_watermark_to_json_body(monkeypatch) -> None:
    bodies = []

    def fake_urlopen(request, timeout):
        bodies.append(request.data)
        return FakeResponse({"id": 1})

    _patch_open_request(monkeypatch, fake_urlopen)

    records = read_rest_api_records(
        {
            "type": "connector",
            "connector": "rest_api",
            "request": {"url": "https://api.example.com/search", "method": "POST", "json": {"status": "open"}},
            "incremental": {
                "watermark_value": "2026-01-01",
                "watermark_body_field": "updated_since",
            },
        }
    )

    assert records == [{"id": 1}]
    assert json.loads(bodies[0].decode("utf-8")) == {"status": "open", "updated_since": "2026-01-01"}


def test_read_rest_api_records_rejects_body_watermark_without_json_body() -> None:
    with pytest.raises(ValueError, match="request.json"):
        read_rest_api_records(
            {
                "type": "connector",
                "connector": "rest_api",
                "request": {"url": "https://api.example.com/search", "method": "POST", "body": "{}"},
                "incremental": {"watermark_value": "2026-01-01", "watermark_body_field": "updated_since"},
            }
        )


def test_resolve_rest_api_dataframe_uses_spark_create_dataframe(monkeypatch) -> None:
    spark = FakeSpark()
    monkeypatch.setattr(
        "contractforge_databricks.runtime.rest_api.read_rest_api_records",
        lambda source: [{"id": 1}],
    )

    assert resolve_rest_api_dataframe(spark, {"type": "connector", "connector": "rest_api"}) == "df"
    assert spark.records == [{"id": 1}]


def test_resolve_rest_api_dataframe_applies_declared_schema(monkeypatch) -> None:
    spark = FakeSpark()
    monkeypatch.setattr(
        "contractforge_databricks.runtime.rest_api.read_rest_api_records",
        lambda source: [{"id": 1}],
    )

    assert resolve_rest_api_dataframe(
        spark,
        {"type": "connector", "connector": "rest_api", "read": {"schema": "id BIGINT"}},
    ) == "df"
    assert spark.schema == "id BIGINT"


def test_resolve_rest_api_dataframe_uses_json_reader_when_available(monkeypatch) -> None:
    spark = FakeSparkWithJsonReader()
    monkeypatch.setattr(
        "contractforge_databricks.runtime.rest_api.read_rest_api_records",
        lambda source: [{"id": 1, "items": [{"sku": "a"}]}],
    )

    assert resolve_rest_api_dataframe(
        spark,
        {
            "type": "rest_api",
            "url": "https://api.example.com/orders",
            "read": {"schema": "id BIGINT, items ARRAY<STRUCT<sku:STRING>>", "json_options": {"multiLine": False}},
        },
    ) == "json_df"
    assert spark.read.schema_value == "id BIGINT, items ARRAY<STRUCT<sku:STRING>>"
    assert spark.read.options == {"multiLine": "false"}
    assert '"items": [{"sku": "a"}]' in spark.read.json_input[0]


def test_read_rest_api_records_rejects_unsupported_method() -> None:
    with pytest.raises(ValueError, match="only GET and POST"):
        read_rest_api_records(
            {
                "type": "connector",
                "connector": "rest_api",
                "request": {"url": "https://api.example.com/orders", "method": "PUT"},
            }
        )
