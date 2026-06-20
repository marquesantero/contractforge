"""SSRF guard around HTTP/REST connector initial URLs."""

from __future__ import annotations

import pytest

from contractforge_databricks.runtime.http_safety import (
    ALLOW_PRIVATE_FLAG,
    validate_http_target,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/orders",
        "http://api.example.com/orders",
        "HTTPS://API.EXAMPLE.COM/orders",
    ],
)
def test_public_https_urls_pass(monkeypatch, url: str) -> None:
    import contractforge_core.connectors.api.rest.safety as http_safety

    monkeypatch.delenv(ALLOW_PRIVATE_FLAG, raising=False)
    monkeypatch.setattr(
        http_safety.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 0, "", ("93.184.216.34", 0))],
    )
    validate_http_target(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "gopher://example.com/",
        "ssh://user@example.com/",
        "data:text/plain,abc",
    ],
)
def test_non_http_schemes_are_rejected(monkeypatch, url: str) -> None:
    monkeypatch.delenv(ALLOW_PRIVATE_FLAG, raising=False)
    with pytest.raises(ValueError, match="scheme"):
        validate_http_target(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "https://127.0.0.1:9000/",
        "http://10.0.0.1/",
        "http://192.168.1.50/",
        "http://172.16.0.10/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fe80::1]/",
    ],
)
def test_private_link_local_and_loopback_addresses_are_rejected(
    monkeypatch, url: str
) -> None:
    monkeypatch.delenv(ALLOW_PRIVATE_FLAG, raising=False)
    with pytest.raises(ValueError, match="non-public address"):
        validate_http_target(url)


def test_private_addresses_pass_when_opt_in_flag_is_set(monkeypatch) -> None:
    monkeypatch.setenv(ALLOW_PRIVATE_FLAG, "1")
    validate_http_target("http://10.0.0.1/internal")


def test_rejects_missing_host(monkeypatch) -> None:
    monkeypatch.delenv(ALLOW_PRIVATE_FLAG, raising=False)
    with pytest.raises(ValueError, match="missing a host"):
        validate_http_target("http:///path")


def test_dns_resolution_disallows_link_local(monkeypatch) -> None:
    """If a hostname resolves to a forbidden range we refuse, even with a public name."""

    import contractforge_core.connectors.api.rest.safety as http_safety

    monkeypatch.delenv(ALLOW_PRIVATE_FLAG, raising=False)
    monkeypatch.setattr(
        http_safety.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 0, "", ("169.254.169.254", 0))],
    )

    with pytest.raises(ValueError, match="non-public address"):
        validate_http_target("http://imds.attacker.example/")
