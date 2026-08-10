"""Immutable syntax and provenance values for configuration documents."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.ast import LclAstNode
from lclang.source import SourceOrigin, SourceSpan
from lclang.types import VarName


@dataclass(frozen=True, slots=True)
class ConfigDefinition:
    """Represent one source-ordered configuration definition.

    :param name: Valid non-empty variable name.
    :param expression: Parsed semantic LCL expression.
    :param span: Complete physical declaration span.
    :param ordinal: Zero-based declaration position in its document.
    :raises ValueError: If the name is empty or the ordinal is negative.

    .. note::
       Duplicate names remain distinct values through their ordinal and span.
    """

    name: VarName
    expression: LclAstNode
    span: SourceSpan
    ordinal: int

    def __post_init__(self) -> None:
        """Validate the definition's scalar invariants.

        :returns: ``None``.
        :raises ValueError: If the name is empty or ordinal is negative.

        .. note::
           Expression ownership stays immutable and is not copied.
        """
        if not self.name:
            raise ValueError("config definition name cannot be empty")
        if self.ordinal < 0:
            raise ValueError("config declaration ordinal cannot be negative")


@dataclass(frozen=True, slots=True)
class ConfigUsing:
    """Represent one quoted source-expansion declaration.

    :param target: Decoded non-empty path target.
    :param span: Complete physical declaration span.
    :param ordinal: Zero-based declaration position in its document.
    :raises ValueError: If the target is empty or the ordinal is negative.

    .. note::
       The decoded target remains unresolved until expansion.
    """

    target: str
    span: SourceSpan
    ordinal: int

    def __post_init__(self) -> None:
        """Validate the using declaration's scalar invariants.

        :returns: ``None``.
        :raises ValueError: If the target is empty or ordinal is negative.

        .. note::
           Suffix validation belongs to the declaration parser.
        """
        if not self.target:
            raise ValueError("config using target cannot be empty")
        if self.ordinal < 0:
            raise ValueError("config declaration ordinal cannot be negative")


type ConfigDeclaration = ConfigDefinition | ConfigUsing


@dataclass(frozen=True, slots=True)
class ConfigDocument:
    """Describe one parsed but unresolved configuration source.

    :param origin: Physical or synthetic source identity.
    :param version: Positive selected configuration language version.
    :param declarations: Source-ordered immutable declarations.
    :raises ValueError: If the version or declaration ordinals are invalid.

    .. note::
       Documents never resolve using declarations or evaluate expressions.
    """

    origin: SourceOrigin
    version: int
    declarations: tuple[ConfigDeclaration, ...]

    def __post_init__(self) -> None:
        """Detach declarations and validate their strict order.

        :returns: ``None``.
        :raises ValueError: If version, ordinals, or origins are inconsistent.

        .. note::
           Tuple conversion detaches mutable caller-owned iterables.
        """
        declarations = tuple(self.declarations)
        if self.version <= 0:
            raise ValueError("config version must be positive")
        if tuple(item.ordinal for item in declarations) != tuple(range(len(declarations))):
            raise ValueError("config declaration ordinals must be contiguous")
        if any(item.span.origin != self.origin for item in declarations):
            raise ValueError("config declarations must share their document origin")
        object.__setattr__(self, "declarations", declarations)
