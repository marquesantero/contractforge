"""Facade for the data sharing connector family."""

from contractforge_core.connectors.sharing.delta_share import (
    delta_share_options,
    is_delta_share_source,
)

__all__ = ["delta_share_options", "is_delta_share_source"]
