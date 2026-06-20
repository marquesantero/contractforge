"""Facade for the Delta Sharing connector."""

from contractforge_core.connectors.sharing.delta_share.source import (
    delta_share_options,
    is_delta_share_source,
)

__all__ = ["delta_share_options", "is_delta_share_source"]
