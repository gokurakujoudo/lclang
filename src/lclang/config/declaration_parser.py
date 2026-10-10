"""Version, using, and binding-name declaration helpers.

Defines ``parse_version``, ``parse_using``, ``validate_definition_name``,
``following_boundary``, ``significant_tokens``.
"""

from pathlib import Path

from lclang.common.source_location import SourceOrigin
from lclang.config.config_document import ConfigUsing
from lclang.config.expression_adapter import parse_config_expression
from lclang.config.logical_line import LogicalLine
from lclang.config.source_coordinate import advance_position
from lclang.error import ConfigurationErrorCode, LclConfigError, LclSyntaxError
from lclang.error.configuration_exception import LclConfigSyntaxError, LclConfigVersionError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.lang.ast import LclConstant, LclJoinedString
from lclang.lang.common.binding_names import validate_qualified_name
from lclang.lang.engine.lexer import Token, TokenKind, scan_tokens


@guard_failure(LclConfigError, ConfigurationErrorCode.E13_CONFIG_DECLARATION_PARSING_NATIVE_FAILURE)
def parse_version(line: LogicalLine, leading: int, origin: SourceOrigin) -> int:
    """Parse the optional leading version metadata line.

    :param line: Logical metadata declaration.
    :param leading: Horizontal indentation before its name.
    :param origin: Owning source origin.
    :returns: Supported integer version.
    :raises LclConfigVersionError: If syntax or the version is unsupported.

    .. note::
       Version metadata is consumed before ordinary declarations are built.
    """
    if line.continued:
        raise LclConfigVersionError(
            "version metadata cannot continue",
            span=line.span,
            code=ConfigurationErrorCode.E13_VERSION_METADATA_CANNOT_CONTINUE,
        )
    rest = line.text[leading + len("__LCL_VERSION__") :]
    if not rest.lstrip(" \t\f").startswith(":"):
        raise LclConfigVersionError(
            "version metadata requires colon",
            span=line.span,
            code=ConfigurationErrorCode.E13_VERSION_METADATA_REQUIRES_COLON,
        )
    colon = leading + len("__LCL_VERSION__") + len(rest) - len(rest.lstrip(" \t\f"))
    value_text = line.text[colon + 1 :]
    start = advance_position(line.start, line.text[: colon + 1])
    try:
        tokens = significant_tokens(
            scan_tokens(value_text, origin=origin, start=start, snapshot=line.span.snapshot)
        )
    except LclSyntaxError as error:
        raise LclConfigVersionError(error.message, span=error.span, code=error.code) from error
    if len(tokens) != 2 or tokens[0].kind is not TokenKind.INTEGER:
        raise LclConfigVersionError(
            "version metadata requires one integer",
            span=line.span,
            code=ConfigurationErrorCode.E13_VERSION_METADATA_REQUIRES_ONE_INTEGER,
        )
    if tokens[0].value != 1:
        raise LclConfigVersionError(
            "unsupported config version",
            span=tokens[0].span,
            code=ConfigurationErrorCode.E13_UNSUPPORTED_CONFIG_VERSION,
        )
    return 1


