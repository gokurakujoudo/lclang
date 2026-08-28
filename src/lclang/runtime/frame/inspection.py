"""Public values and rendering for Frame variable inspection trees."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from lclang.ast import LclAstNode
from lclang.lang.printer import to_source
from lclang.masking import MASKED_VALUE
from lclang.stdlib.namespaces import StdlibNamespace
from lclang.stdlib.recursion import RecursiveFunction
from lclang.types import FrameId, VarName

if TYPE_CHECKING:
    from lclang.runtime.frame.core import Frame


class VariableInspectionStatus(StrEnum):
    """Classify the currently observable state of one selected variable.

    .. note::
       In-flight work without a committed snapshot remains ``NotEvaluated``.
    """

    # A definition has a committed result or failure snapshot.
    CACHED = "Cached"
    # A definition or unresolved reference has no committed snapshot.
    NOT_EVALUATED = "NotEvaluated"
    # Lookup selected an opaque host-provided value.
    EXTERNAL_PROVIDED = "ExternalProvided"
    # Lookup selected a canonical lclang-provided value.
    NATIVE_PROVIDED = "NativeProvided"
    # Lookup selected an explicit or inferred scoped Frame proxy.
    FRAME_PROXY = "FrameProxy"


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
        path = "/".join(str(frame_id) for frame_id in self.definition_path)
        if self.masked:
            return (
                f"{self.var_name}@{path}: ({self.status.value}) {MASKED_VALUE}"
            )
        if self.definition is None:
            definition = (
                ""
                if self.status
                in {
                    VariableInspectionStatus.EXTERNAL_PROVIDED,
                    VariableInspectionStatus.NATIVE_PROVIDED,
                    VariableInspectionStatus.FRAME_PROXY,
                }
                else "<missing> "
            )
        else:
            definition = f"{to_source(self.definition)} "
        if self.current_exception is not None:
            payload = (
                f"{type(self.current_exception).__name__}: "
                f"{compact_text(str(self.current_exception))}"
            )
        elif isinstance(self.current_value, RecursiveFunction):
            payload = compact_repr(self.current_value)
        else:
            payload = (
                native_value_payload(str(self.var_name), self.current_value)
                if self.status is VariableInspectionStatus.NATIVE_PROVIDED
                else (f"{type(self.current_value).__name__}: {compact_repr(self.current_value)}")
            )
        return f"{self.var_name}@{path}: {definition}({self.status.value}) {payload}"

    def to_lines(self, depth: int = 0, prefix: str = "- ") -> list[str]:
        """Render this tree as a markdown-style nested list.

        :param depth: Non-negative initial indentation level.
        :param prefix: Marker inserted after each level's indentation.
        :returns: Detached depth-first list containing one line per tree node.
        :raises TypeError: If *depth* is not an integer or *prefix* is not a string.
        :raises ValueError: If *depth* is negative.

        .. note::
           Every recursive level adds two spaces and reuses the same prefix.
        """
        if not isinstance(depth, int):
            raise TypeError("inspection depth must be an integer")
        if depth < 0:
            raise ValueError("inspection depth cannot be negative")
        if not isinstance(prefix, str):
            raise TypeError("inspection prefix must be a string")
        lines = [f"{'  ' * depth}{prefix}{self!r}"]
        if self.masked:
            return lines
        for dependency in self.dependencies:
            lines.extend(dependency.to_lines(depth + 1, prefix))
        return lines


def compact_repr(value: object) -> str:
    """Return one physical line for an arbitrary current value.

    :param value: Opaque cached value, host object, or exception.
    :returns: Canonical LCL source for supported AST values, otherwise repr.

    .. note::
       Unsupported custom AST nodes retain ordinary repr; all output is one line.
    """
    if isinstance(value, LclAstNode):
        try:
            return compact_text(to_source(value))
        except TypeError:
            pass
    return compact_text(repr(value))


def native_value_payload(name: str, value: object) -> str:
    """Return the uniform dependency-tree payload for a canonical native value.

    :param name: Selected binding name used for callable diagnostics.
    :param value: Reviewed lclang value retained by a canonical Frame.
    :returns: Builtin function/namespace grammar or a typed fallback payload.
    """
    if isinstance(value, StdlibNamespace):
        return f"Builtin Namespace: {value.namespace}"
    if callable(value):
        return f"Builtin Function: {name}"
    return f"{type(value).__name__}: {compact_repr(value)}"


def compact_text(value: str) -> str:
    """Escape physical line breaks in display text.

    :param value: Error message or other text destined for one output line.
    :returns: Text with carriage returns and newlines replaced by escape forms.

    .. note::
       Escaping preserves message content without breaking markdown list output.
    """
    return value.replace("\r", "\\r").replace("\n", "\\n")
