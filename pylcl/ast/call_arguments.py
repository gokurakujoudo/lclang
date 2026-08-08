"""Explicit immutable AST wrappers for call argument forms."""

from __future__ import annotations

from dataclasses import dataclass

from pylcl.ast.base import LclAstNode
from pylcl.types import VarName


@dataclass(frozen=True, slots=True)
class LclPositionalArgument(LclAstNode):
    """Represent one ordinary positional argument.

    :param value: Argument expression.

    .. note::
       Position is preserved by the containing call's argument tuple.
    """

    value: LclAstNode

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the argument expression.

        :returns: A one-element value tuple.

        .. note::
           The wrapper remains visible in its parent's traversal.
        """
        return (self.value,)


@dataclass(frozen=True, slots=True)
class LclStarArgument(LclAstNode):
    """Represent one iterable positional unpacking argument.

    :param value: Iterable expression following ``*``.

    .. note::
       Expansion occurs during call evaluation.
    """

    value: LclAstNode

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the unpacked expression.

        :returns: A one-element value tuple.

        .. note::
           The leading star is scalar syntax, not a child.
        """
        return (self.value,)


@dataclass(frozen=True, slots=True)
class LclKeywordArgument(LclAstNode):
    """Represent one explicitly named keyword argument.

    :param name: Non-empty keyword name.
    :param value: Argument expression.
    :raises ValueError: If *name* is empty.

    .. note::
       Duplicate-name validation belongs to the parser.
    """

    name: VarName
    value: LclAstNode

    def __post_init__(self) -> None:
        """Reject an empty keyword name.

        :raises ValueError: If the name is empty.
        """
        if not self.name:
            raise ValueError("keyword argument name cannot be empty")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the keyword value expression.

        :returns: A one-element value tuple.

        .. note::
           The keyword name is scalar metadata.
        """
        return (self.value,)


@dataclass(frozen=True, slots=True)
class LclKeywordUnpackArgument(LclAstNode):
    """Represent one mapping keyword unpacking argument.

    :param value: Mapping expression following ``**``.

    .. note::
       Key validation occurs during call evaluation.
    """

    value: LclAstNode

    def children(self) -> tuple[LclAstNode, ...]:
        """Return the unpacked mapping expression.

        :returns: A one-element value tuple.

        .. note::
           The double star is scalar syntax, not a child.
        """
        return (self.value,)


type LclCallArgument = (
    LclPositionalArgument
    | LclStarArgument
    | LclKeywordArgument
    | LclKeywordUnpackArgument
)