@guard_failure(LclConfigError, ConfigurationErrorCode.E13_CONFIG_DECLARATION_PARSING_NATIVE_FAILURE)
def parse_using(
    line: LogicalLine,
    leading: int,
    ordinal: int,
    origin: SourceOrigin,
    *,
    keyword: str = "using",
) -> ConfigUsing:
    """Parse one required or optional literal or f-string using declaration.

    :param line: Logical declaration text and span.
    :param leading: Horizontal indentation before `using`.
    :param ordinal: Declaration position in the document.
    :param origin: Owning source origin.
    :returns: Immutable using declaration.
    :param keyword: File-introduction keyword used for syntax and diagnostics.
    :raises LclConfigSyntaxError: If target syntax or suffix is invalid.

    .. note::
       Path resolution is deliberately deferred to the async loader.
    """
    if line.continued:
        raise LclConfigSyntaxError(
            f"{keyword} declaration cannot continue",
            span=line.span,
            code=ConfigurationErrorCode.E13_SOURCE_DECLARATION_CANNOT_CONTINUE,
        )
    optional = line.text[leading:].startswith(keyword + "?")
    keyword_end = leading + len(keyword) + int(optional)
    target_text = line.text[keyword_end:]
    start = advance_position(line.start, line.text[:keyword_end])
    expression = parse_config_expression(
        target_text, origin=origin, start=start, snapshot=line.span.snapshot
    )
    if isinstance(expression, LclConstant) and isinstance(expression.value, str):
        target = expression.value
        if not target:
            raise LclConfigSyntaxError(
                f"{keyword} target must be non-empty text",
                span=expression.span,
                code=ConfigurationErrorCode.E13_SOURCE_TARGET_MUST_BE_NONEMPTY_TEXT,
            )
        if Path(target).suffix != ".lclcfg":
            raise LclConfigSyntaxError(
                f"{keyword} target must end in .lclcfg",
                span=expression.span,
                code=ConfigurationErrorCode.E13_SOURCE_TARGET_MUST_END_IN_LCLCFG,
            )
        return ConfigUsing(target, line.span, ordinal, optional)
    if isinstance(expression, LclJoinedString):
        return ConfigUsing(expression, line.span, ordinal, optional)
    raise LclConfigSyntaxError(
        f"{keyword} requires exactly one string literal or f-string",
        span=expression.span,
        code=ConfigurationErrorCode.E13_SOURCE_DECLARATION_REQUIRES_ONE_STRING_OR_FSTRING,
    )


@guard_failure(
    LclValidationError, ConfigurationErrorCode.E13_CONFIG_DECLARATION_PARSING_NATIVE_FAILURE
)
def validate_definition_name(name: str, line: LogicalLine, origin: SourceOrigin) -> None:
    """Validate one top-level configuration binding spelling.

    :param name: Candidate spelling before the declaration colon.
    :param line: Owning declaration for diagnostic location.
    :param origin: Owning source origin.
    :returns: ``None``.
    :raises LclConfigSyntaxError: If the spelling is not an allowed binding.

    .. note::
       Keyword classification comes from the core lexer rather than Python.
    """
    try:
        validate_qualified_name(name)
    except LclValidationError as error:
        raise LclConfigSyntaxError(
            "invalid config definition name",
            span=line.span,
            code=error.code,
        ) from error
    if name.startswith("__"):
        raise LclConfigSyntaxError(
            "invalid or reserved config definition name",
            span=line.span,
            code=ConfigurationErrorCode.E13_INVALID_OR_RESERVED_CONFIG_DEFINITION_NAME,
        )


@guard_failure(LclConfigError, ConfigurationErrorCode.E13_CONFIG_DECLARATION_PARSING_NATIVE_FAILURE)
def following_boundary(text: str, index: int) -> bool:
    """Check that a recognized declaration word ends at whitespace.

    :param text: Candidate declaration text.
    :param index: Exclusive end of the recognized word.
    :returns: Whether the following character is absent or horizontal space.

    .. note::
       This prevents names such as ``using_value`` from becoming declarations.
    """
    return len(text) == index or text[index] in " \t\f\r\n"


@guard_failure(LclConfigError, ConfigurationErrorCode.E13_CONFIG_DECLARATION_PARSING_NATIVE_FAILURE)
def significant_tokens(tokens: list[Token]) -> list[Token]:
    """Discard physical newline tokens for declaration-level validation.

    :param tokens: Lexer token list containing EOF.
    :returns: Tokens other than physical newlines, preserving EOF.

    .. note::
       Declaration syntax treats retained physical newlines as whitespace.
    """
    return [token for token in tokens if token.kind is not TokenKind.NEWLINE]
