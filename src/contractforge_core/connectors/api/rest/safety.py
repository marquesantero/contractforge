"""SSRF validation for the platform-neutral bounded REST/HTTP client.

Validates fetch targets before a request leaves the host: only http/https is
allowed, and resolved hosts must be public unless the operator opts in with
``CONTRACTFORGE_ALLOW_PRIVATE_HTTP_TARGETS=1``. DNS rebinding is not fully
mitigated (the IP seen at validation can differ from the one used by the
client); production tenants accepting less-trusted contracts should also
enforce network egress controls.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
from collections.abc import Iterable

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOW_PRIVATE_FLAG = "CONTRACTFORGE_ALLOW_PRIVATE_HTTP_TARGETS"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def validate_http_target(url: str, *, context: str = "HTTP target", resolve: bool = True) -> None:
    parsed = urllib.parse.urlsplit(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"{context} scheme {scheme!r} is not allowed; only http/https are accepted (url={url!r})")
    host = parsed.hostname
    if not host:
        raise ValueError(f"{context} URL is missing a host: {url!r}")
    if _allow_private():
        return
    for address in _candidate_addresses(host, resolve=resolve):
        if _is_disallowed(address):
            raise ValueError(
                f"{context} host {host!r} points at non-public address {address} "
                f"(set {ALLOW_PRIVATE_FLAG}=1 to opt in); url={url!r}"
            )


def _candidate_addresses(host: str, *, resolve: bool) -> Iterable[ipaddress._BaseAddress]:
    try:
        yield ipaddress.ip_address(host)
        return
    except ValueError:
        pass
    if not resolve:
        return
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:  # pragma: no cover - depends on DNS at validation time
        raise ValueError(f"HTTP target host {host!r} could not be resolved during SSRF validation: {exc}") from exc
    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr or sockaddr[0] in seen:
            continue
        seen.add(sockaddr[0])
        try:
            yield ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue


def _is_disallowed(address: ipaddress._BaseAddress) -> bool:
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _allow_private() -> bool:
    return os.environ.get(ALLOW_PRIVATE_FLAG, "").strip().lower() in _TRUE_VALUES
