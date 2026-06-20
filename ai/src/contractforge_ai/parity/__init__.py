"""Platform parity reporting for ContractForge AI."""

from contractforge_ai.parity.models import ContractParityItem, PlatformParityReport
from contractforge_ai.parity.platforms import DEFAULT_PARITY_ADAPTERS, compare_platforms

__all__ = [
    "ContractParityItem",
    "DEFAULT_PARITY_ADAPTERS",
    "PlatformParityReport",
    "compare_platforms",
]
