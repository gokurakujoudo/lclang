"""Immutable AST values for try and with control expressions."""

from __future__ import annotations

from dataclasses import dataclass

from pylcl.ast.base import LclAstNode
from pylcl.types import VarName


@dataclass(frozen=True, slots=True)
class LclExceptHandler(LclAstNode):
    """Represent one typed or bare exception handler.

    :param exception: Optional expression matched against the failure.
    :param name: Optional name bound to the matched failure.
    :param body: Expression evaluated after a match.
    :raises ValueError: If *name* is present without *exception*.

    .. note::
       A handler with no exception is the final catch-all handler.
    """

    exception: LclAstNode | None
    name: VarName | None
    body: LclAstNode

    def __post_init__(self) -> None:
        """Validate the optional exception binding.

        :raises ValueError: If a binding is empty or belongs to a bare handler.
        """
        if self.name is not None and not self.name:
            raise ValueError("except binding name cannot be empty")
        if self.name is not None and self.exception is None:
            raise ValueError("bare except handler cannot bind a name")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return optional matcher then body.

        :returns: Body only for bare handlers, otherwise matcher then body.

        .. note::
           The bound name is scalar metadata rather than an expression child.
        """
        if self.exception is None:
            return (self.body,)
        return (self.exception, self.body)


@dataclass(frozen=True, slots=True)
class LclTry(LclAstNode):
    """Represent recovery handlers and optional finalization.

    :param body: Protected expression.
    :param handlers: Ordered typed and optional final bare handlers.
    :param finally_body: Optional expression always evaluated before completion.
    :raises ValueError: If neither handlers nor a finalizer is present.

    .. note::
       Parser validation ensures a bare handler is last.
    """

    body: LclAstNode
    handlers: tuple[LclExceptHandler, ...]
    finally_body: LclAstNode | None = None

    def __post_init__(self) -> None:
        """Require recovery or finalization behaviour.

        :raises ValueError: If both handlers and finalization are absent.
        """
        if not self.handlers and self.finally_body is None:
            raise ValueError("try form requires except or finally")

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


@dataclass(frozen=True, slots=True)
class LclWithItem(LclAstNode):
    """Represent one context expression and optional binding.

    :param context: Expression producing a context manager.
    :param target: Optional non-empty bound name.
    :raises ValueError: If *target* is empty.

    .. note::
       Enter and exit protocol behaviour belongs to the evaluator.
    """

    context: LclAstNode
    target: VarName | None = None

    def __post_init__(self) -> None:
        """Reject an empty optional binding name.

        :raises ValueError: If a supplied target is empty.
        """
        if self.target is not None and not self.target:
            raise ValueError("with target name cannot be empty")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the context expression.

        :returns: A one-element context tuple.

        .. note::
           The optional target is scalar binding metadata.
        """
        return (self.context,)


@dataclass(frozen=True, slots=True)
class LclWith(LclAstNode):
    """Represent ordered context management around one body.

    :param items: Non-empty context items in enter order.
    :param body: Expression evaluated while contexts are active.
    :raises ValueError: If *items* is empty.

    .. note::
       Contexts later exit in reverse order even though children retain source order.
    """

    items: tuple[LclWithItem, ...]
    body: LclAstNode

    def __post_init__(self) -> None:
        """Require at least one context item.

        :raises ValueError: If the item sequence is empty.
        """
        if not self.items:
            raise ValueError("with form requires at least one context item")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return context items then body.

        :returns: All direct children in source order.

        .. note::
           Reverse exit order is runtime behaviour, not traversal order.
        """
        return (*self.items, self.body)
