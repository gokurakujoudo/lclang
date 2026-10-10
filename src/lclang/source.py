"""Immutable source-origin and source-range value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lclang.types import SourceName


@dataclass(frozen=True, slots=True)
class SourceOrigin:
    """Describe the logical and optional filesystem origin of source text.

    :param name: Human-readable source name used in diagnostics.
    :param path: Optional normalized filesystem path.

    .. note::
       In-memory sources omit *path* and still retain a diagnostic name.
    """

    name: SourceName
    path: Path | None = None


@dataclass(frozen=True, slots=True, order=True)
class SourcePosition:
    """Represent one position using one-based display coordinates.

    :param line: One-based line number.
    :param column: One-based Unicode code-point column.
    :param offset: Zero-based Unicode code-point offset.
    :raises ValueError: If any coordinate is outside its valid range.

    .. note::
       Lines and columns are one-based; offsets are zero-based code points.
    """

    line: int
    column: int
    offset: int

    def __post_init__(self) -> None:
        """Validate public coordinate invariants after construction.

        :raises ValueError: If any coordinate is outside its valid range.
        """
        if self.line < 1:
            raise ValueError("source line must be positive")
        if self.column < 1:
            raise ValueError("source column must be positive")
        if self.offset < 0:
            raise ValueError("source offset cannot be negative")


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Retain parsed Unicode source without reopening its original file.

    :param text: Original complete source or independently parsed fragment.
    :param start: Physical position corresponding to the first character.
    :raises TypeError: If text or start has an unsupported type.
    """

    text: str
    start: SourcePosition

    def __post_init__(self) -> None:
        """Validate detached source metadata.

        :raises TypeError: If text or start has an unsupported type.
        """
        if not isinstance(self.text, str) or not isinstance(self.start, SourcePosition):
            raise TypeError("source snapshot requires text and a SourcePosition")


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Represent a half-open source range within one origin.

    :param origin: Source containing the range.
    :param start: Inclusive first position.
    :param end: Exclusive final position.
    :param snapshot: Optional immutable parsed source, excluded from position equality.
    :raises ValueError: If the end precedes the start.
    :raises TypeError: If snapshot is neither a SourceSnapshot nor None.

    .. note::
       Empty spans are valid when *start* and *end* are equal.
    """

    origin: SourceOrigin
    start: SourcePosition
    end: SourcePosition
    snapshot: SourceSnapshot | None = field(default=None, kw_only=True, compare=False, repr=False)

    def __post_init__(self) -> None:
        """Reject ranges whose offsets run backwards.

        :raises ValueError: If the end offset precedes the start offset.
        :raises TypeError: If snapshot has an unsupported type.
        """
        if self.end.offset < self.start.offset:
            raise ValueError("source span end cannot precede its start")
        if self.snapshot is not None and not isinstance(self.snapshot, SourceSnapshot):
            raise TypeError("source span snapshot must be a SourceSnapshot or None")


# Defaults below are internal source-less sentinels, not measured positions in an input.
# <unknown> names that origin; line and column use one-based units and offset uses zero-based
# Unicode code points. The empty range at (1, 1, 0) provides the earliest valid location without
# inventing source text.
UNKNOWN_ORIGIN = SourceOrigin(name=SourceName("<unknown>"))
"""Origin used when a node was not produced from concrete source text."""

UNKNOWN_POSITION = SourcePosition(line=1, column=1, offset=0)
"""Position used for source-less values."""

UNKNOWN_SPAN = SourceSpan(
    origin=UNKNOWN_ORIGIN,
    start=UNKNOWN_POSITION,
    end=UNKNOWN_POSITION,
)
"""Empty span used as the immutable default for source-less values."""


def merge_source_spans(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Cover an ordered pair of spans from the same parsed source.

    :param first: First consumed span, supplying the shared origin and start.
    :param last: Final consumed span, supplying the exclusive end.
    :returns: Span covering both endpoints and intervening source text.
    :raises ValueError: If the final end precedes the initial start.
    """
    return SourceSpan(first.origin, first.start, last.end, snapshot=first.snapshot)


def advance_source_position(start: SourcePosition, prefix: str) -> SourcePosition:
    """Advance Unicode coordinates through original physical source text.

    :param start: Physical position before the source prefix.
    :param prefix: Original text, including retained CRLF or other newlines.
    :returns: Position after the prefix; CRLF consumes two offsets and one line.
    """
    line, column, offset = start.line, start.column, start.offset
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
