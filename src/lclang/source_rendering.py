"""Source excerpts rendered from immutable snapshots without file access."""

from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.core import Code as core_codes
from lclang.source import SourceSpan


@guard_failure(LclValidationError, core_codes.NATIVE_841)
def render_source_location(span: SourceSpan) -> str:
    """Format one-based Unicode source coordinates.

    :param span: Physical or logical source range to describe.
    :returns: Quoted source name followed by line and column.
    """
    return f'"{span.origin.name}":{span.start.line}:{span.start.column}'


@guard_failure(LclValidationError, core_codes.NATIVE_841)
def render_source_excerpt(span: SourceSpan, *, underline: bool = True) -> list[str]:
    """Render the physical lines touched by one source range.

    :param span: Range whose original snapshot supplies the excerpt.
    :param underline: Whether to underline the selected Unicode code points.
    :returns: Original source lines and optional caret lines, or an empty list.
    """
    snapshot = span.snapshot
    if snapshot is None:
        return []
    source_lines = snapshot.text.splitlines() or [""]
    first = span.start.line - snapshot.start.line
    last = span.end.line - snapshot.start.line
    if span.end.column == 1 and span.end.line > span.start.line:
        last -= 1
    output: list[str] = []
    for index in range(max(0, first), min(len(source_lines), last + 1)):
        line = source_lines[index]
        prefix = snapshot.start.column - 1 if index == 0 else 0
        begin = max(0, span.start.column - 1 - prefix) if index == first else 0
        end = (
            span.end.column - 1 - prefix
            if snapshot.start.line + index == span.end.line
            else len(line)
        )
        output.append(" " * prefix + line.expandtabs(4).replace("\f", " "))
        if underline:
            width = len(line[begin : max(begin + 1, end)].expandtabs(4))
            output.append(" " * (prefix + len(line[:begin].expandtabs(4))) + "^" * max(1, width))
    return output
