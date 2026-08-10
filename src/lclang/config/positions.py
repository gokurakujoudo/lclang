"""Small source-coordinate helpers for configuration parsing."""

from lclang.source import SourceOrigin, SourcePosition, SourceSpan


def advance_position(start: SourcePosition, prefix: str) -> SourcePosition:
    """Advance a physical source position across a prefix.

    :param start: Position before the prefix.
    :param prefix: Exact original-width source prefix.
    :returns: Position immediately after the prefix.

    .. note::
       CRLF advances two offsets while counting as one physical newline.
    """
    line = start.line
    column = start.column
    offset = start.offset
    index = 0
    while index < len(prefix):
        if prefix[index : index + 2] == "\r\n":
            index += 2
            offset += 2
            line += 1
            column = 1
        elif prefix[index] in "\r\n":
            index += 1
            offset += 1
            line += 1
            column = 1
        else:
            index += 1
            offset += 1
            column += 1
    return SourcePosition(line, column, offset)


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


def end_position(text: str) -> SourcePosition:
    """Calculate the exclusive position after complete source text.

    :param text: Complete Unicode source.
    :returns: Final source position.

    .. note::
       Empty text uses the conventional initial source position.
    """
    from lclang.config.lines import split_physical_lines

    lines = split_physical_lines(text)
    return SourcePosition(1, 1, 0) if not lines else physical_end(lines[-1])
