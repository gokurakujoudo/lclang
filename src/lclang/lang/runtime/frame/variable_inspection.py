"""Public values and rendering for Frame variable inspection trees.

Defines ``VariableInspectionStatus``, ``VariableInspectionTree``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from lclang.common.identifiers import FrameId, VarName
from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.ast import LclAstNode

if TYPE_CHECKING:
    from lclang.lang.runtime.frame.frame import Frame


class VariableInspectionStatus(StrEnum):
    """Classify the currently observable state of one selected variable.

    .. note::
       In-flight work without a committed snapshot remains ``NotEvaluated``.
    """

    # A definition has a committed result or failure snapshot.
    # Unitless status strings below are the inspection display contract. Their exact labels
    # distinguish committed snapshots, absent evaluation, host or builtin sources and proxies
    # without running user definitions.
    CACHED = "Cached"
    # A definition or unresolved reference has no committed snapshot.
    NOT_EVALUATED = "NotEvaluated"
    # Lookup selected an opaque host-provided value.
    EXTERNAL_PROVIDED = "ExternalProvided"
    # Lookup selected a canonical lclang-provided value.
    NATIVE_PROVIDED = "NativeProvided"
    # Lookup selected an explicit or inferred scoped Frame proxy.
    FRAME_PROXY = "FrameProxy"


@guard_constructor(LclValidationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
@dataclass(slots=True)
class VariableInspectionTree:
    """Describe one variable and its unevaluated dependency descendants.

    :param var_name: Requested semantic variable name.
    :param status: Observable cache or host-value state.
    :param definition: Selected definition syntax, or ``None`` for host/missing names.
    :param definition_path: Child-to-owner Frame identifiers searched by lookup.
    :param defined_at: Selected owner, or lookup origin for a missing name.
    :param current_value: Committed result or raw host value when present.
    :param current_exception: Committed failure or missing-name diagnostic.
    :param dependencies: Ordered first-occurrence child names for this parent.
    :param masked: Whether presentation must redact this node's payload.

    .. note::
       Lists are detached so presentation callers may safely modify their copy.
    """

    var_name: VarName
    status: VariableInspectionStatus
    definition: LclAstNode | None
    definition_path: list[FrameId]
    defined_at: Frame
    current_value: object | None
    current_exception: Exception | None
    dependencies: list[VariableInspectionTree]
    masked: bool = False

    def __repr__(self) -> str:
        """Return a compact non-recursive single-line summary.

        :returns: Stable summary excluding recursive AST, Frame, and child details.

        .. note::
           Values use their escaped representation; failures use their escaped
           message so the output remains one physical line.
        """
        from lclang.lang.runtime.frame.inspection_rendering import render_inspection

        return render_inspection(self)

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E51_VARIABLE_INSPECTION_NATIVE_FAILURE)
    def to_lines(self, depth: int = 0, prefix: str = "- ") -> list[str]:
        """Render this tree as a markdown-style nested list.

        :param depth: Non-negative initial indentation level.
        :param prefix: Marker inserted after each level's indentation.
        :returns: Detached depth-first list containing one line per tree node.
        :raises LclValidationError: If *depth* is not an integer or *prefix* is not a string.
        :raises LclValidationError: If *depth* is negative.

        .. note::
           Every recursive level adds two spaces and reuses the same prefix.
        """
        if not isinstance(depth, int):
            raise LclValidationError(
                "inspection depth must be an integer",
                code=RuntimeErrorCode.E51_INSPECTION_DEPTH_MUST_BE_AN_INTEGER,
            )
        if depth < 0:
            raise LclValidationError(
                "inspection depth cannot be negative",
                code=RuntimeErrorCode.E51_INSPECTION_DEPTH_CANNOT_BE_NEGATIVE,
            )
        if not isinstance(prefix, str):
            raise LclValidationError(
                "inspection prefix must be a string",
                code=RuntimeErrorCode.E51_VARIABLE_NAME_MUST_BE_A_STRING,
            )
        lines = [f"{'  ' * depth}{prefix}{self!r}"]
        if self.masked:
            return lines
        for dependency in self.dependencies:
            lines.extend(dependency.to_lines(depth + 1, prefix))
        return lines
