"""Immutable source-origin and source-range value objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pylcl.types import SourceName


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
class SourceSpan:
    """Represent a half-open source range within one origin.

    :param origin: Source containing the range.
    :param start: Inclusive first position.
    :param end: Exclusive final position.
    :raises ValueError: If the end precedes the start.

    .. note::
       Empty spans are valid when *start* and *end* are equal.
    """

    origin: SourceOrigin
    start: SourcePosition
    end: SourcePosition

    def __post_init__(self) -> None:
        """Reject ranges whose offsets run backwards.

        :raises ValueError: If the end offset precedes the start offset.
        """
        if self.end.offset < self.start.offset:
            raise ValueError("source span end cannot precede its start")


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
