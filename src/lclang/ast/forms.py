"""Immutable AST values for function, raise, and assert expression forms."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lclang.ast.base import LclAstNode
from lclang.types import VarName


class ParameterKind(StrEnum):
    """Classify function parameter binding behaviour.

    .. note::
       Values are stable diagnostic labels rather than source prefixes.
    """

    # Unitless signature categories follow Python calling conventions; distinct values preserve
    # positional and keyword binding rules.
    POSITIONAL = "positional"
    KEYWORD_ONLY = "keyword-only"
    VAR_POSITIONAL = "variadic-positional"
    VAR_KEYWORD = "variadic-keyword"


@dataclass(frozen=True, slots=True)
class LclParameter(LclAstNode):
    """Represent one function parameter and optional default.

    :param name: Non-empty binding name.
    :param kind: Positional or variadic binding category.
    :param default: Optional expression evaluated when the function is created.
    :raises ValueError: If *name* is empty or a variadic parameter has a default.

    .. note::
       Ordering and duplicate-name checks belong to the parser.
    """

    name: VarName
    kind: ParameterKind
    default: LclAstNode | None = None

    def __post_init__(self) -> None:
        """Validate local parameter invariants.

        :raises ValueError: If the name is empty or a variadic default is present.
        """
        if not self.name:
            raise ValueError("function parameter name cannot be empty")
        if self.default is not None and self.kind in {
            ParameterKind.VAR_POSITIONAL,
            ParameterKind.VAR_KEYWORD,
        }:
            raise ValueError("variadic function parameter cannot have a default")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the optional default expression.

        :returns: Empty tuple without a default, otherwise a one-element tuple.

        .. note::
           The name and kind are scalar binding metadata.
        """
        return () if self.default is None else (self.default,)


@dataclass(frozen=True, slots=True)
class LclFunction(LclAstNode):
    """Represent an anonymous function expression.

    :param parameters: Ordered explicit parameter values.
    :param body: Complete expression evaluated on invocation.

    .. note::
       Calling a function recursively is prohibited by runtime policy.
    """

    parameters: tuple[LclParameter, ...]
    body: LclAstNode

    def children(self) -> tuple[LclAstNode, ...]:
        """Return parameters then body.

        :returns: All parameter nodes followed by the body expression.

        .. note::
           Default expressions remain nested beneath their parameters.
        """
        return (*self.parameters, self.body)


@dataclass(frozen=True, slots=True)
class LclRaise(LclAstNode):
    """Represent deliberate evaluation failure.

    :param value: Error value evaluated before the failure is raised.

    .. note::
       Runtime wrapping preserves this node's source span.
    """

    value: LclAstNode

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the error value expression.

        :returns: A one-element value tuple.

        .. note::
           The node never produces a normal runtime result.
        """
        return (self.value,)


@dataclass(frozen=True, slots=True)
class LclAssert(LclAstNode):
    """Represent a condition with an optional failure message.

    :param condition: Expression whose truthiness is required.
    :param message: Optional value used when the assertion fails.

    .. note::
       The message is evaluated only when the condition is false.
    """

    condition: LclAstNode
    message: LclAstNode | None = None

    def children(self) -> tuple[LclAstNode, ...]:
        """Return condition followed by an optional message.

        :returns: One or two children in source order.

        .. note::
           Runtime short-circuiting may skip the message child.
        """
        if self.message is None:
            return (self.condition,)
        return (self.condition, self.message)
