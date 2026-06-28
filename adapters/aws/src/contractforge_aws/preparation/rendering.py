"""Render portable AWS Glue Spark preparation steps."""

from __future__ import annotations

from contractforge_core.semantic import SemanticContract
from contractforge_aws.preparation.metadata import render_metadata_preparation
from contractforge_aws.preparation.shape import (
    can_render_shape,
    render_shape_preparation,
    shape_requires_flatten,
    shape_requires_functions,
)
from contractforge_aws.preparation.transform import (
    can_render_transform,
    render_transform_preparation,
    transform_requires_functions,
    transform_requires_window,
)


def can_render_preparation(contract: SemanticContract) -> bool:
    """Return whether runtime preparation semantics can be preserved."""

    return can_render_shape(contract) and can_render_transform(contract)


def preparation_requires_functions(contract: SemanticContract) -> bool:
    return shape_requires_functions(contract) or transform_requires_functions(contract)


def preparation_requires_window(contract: SemanticContract) -> bool:
    return transform_requires_window(contract)


def preparation_requires_flatten(contract: SemanticContract) -> bool:
    return shape_requires_flatten(contract)


def render_preparation(contract: SemanticContract, *, dataframe_name: str = "df") -> str:
    if not can_render_preparation(contract):
        raise ValueError(
            "AWS Glue preparation rendering is not implemented for one or more declared shape/transform semantics"
        )

    metadata = dict(contract.operations.metadata or {}) if contract.operations and contract.operations.metadata else {}
    lines: list[str] = []
    lines.extend(
        render_metadata_preparation(
            metadata,
            dataframe_name=dataframe_name,
            include_projection=True,
            include_filter=False,
        )
    )
    lines.extend(render_shape_preparation(contract, dataframe_name=dataframe_name))
    lines.extend(
        render_transform_preparation(
            contract,
            dataframe_name=dataframe_name,
            sections=("cast", "standardize", "derive"),
        )
    )
    lines.extend(
        render_metadata_preparation(
            metadata,
            dataframe_name=dataframe_name,
            include_projection=False,
            include_filter=True,
        )
    )
    lines.extend(
        render_transform_preparation(
            contract,
            dataframe_name=dataframe_name,
            sections=("composite_keys", "deduplicate"),
        )
    )
    if not lines:
        return ""
    return "\n".join(["# Apply portable preparation intent.", *lines, ""])
