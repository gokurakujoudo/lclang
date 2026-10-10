# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Pure construction of name-deduplicated variable inspection trees."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error import LclEvaluationError, LclNameError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.runtime import Code as runtime_codes
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


@guard_failure(LclEvaluationError, runtime_codes.NATIVE_251)
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
    :raises LclValidationError: If the Frame parent object graph cycles.
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
            LclNameError(
                f"unknown variable: {name}", code=runtime_codes.E51_UNKNOWN_VARIABLE_VALUE
            ),
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
    definition = None if selected.kind == "host" else owner.module.definitions.get(name)
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


@guard_failure(LclEvaluationError, runtime_codes.NATIVE_251)
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


@guard_failure(LclEvaluationError, runtime_codes.NATIVE_251)
def inspect_variable(frame: Frame, var_name: str) -> VariableInspectionTree:
    """Inspect one selected variable and its unique direct dependency names.

    :param frame: Concrete Frame providing the operation state.
    :param var_name: Non-empty name whose lookup starts at this Frame.
    :returns: A detached tree of cache, syntax, path, and dependency evidence.
    :raises LclValidationError: If *var_name* is not a string.
    :raises LclValidationError: If *var_name* is empty or the parent graph cycles.
    :raises LclClosedFrameError: If this Frame is closing or closed.

    .. note::
       Inspection never evaluates, awaits, creates tasks, or publishes traces.
    """
    if not isinstance(var_name, str):
        raise LclValidationError(
            "variable name must be a string", code=runtime_codes.E51_VARIABLE_NAME_MUST_BE_A_STRING
        )
    if not var_name:
        raise LclValidationError(
            "variable name cannot be empty", code=runtime_codes.E51_VARIABLE_NAME_CANNOT_BE_EMPTY
        )
    frame._lifecycle.ensure_open(None)
    return build_inspection_tree(frame, var_name, frozenset())
