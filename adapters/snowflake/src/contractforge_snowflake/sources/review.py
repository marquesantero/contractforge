"""Review-required Snowflake source families.

Runtime support stays deliberately narrower than planner review support. This
module centralizes source names that should remain review-required or
unsupported until dedicated renderers and live smoke coverage exist.
"""

REVIEW_REQUIRED_SOURCE_TYPES = frozenset(
    {
        "incremental_files",
        "snowpipe",
        "external_stage_stream",
    }
)

UNSUPPORTED_SOURCE_TYPES = frozenset(
    {
        "autoloader",
        "cloudfiles",
    }
)

__all__ = ["REVIEW_REQUIRED_SOURCE_TYPES", "UNSUPPORTED_SOURCE_TYPES"]
