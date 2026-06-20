from __future__ import annotations

import subprocess

import pytest

from contractforge_fabric.runtime import AzureCliFabricTokenProvider, FABRIC_RESOURCE


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["az"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_azure_cli_fabric_token_provider_uses_fabric_resource_and_tenant() -> None:
    calls: list[list[str]] = []

    def runner(args) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return _completed(stdout='{"accessToken":"token-1"}')

    token = AzureCliFabricTokenProvider(tenant_id="tenant-1", runner=runner)()

    assert token == "token-1"
    assert calls == [
        [
            "az",
            "account",
            "get-access-token",
            "--resource",
            FABRIC_RESOURCE,
            "-o",
            "json",
            "--tenant",
            "tenant-1",
        ]
    ]


def test_azure_cli_fabric_token_provider_reports_cli_failure() -> None:
    provider = AzureCliFabricTokenProvider(runner=lambda _args: _completed(stderr="login required", returncode=1))

    with pytest.raises(RuntimeError, match="login required"):
        provider()


def test_azure_cli_fabric_token_provider_rejects_missing_access_token() -> None:
    provider = AzureCliFabricTokenProvider(runner=lambda _args: _completed(stdout="{}"))

    with pytest.raises(RuntimeError, match="accessToken"):
        provider()
