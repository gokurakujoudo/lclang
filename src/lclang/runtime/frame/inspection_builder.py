"""Pure construction of name-deduplicated variable inspection trees."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.errors import LclNameError
from lclang.runtime.dependency.analysis import analyze_dependencies
from lclang.runtime.frame.binding_lookup import (
    hierarchy_binding_names,
    is_name_masked,
    select_binding,
)
from lclang.runtime.frame.inspection_values import (
    VariableInspectionStatus,
    VariableInspectionTree,
)
from lclang.scope_proxy import FrameProxy
from lclang.types import VarName

if TYPE_CHECKING:
    from lclang.runtime.frame.frame import Frame






def build_inspection_tree(
    origin: Frame,
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
    selected = select_binding(origin, name)
    owner, path = selected.owner, list(selected.path)
    masked = is_name_masked(origin, name)
    if owner is None:
        return VariableInspectionTree(
            VarName(name),
            VariableInspectionStatus.NOT_EVALUATED,
            None,
            path,
            origin,
            None,
            LclNameError(f"unknown variable: {name}"),
            [],
            masked,
        )
    owner._lifecycle.ensure_open(None)
    if selected.kind == "proxy":
        return VariableInspectionTree(
            VarName(name),
            VariableInspectionStatus.FRAME_PROXY,
            owner.module.definitions.get(name),
            path,
            owner,
            FrameProxy(origin, tuple(name.split("."))),
            None,
            [],
            masked,
        )
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
            owner,
            owner.values[name],
            None,
            [],
            masked,
        )
    status, value, error = inspect_cache(owner, name)
    key = (id(owner), name)
    dependencies: list[VariableInspectionTree] = []
    if key not in ancestors:
        next_ancestors = ancestors | {key}
        dependency_names = dict.fromkeys(
            str(reference.name)
            for reference in analyze_dependencies(
                definition,
                scoped_names=hierarchy_binding_names(owner),
            )
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
        owner,
        value,
        error,
        dependencies,
        masked,
    )





def inspect_cache(
    owner: Frame,
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


def inspect_variable(frame: Frame, var_name: str) -> VariableInspectionTree:
    """Inspect one selected variable and its unique direct dependency names.

    :param frame: Concrete Frame providing the operation state.
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
    frame._lifecycle.ensure_open(None)
    return build_inspection_tree(frame, var_name, frozenset())
