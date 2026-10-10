"""Small source-coordinate helpers for configuration parsing.

Defines ``advance_position``, ``physical_end``, ``span_for_physical``, ``end_position``.
"""

from lclang.common.source_location import (
    SourceOrigin,
    SourcePosition,
    SourceSpan,
    advance_source_position,
)
from lclang.error import ConfigurationErrorCode, LclConfigError
from lclang.error.operation_guard import guard_failure


@guard_failure(LclConfigError, ConfigurationErrorCode.E11_CONFIG_PARSING_NATIVE_FAILURE)
def advance_position(start: SourcePosition, prefix: str) -> SourcePosition:
    """Advance a physical source position across a prefix.

    :param start: Position before the prefix.
    :param prefix: Exact original-width source prefix.
    :returns: Position immediately after the prefix.

    .. note::
       CRLF advances two offsets while counting as one physical newline.
    """
    return advance_source_position(start, prefix)


@guard_failure(LclConfigError, ConfigurationErrorCode.E11_CONFIG_PARSING_NATIVE_FAILURE)
def physical_end(item: tuple[str, str, int, int]) -> SourcePosition:
    """Return the exclusive position after one physical line.

    :param item: Physical-line tuple containing content, newline, line, and offset.
    :returns: Exclusive original source position.

    .. note::
       Any retained newline moves the result to column one of the next line.
    """
    content, newline, line, offset = item
    if newline:
        return SourcePosition(line + 1, 1, offset + len(content) + len(newline))
    return SourcePosition(line, len(content) + 1, offset + len(content))


@guard_failure(LclConfigError, ConfigurationErrorCode.E11_CONFIG_PARSING_NATIVE_FAILURE)
def span_for_physical(origin: SourceOrigin, item: tuple[str, str, int, int]) -> SourceSpan:
    """Build a complete span for one physical line.

    :param origin: Source containing the line.
    :param item: Physical-line tuple containing content, newline, line, and offset.
    :returns: Complete physical line span.

    .. note::
       The span includes the newline sequence when present.
    """
    _, _, line, offset = item
    return SourceSpan(origin, SourcePosition(line, 1, offset), physical_end(item))


@guard_failure(LclConfigError, ConfigurationErrorCode.E11_CONFIG_PARSING_NATIVE_FAILURE)
def end_position(text: str) -> SourcePosition:
    """Calculate the exclusive position after complete source text.

    :param text: Complete Unicode source.
    :returns: Final source position.

    .. note::
       Empty text uses the conventional initial source position.
    """
    from lclang.config.logical_line import split_physical_lines

    lines = split_physical_lines(text)
    return SourcePosition(1, 1, 0) if not lines else physical_end(lines[-1])
