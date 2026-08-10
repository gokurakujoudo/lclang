"""Physical and explicit-continuation line handling for `.lclcfg` text."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.config.errors import LclConfigSyntaxError
from lclang.config.positions import end_position, physical_end, span_for_physical
from lclang.source import SourceOrigin, SourcePosition, SourceSpan


@dataclass(frozen=True, slots=True)
class LogicalLine:
    """Hold one position-preserving logical declaration.

    :param text: Comment-masked text including retained newline sequences.
    :param start: Physical position of the first character.
    :param span: Complete physical range occupied by the declaration.
    :param continued: Whether at least one explicit marker was consumed.

    .. note::
       Masking retains source width so downstream token spans remain physical.
    """

    text: str
    start: SourcePosition
    span: SourceSpan
    continued: bool = False


def scan_logical_lines(text: str, origin: SourceOrigin) -> tuple[LogicalLine, ...]:
    """Scan meaningful logical declarations with explicit continuation.

    :param text: Complete Unicode configuration source.
    :param origin: Origin attached to emitted spans and failures.
    :returns: Meaningful comment-masked logical lines.
    :raises LclConfigSyntaxError: If a continuation has an empty next fragment.

    .. note::
       Blank lines are ignored only outside active continuation chains.
    """
    physical = split_physical_lines(text)
    output: list[LogicalLine] = []
    index = 0
    while index < len(physical):
        content, newline, line, offset = physical[index]
        masked, marker = mask_physical_line(content)
        if not masked.strip():
            index += 1
            continue
        pieces = [masked + newline]
        start = SourcePosition(line, 1, offset)
        continued = marker
        while marker:
            index += 1
            if index >= len(physical):
                raise LclConfigSyntaxError(
                    "continued definition requires another physical line",
                    span=SourceSpan(origin, start, end_position(text)),
                )
            content, newline, _, _ = physical[index]
            masked, marker = mask_physical_line(content)
            if not masked.strip():
                raise LclConfigSyntaxError(
                    "blank or comment-only continuation fragment",
                    span=span_for_physical(origin, physical[index]),
                )
            pieces.append(masked + newline)
        final = physical[index]
        output.append(
            LogicalLine(
                "".join(pieces),
                start,
                SourceSpan(origin, start, physical_end(final)),
                continued,
            )
        )
        index += 1
    return tuple(output)


def split_physical_lines(text: str) -> list[tuple[str, str, int, int]]:
    """Split text while retaining newline spellings and source offsets.

    :param text: Complete Unicode source.
    :returns: Tuples of content, newline, one-based line, and zero-based offset.

    .. note::
       CRLF is retained as one newline string with two code-point offsets.
    """
    result: list[tuple[str, str, int, int]] = []
    offset = 0
    for number, raw in enumerate(text.splitlines(keepends=True), 1):
        newline = ""
        if raw.endswith("\r\n"):
            newline = "\r\n"
        elif raw.endswith(("\r", "\n")):
            newline = raw[-1]
        content = raw[: len(raw) - len(newline)] if newline else raw
        result.append((content, newline, number, offset))
        offset += len(raw)
    return result


def mask_physical_line(content: str) -> tuple[str, bool]:
    """Mask comments and a final outside-literal continuation marker.

    :param content: One physical line without its newline.
    :returns: Same-length masked content and whether it continues.

    .. note::
       Only a marker outside quoted content and before a comment is significant.
    """
    comment = comment_offset(content)
    boundary = len(content) if comment is None else comment
    code = content[:boundary]
    trimmed = code.rstrip(" \t\f")
    marker = bool(trimmed) and trimmed.endswith("\\")
    chars = list(content)
    if marker:
        chars[len(trimmed) - 1] = " "
    if comment is not None:
        chars[comment:] = " " * (len(chars) - comment)
    return "".join(chars), marker


def comment_offset(content: str) -> int | None:
    """Locate the first comment marker outside a quoted literal.

    :param content: Physical line content.
    :returns: Comment offset or ``None`` when no outside marker exists.

    .. note::
       Complete literal parsing remains the responsibility of the core lexer.
    """
    quote: str | None = None
    triple = False
    escaped = False
    index = 0
    while index < len(content):
        char = content[index]
        if quote is None:
            if char == "#":
                return index
            if char in "'\"":
                quote = char
                triple = content[index : index + 3] == char * 3
                index += 2 if triple else 0
        elif escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif triple and content[index : index + 3] == quote * 3:
            quote = None
            index += 2
        elif not triple and char == quote:
            quote = None
        index += 1
    return None
