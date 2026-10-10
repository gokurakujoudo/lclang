"""Public immutable dependency classifications and references.

Defines ``DependencyKind``, ``DependencyReference``, ``DependencyEdge``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lclang.common.identifiers import VarName
from lclang.common.source_location import SourceSpan
from lclang.error import RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure


class DependencyKind(StrEnum):
    """Classify when evaluation can request a dependency.

    .. note::
       String values are stable graph and diagnostic labels.
    """

    # Unitless edge labels describe interpreter evaluation timing; distinct values preserve
    # eager, conditional, deferred and dynamic analysis.
    EAGER = "eager"
    CONDITIONAL = "conditional"
    DEFERRED = "deferred"
    DYNAMIC = "dynamic"


@guard_constructor(
    LclValidationError, RuntimeErrorCode.E43_DEPENDENCY_TYPE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class DependencyReference:
    """Identify one free-name occurrence and its evaluation class.

    :param name: Non-empty referenced variable name.
    :param kind: Static or runtime dependency classification.
    :param span: Exact source range of this occurrence.
    :raises LclValidationError: If *name* is empty or *kind* is not a dependency kind.

    .. note::
       Equal names at distinct spans remain distinct diagnostic evidence.
    """

    name: VarName
    kind: DependencyKind
    span: SourceSpan

    @guard_failure(
        LclValidationError, RuntimeErrorCode.E43_DEPENDENCY_TYPE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Validate public dependency vocabulary and identifiers.

        :raises LclValidationError: If the name is empty or kind is invalid.
        """
        if not self.name:
            raise LclValidationError(
                "dependency name cannot be empty",
                code=RuntimeErrorCode.E43_FRAME_BINDING_PATH_CANNOT_BE_EMPTY,
            )
        if not isinstance(self.kind, DependencyKind):
            raise LclValidationError(
                "dependency kind must be a DependencyKind",
                code=RuntimeErrorCode.E43_DEPENDENCY_KIND_MUST_BE_A_DEPENDENCYKIND,
            )


@guard_constructor(
    LclValidationError, RuntimeErrorCode.E43_DEPENDENCY_TYPE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """Connect one definition to one referenced name occurrence.

    :param source: Non-empty definition that owns the reference.
    :param target: Non-empty referenced variable name.
    :param kind: Static or runtime dependency classification.
    :param span: Exact source range of the target occurrence.
    :raises LclValidationError: If an endpoint is empty or *kind* is invalid.

    .. note::
       Repeated endpoint pairs remain distinct edges when spans differ.
    """

    source: VarName
    target: VarName
    kind: DependencyKind
    span: SourceSpan

    @guard_failure(
        LclValidationError, RuntimeErrorCode.E43_DEPENDENCY_TYPE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Validate endpoints and dependency vocabulary.

        :raises LclValidationError: If an endpoint is empty or kind is invalid.
        """
        if not self.source or not self.target:
            raise LclValidationError(
                "dependency edge endpoints cannot be empty",
                code=RuntimeErrorCode.E43_FRAME_BINDING_PATH_CANNOT_BE_EMPTY,
            )
        if not isinstance(self.kind, DependencyKind):
            raise LclValidationError(
                "dependency kind must be a DependencyKind",
                code=RuntimeErrorCode.E43_DEPENDENCY_KIND_MUST_BE_A_DEPENDENCYKIND,
            )
