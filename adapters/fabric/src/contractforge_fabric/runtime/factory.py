"""Factories for Fabric runtime clients."""

from __future__ import annotations

from typing import Any

from contractforge_fabric.environment import FabricEnvironment
from contractforge_fabric.runtime.auth import AzureCliFabricTokenProvider
from contractforge_fabric.runtime.rest import FabricRestClient, FabricTransport, TokenProvider


def fabric_rest_client_from_environment(
    environment: FabricEnvironment | dict[str, Any],
    *,
    access_token: str | None = None,
    token_provider: TokenProvider | None = None,
    transport: FabricTransport | None = None,
    base_url: str = "https://api.fabric.microsoft.com/v1",
) -> FabricRestClient:
    env = environment if isinstance(environment, FabricEnvironment) else FabricEnvironment.from_contract(environment)
    if token_provider is None and access_token is None:
        token_provider = AzureCliFabricTokenProvider(tenant_id=env.tenant_id)
    return FabricRestClient(
        workspace_id=env.workspace_id or "",
        access_token=access_token,
        token_provider=token_provider,
        base_url=base_url,
        transport=transport,
    )
