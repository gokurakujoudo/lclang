"""Scoped Frame binding discovery and hierarchy validation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Protocol, cast

from lclang.runtime.modules import Module
from lclang.scopes import (
    ScopedProxyFactory,
    is_frame_proxy,
    real_binding_names,
    scoped_proxy_factory,
    validate_real_conflicts,
)


class ScopedFrame(Protocol):
    """Describe Frame state used by scoped binding operations.

    :param module: Local semantic definition snapshot.
    :param values: Local host-binding view.
    :param parent: Optional next Frame in lookup order.
    :param masked_names: Immutable local exact-name mask policy.
    """

    module: Module
    values: Mapping[str, object]
    parent: ScopedFrame | None
    masked_names: frozenset[str]
    _children: object
    _lifecycle: object


def local_binding_kind(frame: object, name: str) -> str | None:
    """Classify one local binding or inferred prefix.

    :param frame: Frame whose local mappings are inspected.
    :param name: Complete candidate name.
    :returns: ``real``, ``proxy``, ``factory``, or ``None``.
    """
    scoped = cast(ScopedFrame, frame)
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


def walk_hierarchy(frame: object) -> Iterator[ScopedFrame]:
    """Yield one child-to-parent chain while rejecting mutable cycles.

    :param frame: Child-most Frame to traverse.
    :returns: Iterator over each distinct Frame in lookup order.
    :raises ValueError: If the parent graph contains a cycle.
    """
    current: ScopedFrame | None = cast(ScopedFrame, frame)
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
    return any(name in current.masked_names for current in walk_hierarchy(frame))


def find_scoped_binding(frame: object, name: str) -> tuple[ScopedFrame | None, str | None]:
    """Find the nearest real binding or proxy prefix.

    :param frame: Requesting Frame.
    :param name: Complete flat or prefix name.
    :returns: Selected owner and binding kind.
    """
    inferred: ScopedFrame | None = None
    for current in walk_hierarchy(frame):
        kind = local_binding_kind(current, name)
        if kind == "proxy":
            if inferred is None:
                inferred = current
            continue
        if kind is not None:
            return current, kind
    return (inferred, "proxy") if inferred is not None else (None, None)


def find_scoped_factory(frame: object, name: str) -> ScopedProxyFactory | None:
    """Return the selected factory for one exact scoped utility binding.

    :param frame: Owner selected by :func:`find_scoped_binding`.
    :param name: Complete exact utility binding name.
    :returns: Scoped factory or ``None``.
    """
    scoped = cast(ScopedFrame, frame)
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
    pending = [cast(ScopedFrame, frame)]
    while pending:
        current = pending.pop()
        lifecycle = current._lifecycle
        if bool(getattr(lifecycle, "closing", False) or getattr(lifecycle, "closed", False)):
            continue
        validate_real_conflicts(hierarchy_real_names(current, (frame, values)))
        pending.extend(tuple(current._children))  # type: ignore[arg-type]
