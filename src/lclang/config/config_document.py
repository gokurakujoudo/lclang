"""Immutable syntax and provenance values for configuration documents.

Defines ``ConfigDefinition``, ``ConfigUsing``, ``ConfigImport``, ``ConfigDocument``.
"""

from __future__ import annotations

from dataclasses import dataclass

from lclang.common.identifiers import VarName
from lclang.common.source_location import SourceOrigin, SourceSpan
from lclang.error import ConfigurationErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.ast import LclAstNode, LclJoinedString
from lclang.lang.common.binding_names import validate_qualified_name


@guard_constructor(
    LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class ConfigDefinition:
    """Represent one source-ordered configuration definition.

    :param name: Valid non-empty variable name.
    :param expression: Parsed semantic LCL expression.
    :param span: Complete physical declaration span.
    :param ordinal: Zero-based declaration position in its document.
    :param masked: Whether diagnostic renderers must hide this exact value.
    :raises LclValidationError: If the name is empty or the ordinal is negative.

    .. note::
       Duplicate names remain distinct values through their ordinal and span.
    """

    name: VarName
    expression: LclAstNode
    span: SourceSpan
    ordinal: int
    masked: bool = False

    @guard_failure(
        LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Validate the definition's scalar invariants.

        :returns: ``None``.
        :raises LclValidationError: If the masked flag is not Boolean.
        :raises LclValidationError: If the name is empty or ordinal is negative.

        .. note::
           Expression ownership stays immutable and is not copied.
        """
        if not self.name:
            raise LclValidationError(
                "config definition name cannot be empty",
                code=ConfigurationErrorCode.E34_CONFIG_DEFINITION_NAME_CANNOT_BE_EMPTY,
            )
        if self.ordinal < 0:
            raise LclValidationError(
                "config declaration ordinal cannot be negative",
                code=ConfigurationErrorCode.E34_CONFIG_DECLARATION_ORDINAL_CANNOT_BE_NEGATIVE,
            )
        if not isinstance(self.masked, bool):
            raise LclValidationError(
                "config definition masked flag must be Boolean",
                code=ConfigurationErrorCode.E34_CONFIG_DEFINITION_MASKED_FLAG_MUST_BE_BOOLEAN,
            )


@guard_constructor(
    LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class ConfigUsing:
    """Represent one literal or dynamic source-expansion declaration.

    :param target: Decoded literal path or semantic f-string expression.
    :param span: Complete physical declaration span.
    :param ordinal: Zero-based declaration position in its document.
    :param optional: Whether a directly missing source is skipped during loading.
    :raises LclValidationError: If the target or optional flag has an unsupported type.
    :raises LclValidationError: If the target is empty or the ordinal is negative.

    .. note::
       Dynamic targets remain unevaluated until their source-order expansion.
    """

    target: str | LclJoinedString
    span: SourceSpan
    ordinal: int
    optional: bool = False

    @guard_failure(
        LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Validate the using declaration's scalar invariants.

        :returns: ``None``.
        :raises LclValidationError: If the target or optional flag has an unsupported type.
        :raises LclValidationError: If the target is empty or ordinal is negative.

        .. note::
           Suffix validation belongs to the declaration parser.
        """
        if isinstance(self.target, str):
            if not self.target:
                raise LclValidationError(
                    "config using target cannot be empty",
                    code=ConfigurationErrorCode.E34_CONFIG_DEFINITION_NAME_CANNOT_BE_EMPTY,
                )
        elif not isinstance(self.target, LclJoinedString):
            raise LclValidationError(
                "config using target must be text or an LCL f-string",
                code=ConfigurationErrorCode.E34_CONFIG_USING_TARGET_MUST_BE_TEXT_OR_AN_LCL_F_STRING,
            )
        if self.ordinal < 0:
            raise LclValidationError(
                "config declaration ordinal cannot be negative",
                code=ConfigurationErrorCode.E34_CONFIG_DECLARATION_ORDINAL_CANNOT_BE_NEGATIVE,
            )
        if not isinstance(self.optional, bool):
            raise LclValidationError(
                "config using optional flag must be Boolean",
                code=ConfigurationErrorCode.E34_CONFIG_DEFINITION_MASKED_FLAG_MUST_BE_BOOLEAN,
            )


@guard_constructor(
    LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class ConfigImport:
    """Represent an independent configuration subtree under a static alias.

    :param target: Decoded literal path or semantic f-string.
    :param span: Complete physical declaration location.
    :param ordinal: Zero-based declaration position in its document.
    :param alias: Static qualified namespace receiving the imported definitions.
    :param optional: Whether a directly missing target contributes nothing.
    :raises LclValidationError: If a field has an unsupported type.
    :raises LclValidationError: If the alias, target, or ordinal is invalid.
    """

    target: str | LclJoinedString
    span: SourceSpan
    ordinal: int
    alias: str
    optional: bool = False

    @guard_failure(
        LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Validate the shared target contract and static namespace.

        :raises LclValidationError: If a declaration field has an unsupported type.
        :raises LclValidationError: If the alias is malformed or reserved.
        """
        if not isinstance(self.span, SourceSpan):
            raise LclValidationError(
                "config import span must be a SourceSpan",
                code=ConfigurationErrorCode.E34_CONFIG_IMPORT_SPAN_MUST_BE_A_SOURCESPAN,
            )
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise LclValidationError(
                "config import ordinal must be an integer",
                code=ConfigurationErrorCode.E34_CONFIG_IMPORT_ORDINAL_MUST_BE_AN_INTEGER,
            )
        ConfigUsing(self.target, self.span, self.ordinal, self.optional)
        validate_qualified_name(self.alias)
        if self.alias.startswith("__"):
            raise LclValidationError(
                "config import alias cannot be reserved",
                code=ConfigurationErrorCode.E34_CONFIG_IMPORT_ALIAS_CANNOT_BE_RESERVED,
            )


type ConfigDeclaration = ConfigDefinition | ConfigUsing | ConfigImport


@guard_constructor(
    LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
)
@dataclass(frozen=True, slots=True)
class ConfigDocument:
    """Describe one parsed but unresolved configuration source.

    :param origin: Physical or synthetic source identity.
    :param version: Positive selected configuration language version.
    :param declarations: Source-ordered immutable declarations.
    :raises LclValidationError: If the version or declaration ordinals are invalid.

    .. note::
       Documents never resolve using declarations or evaluate expressions.
    """

    origin: SourceOrigin
    version: int
    declarations: tuple[ConfigDeclaration, ...]

    @guard_failure(
        LclValidationError, ConfigurationErrorCode.E34_CONFIG_DOCUMENT_CONSTRUCTION_NATIVE_FAILURE
    )
    def __post_init__(self) -> None:
        """Detach declarations and validate their strict order.

        :returns: ``None``.
        :raises LclValidationError: If version, ordinals, or origins are inconsistent.

        .. note::
           Tuple conversion detaches mutable caller-owned iterables.
        """
        declarations = tuple(self.declarations)
        if self.version <= 0:
            raise LclValidationError(
                "config version must be positive",
                code=ConfigurationErrorCode.E34_CONFIG_VERSION_MUST_BE_POSITIVE,
            )
        if tuple(item.ordinal for item in declarations) != tuple(range(len(declarations))):
            raise LclValidationError(
                "config declaration ordinals must be contiguous",
                code=ConfigurationErrorCode.E34_CONFIG_DECLARATION_ORDINALS_MUST_BE_CONTIGUOUS,
            )
        if any(item.span.origin != self.origin for item in declarations):
            raise LclValidationError(
                "config declarations must share their document origin",
                code=ConfigurationErrorCode.E34_CONFIG_DECLARATIONS_MUST_SHARE_THEIR_DOCUMENT_ORIGIN,
            )
        object.__setattr__(self, "declarations", declarations)
