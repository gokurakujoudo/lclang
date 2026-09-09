"""Structural Frame chain collection and binding resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.runtime.frame.binding_lookup import select_binding, walk_hierarchy

if TYPE_CHECKING:
    from lclang.runtime.frame.frame import Frame

from lclang.runtime.dependency.frame.model import FrameDependencyBinding
from lclang.types import FrameId


def collect_frames(frame: object) -> tuple[Frame, ...]:
    """Collect one linear child-to-parent chain with cycle detection.

    :param frame: Child-most concrete Frame.
    :returns: Ordered structural Frame views through the root owner.
    :raises ValueError: If an object identity repeats in the parent chain.

    .. note::
       Object identity detects cycles even when Frame IDs intentionally repeat.
    """
    return tuple(walk_hierarchy(frame))


def resolve_frame_binding(
    frames: tuple[Frame, ...],
    owner_index: int,
    name: str,
    definition_map: dict[tuple[int, str], FrameDependencyBinding],
    value_map: dict[tuple[int, str], FrameDependencyBinding],
) -> tuple[FrameDependencyBinding | None, tuple[FrameId, ...]]:
    """Apply Frame precedence without evaluating the selected binding.

    :param frames: Complete child-to-parent hierarchy.
    :param owner_index: First Frame searched for the requesting definition.
    :param name: Referenced free-name spelling.
    :param definition_map: Owner-index/name definition lookup.
    :param value_map: Owner-index/name host-value lookup.
    :returns: Selected binding or ``None``, plus every searched Frame ID.

    .. note::
       A same-Frame definition wins before a same-name host value.
    """
    selected = select_binding(frames[owner_index], name)
    index = owner_index + len(selected.path) - 1
    key = (index, name)
    binding = definition_map.get(key) or value_map.get(key)
    return binding, selected.path
