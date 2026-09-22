"""Scoped Frame binding discovery and hierarchy validation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from lclang.types import FrameId

if TYPE_CHECKING:
    from lclang.runtime.frame.frame import Frame

from lclang.scopes import (
    ScopedProxyFactory,
    is_frame_proxy,
    real_binding_names,
    scoped_proxy_factory,
    validate_real_conflicts,
)


def local_binding_kind(frame: object, name: str) -> str | None:
    """Classify one local binding or inferred prefix.

    :param frame: Frame whose local mappings are inspected.
    :param name: Complete candidate name.
    :returns: ``real``, ``proxy``, ``factory``, or ``None``.
    """
    scoped = cast("Frame", frame)
    if name in scoped.module.definitions:
        definition_value = scoped.module.definitions[name]
        return "proxy" if is_frame_proxy(definition_value) else "real"
    if name in scoped.values:
        host_value = scoped.values[name]
        if scoped_proxy_factory(host_value) is not None:
            return "factory"
        return "proxy" if is_frame_proxy(host_value) else "real"
    prefix = f"{name}."
    if any(key.startswith(prefix) for key in scoped.module.definitions):
        return "proxy"
    if any(key.startswith(prefix) for key in scoped.values):
        return "proxy"
    return None


def walk_hierarchy(frame: object) -> Iterator[Frame]:
    """Yield one child-to-parent chain while rejecting mutable cycles.

    :param frame: Child-most Frame to traverse.
    :returns: Iterator over each distinct Frame in lookup order.
    :raises ValueError: If the parent graph contains a cycle.
    """
    current: Frame | None = cast("Frame", frame)
    seen: set[int] = set()
    while current is not None:
        identity = id(current)
        if identity in seen:
            raise ValueError("Frame parent cycle detected")
        seen.add(identity)
        yield current
        current = current.parent


def is_name_masked(frame: object, name: str) -> bool:
    """Report whether any effective hierarchy layer masks one exact name.

    :param frame: Child-most Frame to inspect.
    :param name: Normalized exact binding name.
    :returns: Whether the name is marked in any visible layer.
    """
    from lclang.runtime.frame.defaults import default_frame_for

    defaults = default_frame_for(cast("Frame", frame))
    return any(name in current.masked_names for current in walk_hierarchy(frame)) or (
        defaults is not None and name in defaults.masked_names
    )


def find_scoped_binding(frame: object, name: str) -> tuple[Frame | None, str | None]:
    """Find the nearest real binding or proxy prefix.

    :param frame: Requesting Frame.
    :param name: Complete flat or prefix name.
    :returns: Selected owner and binding kind.
    """
    selected = select_binding(frame, name)
    return selected.owner, selected.kind


@dataclass(frozen=True, slots=True)
class BindingSelection:
    """Retain one operation's selected binding without caching hierarchy state.

    :param owner: Selected Frame, or None for a missing binding.
    :param kind: Real, proxy or factory binding classification, or None.
    :param path: Child-to-owner diagnostic identifiers, or the full missing path.
    """

    owner: Frame | None
    kind: str | None
    path: tuple[FrameId, ...]


def select_binding(frame: object, name: str) -> BindingSelection:
    """Scan a hierarchy once, preferring concrete bindings to inferred proxies.

    :param frame: Requesting Frame whose hierarchy is inspected.
    :param name: Complete normalized binding name.
    :returns: Owner, kind and diagnostic path for this operation only.
    :raises ValueError: If mutable parents form a cycle.
    """
    inferred: BindingSelection | None = None
    path: list[FrameId] = []
    for layer in walk_hierarchy(frame):
        current = layer
        path.append(current.frame_id)
        kind = local_binding_kind(current, name)
        if kind == "proxy":
            if inferred is None:
                inferred = BindingSelection(current, kind, tuple(path))
        elif kind is not None:
            return BindingSelection(current, kind, tuple(path))
    if inferred is not None:
        return inferred
    from lclang.runtime.frame.defaults import default_frame_for

    defaults = default_frame_for(cast("Frame", frame))
    if defaults is not None:
        prefixes = [".".join(name.split(".")[:index]) for index in range(1, len(name.split(".")))]
        blocked = any(
            local_binding_kind(owner, prefix) in {"real", "factory"}
            for owner in walk_hierarchy(frame) for prefix in prefixes
        )
        if not blocked and (kind := local_binding_kind(defaults, name)) is not None:
            return BindingSelection(defaults, kind, (*path, defaults.frame_id))
    return BindingSelection(None, None, tuple(path))



def find_scoped_factory(frame: object, name: str) -> ScopedProxyFactory | None:
    """Return the selected factory for one exact scoped utility binding.

    :param frame: Owner selected by :func:`find_scoped_binding`.
    :param name: Complete exact utility binding name.
    :returns: Scoped factory or ``None``.
    """
    scoped = cast("Frame", frame)
    return cast(ScopedProxyFactory, scoped.values[name])


def hierarchy_real_names(
    frame: object,
    replacement: tuple[object, Mapping[str, object]] | None = None,
) -> tuple[str, ...]:
    """Collect effective real names through one Frame chain.

    :param frame: Child-most Frame to inspect.
    :param replacement: Optional prospective values for one owner.
    :returns: Real names in child-to-parent order.
    """
    result: list[str] = []
    for current in walk_hierarchy(frame):
        values = (
            replacement[1]
            if replacement is not None and current is replacement[0]
            else current.values
        )
        result.extend(real_binding_names(current.module.definitions, values))
    return tuple(result)


def hierarchy_binding_names(frame: object) -> tuple[str, ...]:
    """Collect all names visible from one Frame.

    :param frame: Child-most Frame.
    :returns: Definition and value names in hierarchy order.
    """
    result: list[str] = []
    for current in walk_hierarchy(frame):
        result.extend(current.module.definitions)
        result.extend(name for name in current.values if name not in current.module.definitions)
    from lclang.runtime.frame.defaults import default_frame_for

    defaults = default_frame_for(cast("Frame", frame))
    if defaults is not None:
        result.extend(
            name for name in (*defaults.module.definitions, *defaults.values)
            if name not in result and select_binding(frame, name).owner is not None
        )
    return tuple(result)


def validate_frame_hierarchy(frame: object) -> None:
    """Reject scoped real-value conflicts in one hierarchy.

    :param frame: Child-most effective Frame.
    :raises ValueError: If real ancestor/descendant keys coexist.
    """
    validate_real_conflicts(hierarchy_real_names(frame))


def validate_mixin_tree(frame: object, values: Mapping[str, object]) -> None:
    """Validate a prospective mixin against every live descendant.

    :param frame: Frame receiving the update.
    :param values: Complete prospective local values.
    :raises ValueError: If any affected hierarchy would conflict.
    """
    pending = [cast("Frame", frame)]
    while pending:
        current = pending.pop()
        lifecycle = current._lifecycle
        if bool(getattr(lifecycle, "closing", False) or getattr(lifecycle, "closed", False)):
            continue
        validate_real_conflicts(hierarchy_real_names(current, (frame, values)))
        pending.extend(tuple(current._children))


def find_frame(frame: object, name: str) -> Frame | None:
    """Return the nearest Frame that owns a selected name binding.

    :param frame: First Frame in the child-to-parent search.
    :param name: Non-empty definition or host-value name.
    :returns: Nearest owning Frame, or ``None`` when the hierarchy lacks *name*.
    :raises ValueError: If *name* is empty.

    .. note::
       A local definition wins over a same-Frame value; either stops recursion.
    """
    if not name:
        raise ValueError("variable name cannot be empty")
    owner, _ = find_scoped_binding(frame, name)
    return owner
