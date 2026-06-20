"""Auth header construction for the platform-neutral bounded REST client.

This module operates on already-resolved values. Adapters are responsible for
resolving any secret placeholders (e.g. via their platform secret store) before
calling these helpers, so the core never depends on a platform secret backend.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from typing import Any

from contractforge_core.connectors.api.rest.safety import validate_http_target
from contractforge_core.connectors.api.rest.transport import open_request as _open_request


def rest_request_headers(
    source: dict[str, Any],
    incremental: dict[str, Any] | None = None,
    watermark: str | None = None,
) -> dict[str, str]:
    request = _dict(source.get("request"))
    headers = _string_dict(request.get("headers"))
    auth = _dict(source.get("auth"))
    auth_type = str(auth.get("type") or "").strip().lower()
    if auth_type == "bearer_token":
        token = auth.get("token")
        if not token:
            raise ValueError("REST API bearer_token auth requires auth.token")
        headers["Authorization"] = f"Bearer {token}"
    if auth_type == "api_key":
        api_key = auth.get("value")
        if not api_key:
            raise ValueError("REST API api_key auth requires auth.value")
        headers[str(auth.get("header") or "X-Api-Key")] = str(api_key)
    if auth_type == "basic":
        username = auth.get("username")
        password = auth.get("password")
        if not username or not password:
            raise ValueError("REST API basic auth requires auth.username and auth.password")
        raw = f"{username}:{password}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    if auth_type == "oauth_client_credentials":
        headers["Authorization"] = f"Bearer {_oauth_client_credentials_token(auth, source)}"
    if auth and auth_type not in {"bearer_token", "api_key", "basic", "oauth_client_credentials"}:
        raise ValueError(f"REST API auth.type={auth_type!r} is not supported")
    incremental = incremental or {}
    if watermark and incremental.get("watermark_header"):
        headers[str(incremental["watermark_header"])] = watermark
    return headers


def _oauth_client_credentials_token(auth: dict[str, Any], source: dict[str, Any]) -> str:
    token_url = str(auth.get("token_url") or "").strip()
    tenant_id = str(auth.get("tenant_id") or "").strip()
    if not token_url and tenant_id:
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    client_id = auth.get("client_id")
    client_secret = auth.get("client_secret")
    if not token_url or not client_id or not client_secret:
        raise ValueError(
            "REST API OAuth client credentials auth requires auth.token_url, auth.client_id and auth.client_secret; "
            "auth.tenant_id can replace auth.token_url for Microsoft Entra ID."
        )
    fields = {
        "grant_type": "client_credentials",
        "client_id": str(client_id),
        "client_secret": str(client_secret),
    }
    scope = auth.get("scope")
    scopes = auth.get("scopes")
    if scope:
        fields["scope"] = str(scope)
    elif isinstance(scopes, (list, tuple, set)):
        fields["scope"] = " ".join(str(item) for item in scopes if str(item).strip())
    elif scopes:
        fields["scope"] = str(scopes)
    timeout = int(_dict(source.get("limits")).get("timeout_seconds", 60))
    validate_http_target(token_url, context="REST API OAuth token URL")
    request = urllib.request.Request(
        token_url,
        method="POST",
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with _open_request(request, timeout=timeout) as response:
        raw = response.read()
        encoding = response.headers.get_content_charset() if hasattr(response.headers, "get_content_charset") else None
        payload = json.loads(raw.decode(encoding or "utf-8")) if raw else {}
    token = payload.get("access_token")
    if not token:
        raise ValueError("OAuth response did not return access_token")
    return str(token)


def _dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_dict(value: object) -> dict[str, str]:
    return {str(key): str(item) for key, item in _dict(value).items()}
