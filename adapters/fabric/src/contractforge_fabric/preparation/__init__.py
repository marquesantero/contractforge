"""Fabric notebook preparation rendering."""

from contractforge_fabric.preparation.flatten import render_flatten_helper
from contractforge_fabric.preparation.shape import can_render_shape, render_shape_preparation, shape_requires_flatten
from contractforge_fabric.preparation.transform import (
    can_render_preparation,
    can_render_transform,
    render_preparation,
    render_transform_preparation,
    transform_requires_window,
)

__all__ = [
    "can_render_preparation",
    "can_render_shape",
    "can_render_transform",
    "render_flatten_helper",
    "render_preparation",
    "render_shape_preparation",
    "render_transform_preparation",
    "shape_requires_flatten",
    "transform_requires_window",
]
