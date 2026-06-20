"""Snowflake contract extension accessors and guardrails."""

from __future__ import annotations

from typing import Any

from contractforge_core.planner import PlanningWarning

SNOWFLAKE_EXTENSION_FIELDS = frozenset(
    {
        "annotation_tag_mode",
        "explain_enabled",
        "explain_format",
        "lock_enabled",
        "lock_owner",
        "lock_ttl_minutes",
        "tag_mode",
    }
)


def snowflake_extensions(contract: Any) -> dict[str, Any]:
    """Return the adapter-owned ``extensions.snowflake`` map."""

    extensions = getattr(contract, "extensions", None)
    if not isinstance(extensions, dict):
        return {}
    value = extensions.get("snowflake")
    return dict(value) if isinstance(value, dict) else {}


def snowflake_extension_warnings(contract: Any) -> tuple[PlanningWarning, ...]:
    """Return warnings for Snowflake extension keys the adapter will ignore."""

    unknown = sorted(set(snowflake_extensions(contract)) - SNOWFLAKE_EXTENSION_FIELDS)
    return tuple(
        PlanningWarning(
            code="SNOWFLAKE_UNKNOWN_EXTENSION",
            message=(
                f"extensions.snowflake.{name} is not a recognized Snowflake adapter extension "
                "and will not be honored by planning, rendering or runtime execution."
            ),
        )
        for name in unknown
    )


__all__ = [
    "SNOWFLAKE_EXTENSION_FIELDS",
    "snowflake_extension_warnings",
    "snowflake_extensions",
]
