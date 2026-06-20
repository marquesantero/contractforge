"""Render AWS Glue bounded HTTP(S) file sources.

The contract's ``http_file``/``http_csv``/``http_json``/``http_text`` types
describe a bounded HTTP fetch. The AWS adapter renders a runtime helper that
fetches the URL on the Glue driver (with a scheme guard and byte limit) and
parses the bounded payload in-memory into a Spark DataFrame, so it works
without a shared local filesystem between driver and executors.

Credentials in auth headers are never baked into the artifact: bearer/api-key
values must be ``{{ secret:scope/key }}`` placeholders (resolved at runtime via
Secrets Manager), and basic auth is base64-encoded at runtime after the secret
is resolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from contractforge_core.connectors import http_file_format, http_file_reader_options, http_file_url
from contractforge_aws.security import contains_secret_placeholder, render_secret_aware_literal

__all__ = [
    "render_http_file_source",
    "render_http_file_helper",
    "render_http_basic_auth_helper",
    "source_requires_http_basic_auth",
]


@dataclass(frozen=True)
class _HttpAuthRenderer:
    auth_type: str
    render: Callable[[dict[str, Any]], dict[str, str]]


def source_requires_http_basic_auth(source: dict[str, Any]) -> bool:
    return str((source.get("auth") or {}).get("type") or "").strip().lower() == "basic"


def render_http_file_source(source: dict[str, Any], *, dataframe_name: str = "df") -> str:
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    url = str(source.get("url") or request.get("url") or "").strip()
    if not url:
        raise ValueError("HTTP file source requires request.url")
    method = str(request.get("method") or "GET").upper()
    if method != "GET":
        raise ValueError("HTTP file source supports only GET")
    final_url = http_file_url(source)
    limits = source.get("limits", {}) if isinstance(source.get("limits"), dict) else {}
    max_bytes = limits.get("max_bytes")
    retry_attempts = limits.get("retry_attempts", source.get("read", {}).get("retry_attempts", 1))
    retry_backoff = limits.get("retry_backoff_seconds", source.get("read", {}).get("retry_backoff_seconds", 0))
    lines = [
        f"{dataframe_name} = _cf_http_dataframe(",
        "    spark,",
        f"    url={render_secret_aware_literal(final_url)},",
        f"    headers={_render_headers_expr(source)},",
        f"    fmt={http_file_format(source)!r},",
        f"    options={http_file_reader_options(source)!r},",
        f"    timeout={int(limits.get('timeout_seconds', 60))},",
        f"    retry_attempts={int(retry_attempts)},",
        f"    retry_backoff_seconds={float(retry_backoff)!r},",
        f"    max_bytes={int(max_bytes) if max_bytes is not None else None!r},",
        ")",
    ]
    return "\n".join(lines) + "\n"


def render_http_file_helper() -> str:
    """Render the Glue-runtime ``_cf_http_dataframe`` helper definition.

    The helper validates the *resolved* host before fetching (rejecting private,
    loopback, link-local and reserved ranges, which covers the IMDS endpoint)
    and refuses HTTP redirects, so a hostname that resolves to internal space or
    a 3xx bounce cannot exfiltrate auth headers toward an unvetted host. Set
    CONTRACTFORGE_ALLOW_PRIVATE_HTTP_TARGETS=1 to opt in to private targets.
    """

    return "\n".join(
        [
            "def _cf_http_dataframe(spark, url, headers, fmt, options, timeout, retry_attempts, retry_backoff_seconds, max_bytes):",
            '    """Fetch a bounded HTTP(S) file and parse it into a DataFrame at runtime."""',
            "    from contractforge_core.connectors import read_http_file_payload",
            "    source = {",
            "        'type': 'http_file',",
            "        'url': url,",
            "        'format': fmt,",
            "        'request': {'url': url, 'headers': headers},",
            "        'options': options,",
            "        'limits': {",
            "            'timeout_seconds': timeout,",
            "            'retry_attempts': retry_attempts,",
            "            'retry_backoff_seconds': retry_backoff_seconds,",
            "        },",
            "    }",
            "    if max_bytes is not None:",
            "        source['limits']['max_bytes'] = max_bytes",
            "    payload = read_http_file_payload(source)",
            "    text = payload.decode('utf-8')",
            "    multiline = str(options.get('multiLine', options.get('multiline', 'false'))).lower() == 'true'",
            "    records = [text] if multiline else (text.splitlines() or [''])",
            "    rdd = spark.sparkContext.parallelize(records)",
            "    reader = spark.read",
            "    for key, value in sorted(options.items()):",
            "        reader = reader.option(key, value)",
            "    if fmt == 'csv':",
            "        return reader.csv(rdd)",
            "    if fmt == 'text':",
            "        return rdd.map(lambda value: (value,)).toDF(['value'])",
            "    return reader.json(rdd)",
            "",
        ]
    )


def render_http_basic_auth_helper() -> str:
    """Render the Glue-runtime ``_cf_basic_auth`` helper definition."""

    return "\n".join(
        [
            "def _cf_basic_auth(username, password):",
            '    """Build a runtime HTTP Basic auth header without baking credentials."""',
            "    import base64",
            "    raw = (str(username) + ':' + str(password)).encode('utf-8')",
            "    return 'Basic ' + base64.b64encode(raw).decode('ascii')",
            "",
        ]
    )


def _render_headers_expr(source: dict[str, Any]) -> str:
    request = source.get("request") if isinstance(source.get("request"), dict) else {}
    entries: dict[str, str] = {
        str(key): render_secret_aware_literal(str(value))
        for key, value in (request.get("headers") or {}).items()
    }
    auth = source.get("auth") if isinstance(source.get("auth"), dict) else {}
    auth_type = str(auth.get("type") or "none").strip().lower()
    renderer = _HTTP_AUTH_RENDERERS.get(auth_type)
    if renderer is not None:
        entries.update(renderer.render(auth))
    elif auth_type not in {"", "none"}:
        raise ValueError(f"auth.type={auth_type!r} is not supported for HTTP file sources")
    body = ", ".join(f"{key!r}: {value}" for key, value in entries.items())
    return "{" + body + "}"


def _bearer_auth_headers(auth: dict[str, Any]) -> dict[str, str]:
    token = _require_secret(auth.get("token"), "auth.token")
    return {"Authorization": render_secret_aware_literal("Bearer " + token)}


def _api_key_auth_headers(auth: dict[str, Any]) -> dict[str, str]:
    header = str(auth.get("header") or "X-Api-Key")
    return {header: render_secret_aware_literal(_require_secret(auth.get("value"), "auth.value"))}


def _basic_auth_headers(auth: dict[str, Any]) -> dict[str, str]:
    username = render_secret_aware_literal(str(auth.get("username") or ""))
    password = render_secret_aware_literal(_require_secret(auth.get("password"), "auth.password"))
    return {"Authorization": f"_cf_basic_auth({username}, {password})"}


_HTTP_AUTH_RENDERERS: dict[str, _HttpAuthRenderer] = {
    renderer.auth_type: renderer
    for renderer in (
        _HttpAuthRenderer("bearer_token", _bearer_auth_headers),
        _HttpAuthRenderer("api_key", _api_key_auth_headers),
        _HttpAuthRenderer("basic", _basic_auth_headers),
    )
}


def _require_secret(value: Any, field: str) -> str:
    text = str(value or "")
    if not text:
        raise ValueError(f"HTTP file source {field} is required for this auth type")
    if not contains_secret_placeholder(text):
        raise ValueError(
            f"HTTP file source {field} must be a {{{{ secret:scope/key }}}} placeholder so the credential is "
            "resolved at runtime instead of being baked into the published Glue script."
        )
    return text
