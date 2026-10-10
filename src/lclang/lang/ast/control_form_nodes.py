"""Immutable AST values for try and with control expressions.

Defines ``LclExceptHandler``, ``LclTry``, ``LclWithItem``, ``LclWith``.
"""

from __future__ import annotations

from dataclasses import dataclass

from lclang.common.identifiers import VarName
from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.ast.ast_base_node import LclAstNode


@guard_constructor(
    LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclExceptHandler(LclAstNode):
    """Represent one typed or bare exception handler.

    :param exception: Optional expression matched against the failure.
    :param name: Optional name bound to the matched failure.
    :param body: Expression evaluated after a match.
    :raises LclValidationError: If *name* is present without *exception*.

    .. note::
       A handler with no exception is the final catch-all handler.
    """

    exception: LclAstNode | None
    name: VarName | None
    body: LclAstNode

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Validate the optional exception binding.

        :raises LclValidationError: If a binding is empty or belongs to a bare handler.
        """
        if self.name is not None and not self.name:
            raise LclValidationError(
                "except binding name cannot be empty",
                code=DataModelErrorCode.E24_EXCEPT_BINDING_NAME_CANNOT_BE_EMPTY,
            )
        if self.name is not None and self.exception is None:
            raise LclValidationError(
                "bare except handler cannot bind a name",
                code=DataModelErrorCode.E24_BARE_EXCEPT_HANDLER_CANNOT_BIND_A_NAME,
            )

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return optional matcher then body.

        :returns: Body only for bare handlers, otherwise matcher then body.

        .. note::
           The bound name is scalar metadata rather than an expression child.
        """
        if self.exception is None:
            return (self.body,)
        return (self.exception, self.body)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclTry(LclAstNode):
    """Represent recovery handlers and optional finalization.

    :param body: Protected expression.
    :param handlers: Ordered typed and optional final bare handlers.
    :param finally_body: Optional expression always evaluated before completion.
    :raises LclValidationError: If neither handlers nor a finalizer is present.

    .. note::
       Parser validation ensures a bare handler is last.
    """

    body: LclAstNode
    handlers: tuple[LclExceptHandler, ...]
    finally_body: LclAstNode | None = None

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Require recovery or finalization behaviour.

        :raises LclValidationError: If both handlers and finalization are absent.
        """
        if not self.handlers and self.finally_body is None:
            raise LclValidationError(
                "try form requires except or finally",
                code=DataModelErrorCode.E24_TRY_FORM_REQUIRES_EXCEPT_OR_FINALLY,
            )

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return body, handlers, then optional finalizer.

        :returns: All control expressions in source order.

        .. note::
           Runtime matching may skip every handler body.
        """
        children: tuple[LclAstNode, ...] = (self.body, *self.handlers)
        if self.finally_body is None:
            return children
        return (*children, self.finally_body)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclWithItem(LclAstNode):
    """Represent one context expression and optional binding.

    :param context: Expression producing a context manager.
    :param target: Optional non-empty bound name.
    :raises LclValidationError: If *target* is empty.

    .. note::
       Enter and exit protocol behaviour belongs to the evaluator.
    """

    context: LclAstNode
    target: VarName | None = None

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Reject an empty optional binding name.

        :raises LclValidationError: If a supplied target is empty.
        """
        if self.target is not None and not self.target:
            raise LclValidationError(
                "with target name cannot be empty",
                code=DataModelErrorCode.E24_EXCEPT_BINDING_NAME_CANNOT_BE_EMPTY,
            )

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the context expression.

        :returns: A one-element context tuple.

        .. note::
           The optional target is scalar binding metadata.
        """
        return (self.context,)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclWith(LclAstNode):
    """Represent ordered context management around one body.

    :param items: Non-empty context items in enter order.
    :param body: Expression evaluated while contexts are active.
    :raises LclValidationError: If *items* is empty.

    .. note::
       Contexts later exit in reverse order even though children retain source order.
    """

    items: tuple[LclWithItem, ...]
    body: LclAstNode

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Require at least one context item.

        :raises LclValidationError: If the item sequence is empty.
        """
        if not self.items:
            raise LclValidationError(
                "with form requires at least one context item",
                code=DataModelErrorCode.E24_WITH_FORM_REQUIRES_AT_LEAST_ONE_CONTEXT_ITEM,
            )

    @guard_failure(
        LclValidationError, DataModelErrorCode.E24_CONTROL_NODE_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return context items then body.

        :returns: All direct children in source order.

        .. note::
           Reverse exit order is runtime behaviour, not traversal order.
        """
        return (*self.items, self.body)
