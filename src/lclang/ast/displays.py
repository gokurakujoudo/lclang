"""Immutable AST values for collection displays and unpacking."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.ast.base import LclAstNode
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.core import Code as core_codes
from lclang.types import VarName


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclStarred(LclAstNode):
    """Represent iterable unpacking inside a sequence display.

    :param value: Iterable-producing expression following ``*``.

    .. note::
       Placement validation belongs to the parser.
    """

    value: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the unpacked expression.

        :returns: A one-element value tuple.

        .. note::
           The star is scalar syntax, not an AST child.
        """
        return (self.value,)


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclList(LclAstNode):
    """Represent a list display.

    :param elements: Ordinary or starred elements in source order.

    .. note::
       Empty lists are valid and contain no children.
    """

    elements: tuple[LclAstNode, ...] = ()

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return list elements.

        :returns: The immutable source-order element tuple.

        .. note::
           Starred elements remain explicit wrapper nodes.
        """
        return self.elements


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclRecordField(LclAstNode):
    """Represent one named record field.

    :param name: Non-empty field name before ``=``.
    :param value: Expression supplying the retained field value.
    :raises LclValidationError: If *name* is empty.
    """

    name: VarName
    value: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def __post_init__(self) -> None:
        """Reject an empty field name.

        :raises LclValidationError: If the field name is empty.
        """
        if not self.name:
            raise LclValidationError(
                "record field name cannot be empty",
                code=core_codes.E23_RECORD_FIELD_NAME_CANNOT_BE_EMPTY,
            )

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the field value expression.

        :returns: A one-element value tuple.
        """
        return (self.value,)


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclRecordDisplay(LclAstNode):
    """Represent a non-empty immutable record display.

    :param fields: Named fields in source declaration order.
    :raises LclValidationError: If no field is supplied.
    """

    fields: tuple[LclRecordField, ...]

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def __post_init__(self) -> None:
        """Reject an empty record display.

        :raises LclValidationError: If no field is supplied.
        """
        if not self.fields:
            raise LclValidationError(
                "record display requires at least one field",
                code=core_codes.E23_RECORD_DISPLAY_REQUIRES_AT_LEAST_ONE_FIELD,
            )

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return fields in declaration order.

        :returns: Immutable source-order field tuple.
        """
        return self.fields


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclSet(LclAstNode):
    """Represent a non-empty set display.

    :param elements: Ordinary or starred elements in source order.

    .. note::
       The parser uses an empty dict node for ``{}``.
    """

    elements: tuple[LclAstNode, ...]

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return set elements.

        :returns: The immutable source-order element tuple.

        .. note::
           Runtime set ordering does not alter AST source order.
        """
        return self.elements


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclKeyValue(LclAstNode):
    """Represent one explicit dictionary key/value entry.

    :param key: Key expression before ``:``.
    :param value: Value expression after ``:``.

    .. note::
       Duplicate-key handling occurs during ordered evaluation.
    """

    key: LclAstNode
    value: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return key then value expression.

        :returns: Both entry expressions in source order.

        .. note::
           Key and value are evaluated as one explicit entry.
        """
        return (self.key, self.value)


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclDictUnpack(LclAstNode):
    """Represent mapping unpacking inside a dictionary display.

    :param value: Mapping-producing expression following ``**``.

    .. note::
       Expansion retains its location among explicit entries.
    """

    value: LclAstNode

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return the mapping expression.

        :returns: A one-element value tuple.

        .. note::
           The double star is scalar syntax, not a child.
        """
        return (self.value,)


type LclDictEntry = LclKeyValue | LclDictUnpack


@guard_constructor(LclValidationError, core_codes.NATIVE_823)
@dataclass(frozen=True, slots=True)
class LclDict(LclAstNode):
    """Represent a dictionary display with explicit entry forms.

    :param entries: Key/value and unpack entries in source order.

    .. note::
       Empty dictionaries are valid and contain no children.
    """

    entries: tuple[LclDictEntry, ...] = ()

    @guard_failure(LclValidationError, core_codes.NATIVE_823)
    def children(self) -> tuple[LclAstNode, ...]:
        """Return explicit dictionary entries.

        :returns: The immutable source-order entry tuple.

        .. note::
           Entry wrappers remain visible during traversal.
        """
        return self.entries
