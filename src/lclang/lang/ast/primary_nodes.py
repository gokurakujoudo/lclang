"""Immutable AST values for chained primary expressions.

Defines ``LclAttribute``, ``LclSafeAttribute``, ``LclSlice``, ``LclSubscript``, ``LclCall``.
"""

from __future__ import annotations

from dataclasses import dataclass

from lclang.common.identifiers import VarName
from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.ast.ast_base_node import LclAstNode
from lclang.lang.ast.call_argument_nodes import LclCallArgument


@guard_constructor(
    LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclAttribute(LclAstNode):
    """Represent ordinary attribute access.

    :param value: Receiver expression.
    :param name: Non-empty attribute name.
    :raises LclValidationError: If *name* is empty.

    .. note::
       Runtime policy rejects underscore-prefixed dot access.
    """

    value: LclAstNode
    name: VarName

    @guard_failure(
        LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Reject an empty attribute name.

        :raises LclValidationError: If the attribute name is empty.
        """
        if not self.name:
            raise LclValidationError(
                "attribute name cannot be empty",
                code=DataModelErrorCode.E29_ATTRIBUTE_NAME_CANNOT_BE_EMPTY,
            )

    @guard_failure(
        LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the receiver expression.

        :returns: A one-element receiver tuple.

        .. note::
           The attribute name is scalar metadata.
        """
        return (self.value,)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclSafeAttribute(LclAstNode):
    """Represent null-safe attribute access.

    :param value: Receiver expression.
    :param name: Non-empty attribute name.
    :raises LclValidationError: If *name* is empty.

    .. note::
       A null receiver returns null without reading the attribute.
    """

    value: LclAstNode
    name: VarName

    @guard_failure(
        LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Reject an empty attribute name.

        :raises LclValidationError: If the attribute name is empty.
        """
        if not self.name:
            raise LclValidationError(
                "safe attribute name cannot be empty",
                code=DataModelErrorCode.E29_ATTRIBUTE_NAME_CANNOT_BE_EMPTY,
            )

    @guard_failure(
        LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the receiver expression.

        :returns: A one-element receiver tuple.

        .. note::
           Runtime evaluation may stop at the receiver.
        """
        return (self.value,)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclSlice(LclAstNode):
    """Represent a slice with independently optional bounds.

    :param lower: Optional inclusive lower bound.
    :param upper: Optional exclusive upper bound.
    :param step: Optional step expression.

    .. note::
       All three omitted values represent ``:``.
    """

    lower: LclAstNode | None = None
    upper: LclAstNode | None = None
    step: LclAstNode | None = None

    @guard_failure(
        LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return only present slice expressions.

        :returns: Lower, upper, and step values with omissions removed.

        .. note::
           Missing positions remain distinguishable through the public fields.
        """
        return tuple(value for value in (self.lower, self.upper, self.step) if value is not None)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclSubscript(LclAstNode):
    """Represent subscription by an expression or slice.

    :param value: Receiver expression.
    :param index: Index, tuple index, or slice expression.

    .. note::
       Extended slicing is represented by a tuple index node.
    """

    value: LclAstNode
    index: LclAstNode

    @guard_failure(
        LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return receiver then index.

        :returns: Both primary operands in source order.

        .. note::
           A slice remains a first-class child node.
        """
        return (self.value, self.index)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclCall(LclAstNode):
    """Represent a function call with explicit argument forms.

    :param function: Callable-producing expression.
    :param arguments: Argument wrapper nodes in source order.

    .. note::
       Argument ordering and duplicate validation belong to the parser.
    """

    function: LclAstNode
    arguments: tuple[LclCallArgument, ...] = ()

    @guard_failure(
        LclValidationError, DataModelErrorCode.E29_PRIMARY_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return function then argument wrappers.

        :returns: All direct children in source order.

        .. note::
           Each wrapper exposes its own value as a nested child.
        """
        return (self.function, *self.arguments)
