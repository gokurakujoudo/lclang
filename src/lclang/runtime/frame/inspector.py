"""Pure construction of name-deduplicated variable inspection trees."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol, cast

from lclang.errors import LclNameError
from lclang.runtime.dependency.analysis import analyze_dependencies
from lclang.runtime.frame.inspection import (
    VariableInspectionStatus,
    VariableInspectionTree,
)
from lclang.runtime.frame.lifecycle import InternalFrameLifecycle
from lclang.runtime.modules import Module
from lclang.types import FrameId, VarName

if TYPE_CHECKING:
    from lclang.runtime.frame.core import Frame


class InspectionFrame(Protocol):
    """Describe read-only Frame state required by inspection construction.

    :param module: Immutable local definitions.
    :param frame_id: Diagnostic identifier retained in lookup paths.
    :param values: Read-only local host-value view.
    :param parent: Optional next Frame in lookup order.
    :param native_values: Whether local host bindings are canonical lclang values.

    .. note::
       Cache dictionaries are read for membership only and are never changed.
    """

    module: Module
    frame_id: FrameId
    values: Mapping[str, object]
    parent: InspectionFrame | None
    native_values: bool
    _results: dict[str, object]
    _failures: dict[str, Exception]
    _lifecycle: InternalFrameLifecycle


class FrameInspectionApi:
    """Provide side-effect-free variable tree inspection for concrete Frames.

    .. note::
       Concrete Frames supply lifecycle, hierarchy, syntax, and cache state.
    """

    def inspect_variable(self, var_name: str) -> VariableInspectionTree:
        """Inspect one selected variable and its unique direct dependency names.

        :param var_name: Non-empty name whose lookup starts at this Frame.
        :returns: A detached tree of cache, syntax, path, and dependency evidence.
        :raises TypeError: If *var_name* is not a string.
        :raises ValueError: If *var_name* is empty or the parent graph cycles.
        :raises LclClosedFrameError: If this Frame is closing or closed.

        .. note::
           Inspection never evaluates, awaits, creates tasks, or publishes traces.
        """
        if not isinstance(var_name, str):
            raise TypeError("variable name must be a string")
        if not var_name:
            raise ValueError("variable name cannot be empty")
        frame = cast(InspectionFrame, self)
        frame._lifecycle.ensure_open(None)
        return build_inspection_tree(frame, var_name, frozenset())


def build_inspection_tree(
    origin: InspectionFrame,
    name: str,
    ancestors: frozenset[tuple[int, str]],
) -> VariableInspectionTree:
    """Build one lookup node and recursively inspect its static dependencies.

    :param origin: Frame where this name lookup begins.
    :param name: Requested non-empty variable name.
    :param ancestors: Owner/name pairs already expanded on the current branch.
    :returns: One detached inspection node with first-seen unique direct children.
    :raises ValueError: If the Frame parent object graph cycles.
    :raises LclClosedFrameError: If a selected owner is closing or closed.

    .. note::
       Ancestors are path-local so duplicate variables on sibling branches expand.
    """
    owner, path = resolve_inspection_owner(origin, name)
    if owner is None:
        return VariableInspectionTree(
            VarName(name),
            VariableInspectionStatus.NOT_EVALUATED,
            None,
            path,
            cast("Frame", origin),
            None,
            LclNameError(f"unknown variable: {name}"),
            [],
        )
    owner._lifecycle.ensure_open(None)
    definition = owner.module.definitions.get(name)
    if definition is None:
        status = (
            VariableInspectionStatus.NATIVE_PROVIDED
            if owner.native_values
            else VariableInspectionStatus.EXTERNAL_PROVIDED
        )
        return VariableInspectionTree(
            VarName(name),
            status,
            None,
            path,
            cast("Frame", owner),
            owner.values[name],
            None,
            [],
        )
    status, value, error = inspect_cache(owner, name)
    key = (id(owner), name)
    dependencies: list[VariableInspectionTree] = []
    if key not in ancestors:
        next_ancestors = ancestors | {key}
        dependency_names = dict.fromkeys(
            str(reference.name) for reference in analyze_dependencies(definition)
        )
        dependencies = [
            build_inspection_tree(owner, dependency_name, next_ancestors)
            for dependency_name in dependency_names
        ]
    return VariableInspectionTree(
        VarName(name),
        status,
        definition,
        path,
        cast("Frame", owner),
        value,
        error,
        dependencies,
    )


def resolve_inspection_owner(
    origin: InspectionFrame,
    name: str,
) -> tuple[InspectionFrame | None, list[FrameId]]:
    """Resolve one binding while retaining its exact child-to-owner path.

    :param origin: Frame where lookup begins.
    :param name: Requested variable name.
    :returns: Selected owner or ``None``, plus every searched Frame identifier.
    :raises ValueError: If the mutable parent object graph contains a cycle.

    .. note::
       Definitions and host values share evaluator precedence at every level.
    """
    current: InspectionFrame | None = origin
    seen: set[int] = set()
    path: list[FrameId] = []
    while current is not None:
        identity = id(current)
        if identity in seen:
            raise ValueError("Frame parent cycle detected")
        seen.add(identity)
        path.append(current.frame_id)
        if name in current.module.definitions or name in current.values:
            return current, path
        current = current.parent
    return None, path


def inspect_cache(
    owner: InspectionFrame,
    name: str,
) -> tuple[VariableInspectionStatus, object | None, Exception | None]:
    """Read the committed cache state for one definition without joining work.

    :param owner: Frame that owns the selected definition.
    :param name: Owned definition name.
    :returns: Status, current value, and current exception tuple.

    .. note::
       In-flight Tasks are intentionally ignored rather than joined or exposed.
    """
    if name in owner._results:
        return VariableInspectionStatus.CACHED, owner._results[name], None
    if name in owner._failures:
        return VariableInspectionStatus.CACHED, None, owner._failures[name]
    return VariableInspectionStatus.NOT_EVALUATED, None, None
