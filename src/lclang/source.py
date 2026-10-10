"""Immutable source-origin and source-range value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.core import Code as core_codes
from lclang.types import SourceName


@guard_constructor(LclValidationError, core_codes.NATIVE_811)
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


@guard_constructor(LclValidationError, core_codes.NATIVE_811)
@dataclass(frozen=True, slots=True, order=True)
class SourcePosition:
    """Represent one position using one-based display coordinates.

    :param line: One-based line number.
    :param column: One-based Unicode code-point column.
    :param offset: Zero-based Unicode code-point offset.
    :raises LclValidationError: If any coordinate is outside its valid range.

    .. note::
       Lines and columns are one-based; offsets are zero-based code points.
    """

    line: int
    column: int
    offset: int

    @guard_failure(LclValidationError, core_codes.NATIVE_811)
    def __post_init__(self) -> None:
        """Validate public coordinate invariants after construction.

        :raises LclValidationError: If any coordinate is outside its valid range.
        """
        if any(type(value) is not int for value in (self.line, self.column, self.offset)):
            raise LclValidationError(
                "source coordinates must be integers excluding bool",
                code=core_codes.COORDINATE_TYPE,
            )
        if self.line < 1:
            raise LclValidationError(
                "source line must be positive", code=core_codes.E11_SOURCE_LINE_MUST_BE_POSITIVE
            )
        if self.column < 1:
            raise LclValidationError(
                "source column must be positive", code=core_codes.E11_SOURCE_LINE_MUST_BE_POSITIVE
            )
        if self.offset < 0:
            raise LclValidationError(
                "source offset cannot be negative",
                code=core_codes.E11_SOURCE_OFFSET_CANNOT_BE_NEGATIVE,
            )


@guard_constructor(LclValidationError, core_codes.NATIVE_811)
@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Retain parsed Unicode source without reopening its original file.

    :param text: Original complete source or independently parsed fragment.
    :param start: Physical position corresponding to the first character.
    :raises LclValidationError: If text or start has an unsupported type.
    """

    text: str
    start: SourcePosition

    @guard_failure(LclValidationError, core_codes.NATIVE_811)
    def __post_init__(self) -> None:
        """Validate detached source metadata.

        :raises LclValidationError: If text or start has an unsupported type.
        """
        if not isinstance(self.text, str) or not isinstance(self.start, SourcePosition):
            raise LclValidationError(
                "source snapshot requires text and a SourcePosition",
                code=core_codes.E11_SOURCE_SNAPSHOT_REQUIRES_TEXT_AND_A_SOURCEPOSITION,
            )


@guard_constructor(LclValidationError, core_codes.NATIVE_811)
@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Represent a half-open source range within one origin.

    :param origin: Source containing the range.
    :param start: Inclusive first position.
    :param end: Exclusive final position.
    :param snapshot: Optional immutable parsed source, excluded from position equality.
    :raises LclValidationError: If the end precedes the start.
    :raises LclValidationError: If snapshot is neither a SourceSnapshot nor None.

    .. note::
       Empty spans are valid when *start* and *end* are equal.
    """

    origin: SourceOrigin
    start: SourcePosition
    end: SourcePosition
    snapshot: SourceSnapshot | None = field(default=None, kw_only=True, compare=False, repr=False)

    @guard_failure(LclValidationError, core_codes.NATIVE_811)
    def __post_init__(self) -> None:
        """Reject ranges whose offsets run backwards.

        :raises LclValidationError: If the end offset precedes the start offset.
        :raises LclValidationError: If snapshot has an unsupported type.
        """
        if self.end.offset < self.start.offset:
            raise LclValidationError(
                "source span end cannot precede its start",
                code=core_codes.E11_SOURCE_SPAN_END_CANNOT_PRECEDE_ITS_START,
            )
        if self.snapshot is not None and not isinstance(self.snapshot, SourceSnapshot):
            raise LclValidationError(
                "source span snapshot must be a SourceSnapshot or None",
                code=core_codes.E11_SOURCE_SPAN_SNAPSHOT_MUST_BE_A_SOURCESNAPSHOT_OR_NONE,
            )


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


@guard_failure(LclValidationError, core_codes.NATIVE_811)
def merge_source_spans(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Cover an ordered pair of spans from the same parsed source.

    :param first: First consumed span, supplying the shared origin and start.
    :param last: Final consumed span, supplying the exclusive end.
    :returns: Span covering both endpoints and intervening source text.
    :raises LclValidationError: If the final end precedes the initial start.
    """
    return SourceSpan(first.origin, first.start, last.end, snapshot=first.snapshot)


@guard_failure(LclValidationError, core_codes.NATIVE_811)
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
