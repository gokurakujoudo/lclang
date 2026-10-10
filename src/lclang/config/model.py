"""Immutable syntax and provenance values for configuration documents."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.ast import LclAstNode, LclJoinedString
from lclang.scopes import validate_qualified_name
from lclang.source import SourceOrigin, SourceSpan
from lclang.types import VarName


@dataclass(frozen=True, slots=True)
class ConfigDefinition:
    """Represent one source-ordered configuration definition.

    :param name: Valid non-empty variable name.
    :param expression: Parsed semantic LCL expression.
    :param span: Complete physical declaration span.
    :param ordinal: Zero-based declaration position in its document.
    :param masked: Whether diagnostic renderers must hide this exact value.
    :raises ValueError: If the name is empty or the ordinal is negative.

    .. note::
       Duplicate names remain distinct values through their ordinal and span.
    """

    name: VarName
    expression: LclAstNode
    span: SourceSpan
    ordinal: int
    masked: bool = False

    def __post_init__(self) -> None:
        """Validate the definition's scalar invariants.

        :returns: ``None``.
        :raises TypeError: If the masked flag is not Boolean.
        :raises ValueError: If the name is empty or ordinal is negative.

        .. note::
           Expression ownership stays immutable and is not copied.
        """
        if not self.name:
            raise ValueError("config definition name cannot be empty")
        if self.ordinal < 0:
            raise ValueError("config declaration ordinal cannot be negative")
        if not isinstance(self.masked, bool):
            raise TypeError("config definition masked flag must be Boolean")


@dataclass(frozen=True, slots=True)
class ConfigUsing:
    """Represent one literal or dynamic source-expansion declaration.

    :param target: Decoded literal path or semantic f-string expression.
    :param span: Complete physical declaration span.
    :param ordinal: Zero-based declaration position in its document.
    :param optional: Whether a directly missing source is skipped during loading.
    :raises TypeError: If the target or optional flag has an unsupported type.
    :raises ValueError: If the target is empty or the ordinal is negative.

    .. note::
       Dynamic targets remain unevaluated until their source-order expansion.
    """

    target: str | LclJoinedString
    span: SourceSpan
    ordinal: int
    optional: bool = False

    def __post_init__(self) -> None:
        """Validate the using declaration's scalar invariants.

        :returns: ``None``.
        :raises TypeError: If the target or optional flag has an unsupported type.
        :raises ValueError: If the target is empty or ordinal is negative.

        .. note::
           Suffix validation belongs to the declaration parser.
        """
        if isinstance(self.target, str):
            if not self.target:
                raise ValueError("config using target cannot be empty")
        elif not isinstance(self.target, LclJoinedString):
            raise TypeError("config using target must be text or an LCL f-string")
        if self.ordinal < 0:
            raise ValueError("config declaration ordinal cannot be negative")
        if not isinstance(self.optional, bool):
            raise TypeError("config using optional flag must be Boolean")


@dataclass(frozen=True, slots=True)
class ConfigImport:
    """Represent an independent configuration subtree under a static alias.

    :param target: Decoded literal path or semantic f-string.
    :param span: Complete physical declaration location.
    :param ordinal: Zero-based declaration position in its document.
    :param alias: Static qualified namespace receiving the imported definitions.
    :param optional: Whether a directly missing target contributes nothing.
    :raises TypeError: If a field has an unsupported type.
    :raises ValueError: If the alias, target, or ordinal is invalid.
    """

    target: str | LclJoinedString
    span: SourceSpan
    ordinal: int
    alias: str
    optional: bool = False

    def __post_init__(self) -> None:
        """Validate the shared target contract and static namespace.

        :raises TypeError: If a declaration field has an unsupported type.
        :raises ValueError: If the alias is malformed or reserved.
        """
        if not isinstance(self.span, SourceSpan):
            raise TypeError("config import span must be a SourceSpan")
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise TypeError("config import ordinal must be an integer")
        ConfigUsing(self.target, self.span, self.ordinal, self.optional)
        validate_qualified_name(self.alias)
        if self.alias.startswith("__"):
            raise ValueError("config import alias cannot be reserved")


type ConfigDeclaration = ConfigDefinition | ConfigUsing | ConfigImport


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
