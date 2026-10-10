"""Parsing of required aliases on independent file imports."""

from dataclasses import replace

from lclang.config.declarations import parse_using, significant_tokens, validate_definition_name
from lclang.config.errors import LclConfigSyntaxError
from lclang.config.lines import LogicalLine
from lclang.config.model import ConfigImport
from lclang.config.positions import advance_position
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind, scan_tokens
from lclang.source import SourceOrigin


def parse_import(
    line: LogicalLine, leading: int, ordinal: int, origin: SourceOrigin
) -> ConfigImport:
    """Parse a file target followed by ``as`` and a static qualified alias.

    :param line: Position-preserving logical declaration.
    :param leading: Horizontal indentation before the import keyword.
    :param ordinal: Declaration position in the owning document.
    :param origin: Unchanged physical source origin.
    :returns: Validated independent import declaration.
    :raises LclConfigSyntaxError: If target, alias, or delimiter syntax is invalid.
    """
    if line.continued:
        raise LclConfigSyntaxError("import declaration cannot continue", span=line.span)
    keyword_end = leading + (7 if line.text[leading:].startswith("import?") else 6)
    try:
        tokens = significant_tokens(
            scan_tokens(
                line.text[keyword_end:],
                origin=origin,
                start=advance_position(line.start, line.text[:keyword_end]),
                snapshot=line.span.snapshot,
            )
        )
    except LclSyntaxError as error:
        raise LclConfigSyntaxError(error.message, span=error.span) from error
    separators = [token for token in tokens if token.kind is TokenKind.KW_AS]
    if len(separators) != 1:
        raise LclConfigSyntaxError("import requires one static alias after 'as'", span=line.span)
    separator = separators[0]
    boundary = separator.span.start.offset - line.start.offset
    alias_start = separator.span.end.offset - line.start.offset
    alias = line.text[alias_start:].strip()
    validate_definition_name(alias, line, origin)
    target = parse_using(
        replace(line, text=line.text[:boundary]), leading, ordinal, origin, keyword="import"
    )
    return ConfigImport(target.target, line.span, ordinal, alias, target.optional)
