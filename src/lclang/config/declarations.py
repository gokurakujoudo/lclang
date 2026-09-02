"""Version, using, and binding-name declaration helpers."""

from pathlib import Path

from lclang.ast import LclConstant, LclJoinedString
from lclang.config.errors import LclConfigSyntaxError, LclConfigVersionError
from lclang.config.expressions import parse_config_expression
from lclang.config.lines import LogicalLine
from lclang.config.model import ConfigUsing
from lclang.config.positions import advance_position
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import Token, TokenKind, scan_tokens
from lclang.scopes import validate_qualified_name
from lclang.source import SourceOrigin


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
        raise LclConfigVersionError("version metadata cannot continue", span=line.span)
    rest = line.text[leading + len("__LCL_VERSION__") :]
    if not rest.lstrip(" \t\f").startswith(":"):
        raise LclConfigVersionError("version metadata requires colon", span=line.span)
    colon = leading + len("__LCL_VERSION__") + len(rest) - len(rest.lstrip(" \t\f"))
    value_text = line.text[colon + 1 :]
    start = advance_position(line.start, line.text[: colon + 1])
    try:
        tokens = significant_tokens(scan_tokens(value_text, origin=origin, start=start))
    except LclSyntaxError as error:
        raise LclConfigVersionError(error.message, span=error.span) from error
    if len(tokens) != 2 or tokens[0].kind is not TokenKind.INTEGER:
        raise LclConfigVersionError("version metadata requires one integer", span=line.span)
    if tokens[0].value != 1:
        raise LclConfigVersionError("unsupported config version", span=tokens[0].span)
    return 1


def parse_using(
    line: LogicalLine,
    leading: int,
    ordinal: int,
    origin: SourceOrigin,
) -> ConfigUsing:
    """Parse one literal or semantic f-string using declaration.

    :param line: Logical declaration text and span.
    :param leading: Horizontal indentation before `using`.
    :param ordinal: Declaration position in the document.
    :param origin: Owning source origin.
    :returns: Immutable using declaration.
    :raises LclConfigSyntaxError: If target syntax or suffix is invalid.

    .. note::
       Path resolution is deliberately deferred to the async loader.
    """
    if line.continued:
        raise LclConfigSyntaxError("using declaration cannot continue", span=line.span)
    target_text = line.text[leading + 5 :]
    start = advance_position(line.start, line.text[: leading + 5])
    expression = parse_config_expression(target_text, origin=origin, start=start)
    if isinstance(expression, LclConstant) and isinstance(expression.value, str):
        target = expression.value
        if not target:
            raise LclConfigSyntaxError("using target must be non-empty text", span=expression.span)
        if Path(target).suffix != ".lclcfg":
            raise LclConfigSyntaxError("using target must end in .lclcfg", span=expression.span)
        return ConfigUsing(target, line.span, ordinal)
    if isinstance(expression, LclJoinedString):
        return ConfigUsing(expression, line.span, ordinal)
    raise LclConfigSyntaxError(
        "using requires exactly one string literal or f-string",
        span=expression.span,
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
    except (TypeError, ValueError) as error:
        raise LclConfigSyntaxError("invalid config definition name", span=line.span) from error
    if name.startswith("__"):
        raise LclConfigSyntaxError("invalid or reserved config definition name", span=line.span)


def following_boundary(text: str, index: int) -> bool:
    """Check that a recognized declaration word ends at whitespace.

    :param text: Candidate declaration text.
    :param index: Exclusive end of the recognized word.
    :returns: Whether the following character is absent or horizontal space.

    .. note::
       This prevents names such as ``using_value`` from becoming declarations.
    """
    return len(text) == index or text[index] in " \t\f\r\n"


def significant_tokens(tokens: list[Token]) -> list[Token]:
    """Discard physical newline tokens for declaration-level validation.

    :param tokens: Lexer token list containing EOF.
    :returns: Tokens other than physical newlines, preserving EOF.

    .. note::
       Declaration syntax treats retained physical newlines as whitespace.
    """
    return [token for token in tokens if token.kind is not TokenKind.NEWLINE]
