"""Atomic and tuple AST value nodes."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.ast.base import LclAstNode
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.core import Code as core_codes
from lclang.types import VarName


@guard_constructor(LclValidationError, core_codes.NATIVE_821)
@dataclass(frozen=True, slots=True)
class LclConstant(LclAstNode):
    """Represent an already-decoded literal value.

    :param value: Immutable or runtime-safe literal value.
    :param span: Optional source span inherited from :class:`LclAstNode`.

    .. note::
       Literal-domain validation belongs to the lexer and parser.
    """

    value: object


@guard_constructor(LclValidationError, core_codes.NATIVE_821)
@dataclass(frozen=True, slots=True)
class LclName(LclAstNode):
    """Represent a variable reference.

    :param identifier: Non-empty variable identifier.
    :param span: Optional source span inherited from :class:`LclAstNode`.
    :raises LclValidationError: If *identifier* is empty.

    .. note::
       Name resolution is deferred to runtime evaluation.
    """

    identifier: VarName

    @guard_failure(LclValidationError, core_codes.NATIVE_821)
    def __post_init__(self) -> None:
        """Reject identifiers that cannot name a value.

        :raises LclValidationError: If the identifier is empty.
        """
        if not self.identifier:
            raise LclValidationError(
                "AST name identifier cannot be empty",
                code=core_codes.E21_AST_NAME_IDENTIFIER_CANNOT_BE_EMPTY,
            )


@guard_constructor(LclValidationError, core_codes.NATIVE_821)
@dataclass(frozen=True, slots=True)
class LclTuple(LclAstNode):
    """Represent a tuple expression in source order.

    :param elements: Tuple element nodes.
    :param span: Optional source span inherited from :class:`LclAstNode`.

    .. note::
       An empty tuple is valid and has no children.
    """

    elements: tuple[LclAstNode, ...] = ()

    @guard_failure(LclValidationError, core_codes.NATIVE_821)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return tuple elements in source order.

        :returns: The immutable element tuple supplied at construction.

        .. note::
           No defensive copy is required because the value is already a tuple.
        """
        return self.elements
