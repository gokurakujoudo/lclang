"""Structural Frame chain collection and binding resolution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

from lclang.runtime.dependency.frame.model import FrameDependencyBinding
from lclang.runtime.modules import Module
from lclang.types import FrameId


class GraphFrame(Protocol):
    """Describe immutable inputs consumed by Frame graph construction.

    :param module: Local immutable definition snapshot.
    :param frame_id: Non-empty diagnostic identity.
    :param values: Current read-only host-binding view.
    :param parent: Optional next owner in the lookup chain.

    .. note::
       Cache, lifecycle, and evaluation members are deliberately absent.
    """

    module: Module
    frame_id: FrameId
    values: Mapping[str, object]
    parent: GraphFrame | None


def collect_frames(frame: object) -> tuple[GraphFrame, ...]:
    """Collect one linear child-to-parent chain with cycle detection.

    :param frame: Child-most concrete Frame.
    :returns: Ordered structural Frame views through the root owner.
    :raises ValueError: If an object identity repeats in the parent chain.

    .. note::
       Object identity detects cycles even when Frame IDs intentionally repeat.
    """
    result: list[GraphFrame] = []
    seen: set[int] = set()
    current: object | None = frame
    while current is not None:
        identity = id(current)
        if identity in seen:
            raise ValueError("Frame hierarchy contains a parent cycle")
        seen.add(identity)
        selected = cast(GraphFrame, current)
        result.append(selected)
        current = selected.parent
    return tuple(result)


def resolve_frame_binding(
    frames: tuple[GraphFrame, ...],
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
    searched: list[FrameId] = []
    for index in range(owner_index, len(frames)):
        searched.append(frames[index].frame_id)
        definition = definition_map.get((index, name))
        if definition is not None:
            return definition, tuple(searched)
        value = value_map.get((index, name))
        if value is not None:
            return value, tuple(searched)
    return None, tuple(searched)
