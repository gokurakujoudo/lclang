"""Explicit immutable AST wrappers for call argument forms.

Defines ``LclPositionalArgument``, ``LclStarArgument``, ``LclKeywordArgument``,
``LclKeywordUnpackArgument``.
"""

from __future__ import annotations

from dataclasses import dataclass

from lclang.common.identifiers import VarName
from lclang.error import DataModelErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.ast.ast_base_node import LclAstNode


@guard_constructor(
    LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclPositionalArgument(LclAstNode):
    """Represent one ordinary positional argument.

    :param value: Argument expression.

    .. note::
       Position is preserved by the containing call's argument tuple.
    """

    value: LclAstNode

    @guard_failure(
        LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the argument expression.

        :returns: A one-element value tuple.

        .. note::
           The wrapper remains visible in its parent's traversal.
        """
        return (self.value,)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclStarArgument(LclAstNode):
    """Represent one iterable positional unpacking argument.

    :param value: Iterable expression following ``*``.

    .. note::
       Expansion occurs during call evaluation.
    """

    value: LclAstNode

    @guard_failure(
        LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the unpacked expression.

        :returns: A one-element value tuple.

        .. note::
           The leading star is scalar syntax, not a child.
        """
        return (self.value,)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclKeywordArgument(LclAstNode):
    """Represent one explicitly named keyword argument.

    :param name: Non-empty keyword name.
    :param value: Argument expression.
    :raises LclValidationError: If *name* is empty.

    .. note::
       Duplicate-name validation belongs to the parser.
    """

    name: VarName
    value: LclAstNode

    @guard_failure(
        LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Reject an empty keyword name.

        :raises LclValidationError: If the name is empty.
        """
        if not self.name:
            raise LclValidationError(
                "keyword argument name cannot be empty",
                code=DataModelErrorCode.E22_KEYWORD_ARGUMENT_NAME_CANNOT_BE_EMPTY,
            )

    @guard_failure(
        LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the keyword value expression.

        :returns: A one-element value tuple.

        .. note::
           The keyword name is scalar metadata.
        """
        return (self.value,)


@guard_constructor(
    LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class LclKeywordUnpackArgument(LclAstNode):
    """Represent one mapping keyword unpacking argument.

    :param value: Mapping expression following ``**``.

    .. note::
       Key validation occurs during call evaluation.
    """

    value: LclAstNode

    @guard_failure(
        LclValidationError, DataModelErrorCode.E22_CALL_ARGUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the unpacked mapping expression.

        :returns: A one-element value tuple.

        .. note::
           The double star is scalar syntax, not a child.
        """
        return (self.value,)


type LclCallArgument = (
    LclPositionalArgument | LclStarArgument | LclKeywordArgument | LclKeywordUnpackArgument
)
